import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, Response
from services.db import get_db_connection
from services.carbon_calculator import get_distance_midpoint
from routes.utils import _get_user_id

onboarding_bp = Blueprint("onboarding", __name__)


# ---------------------------------------------------------------------------
# POST /api/session/init
# ---------------------------------------------------------------------------

@onboarding_bp.route("/api/session/init", methods=["POST"])
def session_init() -> Response:
    """
    Create a new user session with a server-generated UUID.

    Returns the UUID to the frontend for storage in localStorage.
    This is the ONLY endpoint that inserts a row into the users table.
    """
    new_uuid = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO users (id, city, default_commute, commute_fuel_type,
                               default_distance, diet, ac_usage, cooking_fuel)
            VALUES (?, '', '', NULL, 0.0, '', '', '');
            """,
            (new_uuid,)
        )
        conn.commit()
    except Exception as e:
        return jsonify({"error": f"Session creation failed: {str(e)}"}), 500
    finally:
        conn.close()

    return jsonify({"user_id": new_uuid}), 201


# ---------------------------------------------------------------------------
# POST /api/onboarding/profile  (Part A — Base Profile)
# ---------------------------------------------------------------------------

@onboarding_bp.route("/api/onboarding/profile", methods=["POST"])
def save_profile() -> Response:
    """
    Persist onboarding Part A base profile answers and write to baseline_history.

    Expects JSON body with: city, commute_mode, commute_fuel (optional),
    distance_bucket, diet, ac_usage, cooking_fuel.
    """
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Missing X-User-ID header"}), 400

    data: dict = request.get_json(silent=True) or {}

    city = data.get("city", "").strip()
    commute_mode = data.get("commute_mode", "").strip().lower()
    commute_fuel = data.get("commute_fuel", None)
    if commute_fuel:
        commute_fuel = commute_fuel.strip().lower()
    distance_bucket = data.get("distance_bucket", "5-15km").strip()
    diet = data.get("diet", "veg").strip().lower()
    ac_usage = data.get("ac_usage", "no").strip().lower()
    cooking_fuel = data.get("cooking_fuel", "lpg").strip().lower()

    if not city or not commute_mode or not diet:
        return jsonify(
            {"error": "Missing required profile fields: city, commute_mode, diet"}), 400

    distance_km = get_distance_midpoint(distance_bucket)

    conn = get_db_connection()
    try:
        # Update the users row created at session init
        conn.execute(
            """
            UPDATE users
            SET city = ?, default_commute = ?, commute_fuel_type = ?,
                default_distance = ?, diet = ?, ac_usage = ?, cooking_fuel = ?
            WHERE id = ?;
            """,
            (city,
             commute_mode,
             commute_fuel,
             distance_km,
             diet,
             ac_usage,
             cooking_fuel,
             user_id))

        # Write initial onboarding baseline_history record
        week_start = datetime.now().strftime("%Y-%m-%d")
        conn.execute(
            """
            INSERT INTO baseline_history (
                user_id, week_start_date, transport_mode, transport_fuel_type,
                food_pattern, ac_usage, source
            ) VALUES (?, ?, ?, ?, ?, ?, 'onboarding');
            """,
            (user_id, week_start, commute_mode, commute_fuel, diet, ac_usage)
        )
        conn.commit()
    except Exception as e:
        return jsonify({"error": f"Profile save failed: {str(e)}"}), 500
    finally:
        conn.close()

    return jsonify({"status": "profile saved",
                   "distance_km": distance_km}), 200
