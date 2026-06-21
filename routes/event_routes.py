from datetime import datetime
from flask import Blueprint, request, jsonify, Response
from services.db import get_db_connection
from services.carbon_calculator import (
    calculate_transport_co2,
    calculate_diet_co2,
    calculate_counterfactuals
)
from routes.utils import _get_user_id, _verify_user, _calculate_event_co2

event_bp = Blueprint("event", __name__)


# ---------------------------------------------------------------------------
# POST /api/event/log  — Structured manual event logging
# ---------------------------------------------------------------------------

@event_bp.route("/api/event/log", methods=["POST"])
def log_event() -> Response:
    """
    Persist a structured manual event with HIGH confidence and return counterfactual comparison.

    Expects JSON body with: category, subtype, value, unit, fuel_type (optional).
    Counterfactual comparison is returned only for transport car/uber_ola events.
    """
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Missing X-User-ID header"}), 400

    data: dict = request.get_json(silent=True) or {}

    category = data.get("category", "").strip().lower()
    subtype = data.get("subtype", "").strip().lower()
    value = data.get("value", None)
    unit = data.get("unit", "").strip()
    fuel_type = data.get("fuel_type", None)
    if fuel_type:
        fuel_type = fuel_type.strip().lower()

    # Input validation
    if not category or not subtype:
        return jsonify(
            {"error": "Missing required fields: category, subtype"}), 400
    if value is None:
        return jsonify({"error": "Missing required field: value"}), 400
    try:
        value = float(value)
    except (TypeError, ValueError):
        return jsonify({"error": "Field 'value' must be a number"}), 400
    if value < 0:
        return jsonify({"error": "Field 'value' cannot be negative"}), 400

    valid_categories = ("transport", "food", "energy", "other")
    if category not in valid_categories:
        return jsonify(
            {"error": f"Invalid category. Must be one of: {valid_categories}"}), 400

    conn = get_db_connection()
    try:
        if not _verify_user(user_id, conn):
            return jsonify({"error": "User not found"}), 404

        today_str = datetime.now().strftime("%Y-%m-%d")

        # Calculate CO2 — 'other' events get NULL co2_kg
        if category == "other":
            co2_kg = None
            confidence = "HIGH"
        else:
            co2_kg = round(
                _calculate_event_co2(
                    category,
                    subtype,
                    value,
                    fuel_type),
                3)
            confidence = "HIGH"

        # Build counterfactual comparison for car/uber_ola transport events
        counterfactual_alt = None
        counterfactual_co2_kg = None
        counterfactual_payload = None

        if category == "transport" and subtype in ("car", "uber_ola") or (
            category == "transport" and subtype.startswith("car_")
        ):
            # Fetch user's default fuel for comparison baseline
            cursor = conn.cursor()
            cursor.execute(
                "SELECT commute_fuel_type FROM users WHERE id = ?;", (user_id,))
            user_row = cursor.fetchone()
            user_fuel = fuel_type or (
                user_row["commute_fuel_type"] if user_row else "petrol") or "petrol"

            cf = calculate_counterfactuals(
                distance_km=value, user_car_fuel=user_fuel)
            counterfactual_alt = "metro_and_bus"
            # Store the best (metro) alternative as the primary counterfactual CO2 value
            counterfactual_co2_kg = cf["metro_co2"]
            counterfactual_payload = cf

        conn.execute(
            """
            INSERT INTO events (
                user_id, category, subtype, value, unit,
                co2_kg, confidence, counterfactual_alt, counterfactual_co2_kg, event_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (user_id,
             category,
             subtype,
             value,
             unit,
             co2_kg,
             confidence,
             counterfactual_alt,
             counterfactual_co2_kg,
             today_str))
        conn.commit()
    except Exception as e:
        return jsonify({"error": f"Event save failed: {str(e)}"}), 500
    finally:
        conn.close()

    response_payload = {
        "status": "logged",
        "event": {
            "category": category,
            "subtype": subtype,
            "value": value,
            "unit": unit,
            "co2_kg": co2_kg,
            "confidence": confidence,
            "event_date": today_str
        }
    }
    if counterfactual_payload:
        response_payload["counterfactual"] = counterfactual_payload

    return jsonify(response_payload), 201


# ---------------------------------------------------------------------------
# POST /api/event/confirm_baseline  — Confirm today as a usual day
# ---------------------------------------------------------------------------

@event_bp.route("/api/event/confirm_baseline", methods=["POST"])
def confirm_baseline() -> Response:
    """
    Log today's default baseline profile as confirmed HIGH confidence events.

    Deletes today's existing events (excluding 'other') and inserts baseline events.
    """
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Missing X-User-ID header"}), 400

    conn = get_db_connection()
    try:
        if not _verify_user(user_id, conn):
            return jsonify({"error": "User not found"}), 404

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return jsonify({"error": "User not found"}), 404

        today_str = datetime.now().strftime("%Y-%m-%d")

        from services.carbon_calculator import (
            calculate_ac_co2,
            calculate_cooking_co2
        )

        # Calculate CO2 values for baseline
        transport_co2 = calculate_transport_co2(
            mode=user_row["default_commute"],
            distance_km=float(user_row["default_distance"]),
            fuel_type=user_row["commute_fuel_type"]
        )
        food_co2 = calculate_diet_co2(user_row["diet"])
        ac_co2 = calculate_ac_co2(user_row["ac_usage"])
        cooking_co2 = calculate_cooking_co2(user_row["cooking_fuel"])

        diet_map = {
            "veg": "vegetarian_day",
            "non-veg": "non_vegetarian_day",
            "vegan": "vegan_day",
            "mixed": "mixed"
        }
        food_subtype = diet_map.get(user_row["diet"], "vegetarian_day")

        fuel_suffix = f"_{
            user_row['commute_fuel_type']}" if user_row["commute_fuel_type"] else ""
        transport_subtype = f"{user_row['default_commute']}{fuel_suffix}"

        conn.execute(
            "DELETE FROM events WHERE user_id = ? AND event_date = ? AND category != 'other';",
            (user_id, today_str)
        )

        # Insert Transport
        conn.execute(
            """
            INSERT INTO events (user_id, category, subtype, value, unit, co2_kg, confidence, event_date)
            VALUES (?, 'transport', ?, ?, 'km', ?, 'HIGH', ?);
            """,
            (user_id,
             transport_subtype,
             user_row["default_distance"],
             round(
                 transport_co2,
                 3),
                today_str))

        # Insert Food
        conn.execute(
            """
            INSERT INTO events (user_id, category, subtype, value, unit, co2_kg, confidence, event_date)
            VALUES (?, 'food', ?, 1.0, 'day', ?, 'HIGH', ?);
            """,
            (user_id, food_subtype, round(food_co2, 3), today_str)
        )

        # Insert Energy AC
        conn.execute(
            """
            INSERT INTO events (user_id, category, subtype, value, unit, co2_kg, confidence, event_date)
            VALUES (?, 'energy', 'ac_usage', 1.0, 'day', ?, 'HIGH', ?);
            """,
            (user_id, round(ac_co2, 3), today_str)
        )

        # Insert Energy Cooking
        conn.execute(
            """
            INSERT INTO events (user_id, category, subtype, value, unit, co2_kg, confidence, event_date)
            VALUES (?, 'energy', ?, 1.0, 'day', ?, 'HIGH', ?);
            """, (user_id, f"{user_row['cooking_fuel']}_cooking", round(cooking_co2, 3), today_str))

        conn.commit()
    except Exception as e:
        return jsonify({"error": f"Failed to confirm baseline: {str(e)}"}), 500
    finally:
        conn.close()

    return jsonify({"status": "baseline confirmed", "date": today_str}), 200
