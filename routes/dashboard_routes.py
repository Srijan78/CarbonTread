from datetime import datetime
from flask import Blueprint, jsonify, Response
from services.db import get_db_connection
from services.carbon_calculator import DAILY_BUDGET
from routes.utils import (
    _get_user_id,
    _build_baseline_estimate,
    _merge_events_into_categories
)

dashboard_bp = Blueprint("dashboard", __name__)


# ---------------------------------------------------------------------------
# GET /api/dashboard
# ---------------------------------------------------------------------------

@dashboard_bp.route("/api/dashboard", methods=["GET"])
def get_dashboard() -> Response:
    """
    Return today's carbon footprint breakdown, budget ratio, and confidence tiers.

    Merges today's logged events (HIGH/MEDIUM) over the LOW-confidence baseline.
    Filters by the X-User-ID header — returns 400 if header is absent.
    """
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Missing X-User-ID header"}), 400

    today_str = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verify user exists
        cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return jsonify({"error": "User not found"}), 404

        user = dict(user_row)

        # Fetch all of today's non-baseline events
        cursor.execute(
            """
            SELECT category, subtype, co2_kg, confidence
            FROM events
            WHERE user_id = ? AND event_date = ?
            ORDER BY logged_at ASC;
            """,
            (user_id, today_str)
        )
        today_events = [dict(row) for row in cursor.fetchall()]

        # Fetch this week's total (Mon–today) for week comparison
        cursor.execute(
            """
            SELECT SUM(co2_kg) AS week_total
            FROM events
            WHERE user_id = ?
              AND category != 'other'
              AND event_date >= date('now', 'weekday 0', '-7 days')
              AND event_date <= ?;
            """,
            (user_id, today_str)
        )
        week_row = cursor.fetchone()
        week_total_kg = round(float(week_row["week_total"] or 0.0), 3)
    finally:
        conn.close()

    # Build baseline estimate and merge logged events on top
    baseline = _build_baseline_estimate(user)
    categories = _merge_events_into_categories(today_events, baseline)

    # Sum today's total across all three scored categories
    total_co2 = round(sum(c["co2_kg"] for c in categories.values()), 3)
    budget_pct = round((total_co2 / DAILY_BUDGET) * 100, 1)

    # Determine overall day confidence from category tiers
    TIER_RANK = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
    overall_confidence = max(
        categories.values(),
        key=lambda c: TIER_RANK.get(c["confidence"], 0)
    )["confidence"]

    # Build the Sky Gauge clarity percentage
    # HIGH events contribute full clarity, MEDIUM partial, LOW none
    high_co2 = sum(
        c["co2_kg"] for c in categories.values() if c["confidence"] == "HIGH"
    )
    medium_co2 = sum(
        c["co2_kg"] for c in categories.values() if c["confidence"] == "MEDIUM"
    )
    clarity_pct = round(((high_co2 + medium_co2 * 0.5) /
                         total_co2 * 100) if total_co2 > 0 else 0.0, 1)

    # India urban average for context (approx. 7.5 kg CO2/day per WRI
    # estimates)
    INDIA_URBAN_DAILY_AVG = 7.5

    return jsonify({
        "date": today_str,
        "total_co2_kg": total_co2,
        "budget_kg": DAILY_BUDGET,
        "budget_pct": budget_pct,
        "over_budget": total_co2 > DAILY_BUDGET,
        "overall_confidence": overall_confidence,
        "sky_gauge_clarity_pct": clarity_pct,
        "week_total_co2_kg": week_total_kg,
        "india_urban_avg_kg": INDIA_URBAN_DAILY_AVG,
        "categories": {
            "transport": categories["transport"],
            "food": categories["food"],
            "energy": categories["energy"]
        }
    }), 200
