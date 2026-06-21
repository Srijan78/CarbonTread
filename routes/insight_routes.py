from datetime import datetime, timedelta
from flask import Blueprint, jsonify, Response
from services.db import get_db_connection
from routes.utils import (
    _get_user_id,
    _build_baseline_estimate,
    _merge_events_into_categories
)

insight_bp = Blueprint("insight", __name__)


# ---------------------------------------------------------------------------
# GET /api/insights/confidence
# ---------------------------------------------------------------------------

@insight_bp.route("/api/insights/confidence", methods=["GET"])
def get_confidence() -> Response:
    """
    Compile user tracking data source metrics and trigger confidence warnings/nudges.
    """
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Missing X-User-ID header"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verify user
        cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return jsonify({"error": "User not found"}), 404

        user = dict(user_row)

        # Compile prior 7-day range (today down to 6 days ago)
        today = datetime.now()
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range(7)]
        start_date_str = dates[-1]
        end_date_str = dates[0]

        # Retrieve all events in the last 7 days
        cursor.execute(
            """
            SELECT category, confidence, event_date, co2_kg
            FROM events
            WHERE user_id = ? AND event_date >= ? AND event_date <= ?;
            """,
            (user_id, start_date_str, end_date_str)
        )
        events = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    # Group events by category and event_date to determine highest daily confidence
    category_daily_conf: dict = {
        "transport": {},
        "food": {},
        "energy": {}
    }

    TIER_RANK = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}

    for ev in events:
        cat = ev["category"]
        date_str = ev["event_date"]
        tier = ev["confidence"]

        if cat not in category_daily_conf:
            continue

        current_max = category_daily_conf[cat].get(date_str, "LOW")
        if TIER_RANK.get(tier, 0) > TIER_RANK.get(current_max, 0):
            category_daily_conf[cat][date_str] = tier

    # Calculate metrics for each category
    report: dict = {}
    baseline = _build_baseline_estimate(user)

    weekly_total_co2 = 0.0
    weekly_high_co2 = 0.0
    weekly_medium_co2 = 0.0

    for cat in ("transport", "food", "energy"):
        high_days = 0
        medium_days = 0
        low_days = 0

        for date_str in dates:
            day_conf = category_daily_conf[cat].get(date_str, "LOW")
            if day_conf == "HIGH":
                high_days += 1
            elif day_conf == "MEDIUM":
                medium_days += 1
            else:
                low_days += 1

        # Determine weekly confidence tier for this category
        if high_days >= 4:
            cat_conf = "HIGH"
            source = "Same-day logs"
            nudge = "Excellent tracking! Your emissions reflect your real-world choices."
        elif high_days + medium_days >= 4:
            cat_conf = "MEDIUM"
            source = "Retroactive recaps"
            nudge = "Your data is based on past recollections. Log same-day activities or suggestions to reach high accuracy."
        else:
            cat_conf = "LOW"
            source = "Default baseline"
            nudge = "You are relying on default assumptions. Log your activities daily to see your real impact."

        report[cat] = {
            "confidence": cat_conf,
            "source": source,
            "nudge": nudge,
            "high_days": high_days,
            "medium_days": medium_days,
            "low_days": low_days
        }

    # Recalculate daily totals to find overall weekly clarity percentage
    for date_str in dates:
        day_events = [ev for ev in events if ev["event_date"] == date_str]
        day_categories = _merge_events_into_categories(day_events, baseline)
        for cat_info in day_categories.values():
            co2 = cat_info["co2_kg"]
            conf = cat_info["confidence"]
            weekly_total_co2 += co2
            if conf == "HIGH":
                weekly_high_co2 += co2
            elif conf == "MEDIUM":
                weekly_medium_co2 += co2

    numerator = weekly_high_co2 + weekly_medium_co2 * 0.5
    weekly_clarity = round(
        (numerator / weekly_total_co2 * 100)
        if weekly_total_co2 > 0 else 0.0,
        1
    )

    return jsonify({
        "categories": report,
        "overall_weekly_clarity_pct": weekly_clarity
    }), 200
