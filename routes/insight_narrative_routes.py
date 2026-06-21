from datetime import datetime, timedelta
from flask import Blueprint, jsonify, Response
from services.db import get_db_connection
from services.gemini_service import generate_weekly_narrative
from routes.utils import (
    _get_user_id,
    _build_baseline_estimate,
    _merge_events_into_categories
)

insight_narrative_bp = Blueprint("insight_narrative", __name__)


# ---------------------------------------------------------------------------
# GET /api/insights/narrative
# ---------------------------------------------------------------------------

@insight_narrative_bp.route("/api/insights/narrative", methods=["GET"])
def get_narrative() -> Response:
    """
    Return a weekly narrative, using cached narrative if generated in the last 7 days.
    """
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Missing X-User-ID header"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verify user
        cursor.execute("SELECT id FROM users WHERE id = ?;", (user_id,))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404

        # Check for cached narrative from last 7 days
        cursor.execute(
            """
            SELECT narrative_text, generated_at
            FROM weekly_narratives
            WHERE user_id = ?
            ORDER BY generated_at DESC
            LIMIT 1;
            """,
            (user_id,)
        )
        narrative_row = cursor.fetchone()

        def _is_cache_valid(gen_at_str: str) -> bool:
            try:
                gen_time = datetime.strptime(gen_at_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    gen_time = datetime.strptime(
                        gen_at_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return False
            return (datetime.utcnow() - gen_time) < timedelta(days=7)

        if narrative_row and _is_cache_valid(narrative_row["generated_at"]):
            narrative_text = narrative_row["narrative_text"]
            if "•" in narrative_text:
                return jsonify({"narrative": narrative_text}), 200

        # Cache is invalid; generate a new narrative
        cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
        user = dict(cursor.fetchone())

        today = datetime.now()
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range(7)]
        start_date_str = dates[-1]
        end_date_str = dates[0]

        cursor.execute(
            """
            SELECT category, confidence, event_date, co2_kg, subtype, value, unit
            FROM events
            WHERE user_id = ? AND event_date >= ? AND event_date <= ?;
            """,
            (user_id, start_date_str, end_date_str)
        )
        weekly_events = [dict(row) for row in cursor.fetchall()]

        # Generate confidence report
        category_daily_conf: dict = {"transport": {}, "food": {}, "energy": {}}
        TIER_RANK = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}

        for ev in weekly_events:
            cat = ev["category"]
            date_str = ev["event_date"]
            tier = ev["confidence"]

            if cat not in category_daily_conf:
                continue

            current_max = category_daily_conf[cat].get(date_str, "LOW")
            if TIER_RANK.get(tier, 0) > TIER_RANK.get(current_max, 0):
                category_daily_conf[cat][date_str] = tier

        confidence_report: dict = {}
        for cat in ("transport", "food", "energy"):
            high_days = 0
            medium_days = 0
            for date_str in dates:
                day_conf = category_daily_conf[cat].get(date_str, "LOW")
                if day_conf == "HIGH":
                    high_days += 1
                elif day_conf == "MEDIUM":
                    medium_days += 1

            if high_days >= 4:
                cat_conf = "HIGH"
            elif high_days + medium_days >= 4:
                cat_conf = "MEDIUM"
            else:
                cat_conf = "LOW"
            confidence_report[cat] = cat_conf

        # Calculate category breakdown
        baseline = _build_baseline_estimate(user)
        transport_co2 = 0.0
        food_co2 = 0.0
        energy_co2 = 0.0

        for date_str in dates:
            day_events = [
                ev for ev in weekly_events if ev["event_date"] == date_str]
            day_categories = _merge_events_into_categories(day_events, baseline)
            transport_co2 += day_categories["transport"]["co2_kg"]
            food_co2 += day_categories["food"]["co2_kg"]
            energy_co2 += day_categories["energy"]["co2_kg"]

        category_breakdown = {
            "transport": round(transport_co2, 3),
            "food": round(food_co2, 3),
            "energy": round(energy_co2, 3)
        }

        narrative_text = generate_weekly_narrative(
            weekly_events=weekly_events,
            confidence_report=confidence_report,
            category_breakdown=category_breakdown
        )

        cursor.execute(
            """
            INSERT INTO weekly_narratives (user_id, week_start_date, narrative_text)
            VALUES (?, ?, ?);
            """,
            (user_id, start_date_str, narrative_text)
        )
        conn.commit()
    except Exception as e:
        return jsonify(
            {"error": f"Failed to cache generated narrative: {str(e)}"}), 500
    finally:
        conn.close()

    return jsonify({"narrative": narrative_text}), 200
