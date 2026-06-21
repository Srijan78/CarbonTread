from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, Response
from services.db import get_db_connection
from services.carbon_calculator import (
    calculate_transport_co2,
    calculate_diet_co2
)
from routes.utils import _get_user_id

onboarding_recap_bp = Blueprint("onboarding_recap", __name__)


# ---------------------------------------------------------------------------
# POST /api/onboarding/recap  (Part B — Last 7 Days)
# ---------------------------------------------------------------------------

@onboarding_recap_bp.route("/api/onboarding/recap", methods=["POST"])
def save_recap() -> Response:
    """
    Compute and persist retroactive 7-day recap events with MEDIUM confidence.

    Expects JSON body with: transport_pattern, car_days (optional),
    recap_fuel (optional), food_pattern, unusual_events (optional list).
    All written events are tagged MEDIUM confidence — retroactive recall, not real-time.
    """
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Missing X-User-ID header"}), 400

    data: dict = request.get_json(silent=True) or {}

    transport_pattern = data.get(
        "transport_pattern",
        "mostly_metro_bus").strip().lower()
    car_days = int(data.get("car_days", 0))
    recap_fuel = data.get("recap_fuel", None)
    if recap_fuel:
        recap_fuel = recap_fuel.strip().lower()
    food_pattern = data.get("food_pattern", "mostly_veg").strip().lower()
    unusual_events: list = data.get("unusual_events", [])

    # Fetch the user's registered profile for context
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT default_commute, commute_fuel_type, default_distance, diet FROM users WHERE id = ?;",
            (user_id,)
        )
        user_row = cursor.fetchone()
        if not user_row:
            return jsonify(
                {"error": "User profile not found. Complete Part A first."}), 404

        default_distance = user_row["default_distance"]

        # Map transport_pattern to car days and non-car days for the 7-day window
        if transport_pattern == "mostly_car":
            effective_car_days = 5
            effective_transit_days = 2
        elif transport_pattern == "mostly_metro_bus":
            effective_car_days = 0
            effective_transit_days = 7
        elif transport_pattern == "mix":
            effective_car_days = max(1, car_days)
            effective_transit_days = 7 - effective_car_days
        elif transport_pattern == "mostly_wfh":
            effective_car_days = 0
            effective_transit_days = 0
        else:
            effective_car_days = 0
            effective_transit_days = 7

        # Determine fuel for car days — reuse profile unless recap provides a new one
        fuel_for_recap = recap_fuel or user_row["commute_fuel_type"] or "petrol"

        events_written = 0
        today = datetime.now()

        # Write car-trip events for estimated car days across the past week
        for day_offset in range(1, effective_car_days + 1):
            event_date = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            co2 = calculate_transport_co2("car", default_distance, fuel_for_recap)
            conn.execute(
                """
                INSERT INTO events (
                    user_id, category, subtype, value, unit,
                    co2_kg, confidence, event_date
                ) VALUES (?, 'transport', ?, ?, 'km', ?, 'MEDIUM', ?);
                """,
                (user_id, f"car_{fuel_for_recap}", default_distance, round(co2, 3), event_date)
            )
            events_written += 1

        # Write transit events for estimated transit days
        for day_offset in range(
                effective_car_days + 1,
                effective_car_days + effective_transit_days + 1):
            event_date = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            co2 = calculate_transport_co2("metro", default_distance)
            conn.execute(
                """
                INSERT INTO events (
                    user_id, category, subtype, value, unit,
                    co2_kg, confidence, event_date
                ) VALUES (?, 'transport', 'metro', ?, 'km', ?, 'MEDIUM', ?);
                """,
                (user_id, default_distance, round(co2, 3), event_date)
            )
            events_written += 1

        # Map food_pattern to diet subtype
        food_subtype_map = {
            "mostly_veg": "vegetarian_day",
            "mostly_non_veg": "non_vegetarian_day",
            "half_half": "mixed"
        }
        food_subtype = food_subtype_map.get(food_pattern, "vegetarian_day")

        # Write food events for the past 7 days
        for day_offset in range(1, 8):
            event_date = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            co2 = calculate_diet_co2(food_pattern)
            conn.execute(
                """
                INSERT INTO events (
                    user_id, category, subtype, value, unit,
                    co2_kg, confidence, event_date
                ) VALUES (?, 'food', ?, 1, 'day', ?, 'MEDIUM', ?);
                """,
                (user_id, food_subtype, round(co2, 3), event_date)
            )
            events_written += 1

        # Write unusual events (flights, big purchases, etc.) — no CO2 score for 'other'
        for unusual in unusual_events:
            event_type = unusual.get("type", "other").strip().lower()
            event_value = float(unusual.get("value", 0))
            event_unit = unusual.get("unit", "event")
            event_date_str = (today - timedelta(days=3)).strftime("%Y-%m-%d")  # Approx mid-week

            if event_type == "flight":
                from services.carbon_calculator import FLIGHT_DOMESTIC
                co2 = round(event_value * FLIGHT_DOMESTIC, 3)
                category = "transport"
                subtype = "flight"
                confidence = "MEDIUM"
            else:
                # big_purchase / other — logged for reference, excluded from CO2 total
                co2 = None
                category = "other"
                subtype = event_type
                confidence = "MEDIUM"

            conn.execute(
                """
                INSERT INTO events (
                    user_id, category, subtype, value, unit,
                    co2_kg, confidence, event_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (user_id, category, subtype, event_value, event_unit, co2, confidence, event_date_str)
            )
            events_written += 1

        conn.commit()
    except Exception as e:
        return jsonify({"error": f"Recap save failed: {str(e)}"}), 500
    finally:
        conn.close()

    return jsonify({"status": "recap saved", "events_written": events_written}), 200
