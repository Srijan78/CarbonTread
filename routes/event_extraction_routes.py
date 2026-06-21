from datetime import datetime
from flask import Blueprint, request, jsonify, Response
from services.db import get_db_connection
from services.gemini_service import extract_event_from_text
from routes.utils import _get_user_id, _verify_user, _calculate_event_co2

event_extraction_bp = Blueprint("event_extraction", __name__)


# ---------------------------------------------------------------------------
# POST /api/event/extract  — Free-text event extraction via Gemini Call 1
# ---------------------------------------------------------------------------

@event_extraction_bp.route("/api/event/extract", methods=["POST"])
def extract_event() -> Response:
    """
    Parse a free-text description into a structured event via Gemini Call 1 and log it.

    Expects JSON body with: text (the user's raw description).
    If 'unrecognized' is set in the Gemini output, returns a 422 with a prompt
    to log manually rather than silently writing a bad record.
    """
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Missing X-User-ID header"}), 400

    data: dict = request.get_json(silent=True) or {}
    text: str = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "Missing required field: text"}), 400

    if len(text) > 500:
        return jsonify(
            {"error": "Input text exceeds 500 character limit"}), 400

    text = "".join(ch for ch in text if ch.isprintable())

    conn = get_db_connection()
    try:
        if not _verify_user(user_id, conn):
            return jsonify({"error": "User not found"}), 404

        extracted = extract_event_from_text(text)

        if extracted.get("unrecognized"):
            return jsonify({
                "error": "Could not confidently extract a loggable event from your input.",
                "unrecognized": extracted["unrecognized"],
                "suggestion": "Please use the structured Event Logger to log this activity."
            }), 422

        category = extracted.get("category", "other").lower()
        subtype = extracted.get("subtype", "").lower()
        value = float(extracted.get("value", 0))
        unit = extracted.get("unit", "event")
        confidence_raw = extracted.get("confidence", "low").upper()
        confidence = confidence_raw if confidence_raw in (
            "HIGH", "MEDIUM", "LOW") else "LOW"

        today_str = datetime.now().strftime("%Y-%m-%d")

        if category == "other":
            co2_kg = None
        else:
            fuel_type = None
            if category == "transport" and subtype.startswith("car_"):
                fuel_type = subtype.replace("car_", "")
                subtype = "car"
            co2_kg = round(
                _calculate_event_co2(
                    category,
                    subtype,
                    value,
                    fuel_type),
                3)

        conn.execute(
            """
            INSERT INTO events (
                user_id, category, subtype, value, unit,
                co2_kg, confidence, event_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (user_id, category, subtype, value, unit, co2_kg, confidence, today_str)
        )
        conn.commit()
    except Exception as e:
        return jsonify(
            {"error": f"Event save failed after extraction: {str(e)}"}), 500
    finally:
        conn.close()

    return jsonify({
        "status": "extracted and logged",
        "event": {
            "category": category,
            "subtype": subtype,
            "value": value,
            "unit": unit,
            "co2_kg": co2_kg,
            "confidence": confidence,
            "event_date": today_str
        }
    }), 201
