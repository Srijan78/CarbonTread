from datetime import datetime
from flask import Blueprint, request, jsonify, Response
from services.db import get_db_connection
from services.suggestion_engine import get_daily_suggestions
from routes.utils import _get_user_id, _verify_user

suggestion_bp = Blueprint("suggestion", __name__)


# ---------------------------------------------------------------------------
# GET /api/suggestions
# ---------------------------------------------------------------------------

@suggestion_bp.route("/api/suggestions", methods=["GET"])
def get_suggestions() -> Response:
    """
    Return today's ranked suggestions for the user, generating via Gemini if not cached.

    Delegates entirely to suggestion_engine.get_daily_suggestions which handles
    caching, OpenWeatherMap fetch, deduplication, and Gemini Call 2 invocation.
    """
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Missing X-User-ID header"}), 400

    conn = get_db_connection()
    try:
        if not _verify_user(user_id, conn):
            return jsonify({"error": "User not found"}), 404
    finally:
        conn.close()

    suggestions = get_daily_suggestions(user_id)

    return jsonify({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "suggestions": suggestions
    }), 200


# ---------------------------------------------------------------------------
# POST /api/suggestions/respond
# ---------------------------------------------------------------------------

@suggestion_bp.route("/api/suggestions/respond", methods=["POST"])
def respond_to_suggestion() -> Response:
    """
    Record the user's response to a suggestion and write a confirmed HIGH confidence event.

    Expects JSON body with: suggestion_id (int), response ('I\'ll do it' or 'Not possible today').
    When response is 'I\'ll do it', writes a confirmed HIGH confidence event to the events table —
    identical confidence to a manually logged same-day event, per PRD Section 2.2.
    """
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Missing X-User-ID header"}), 400

    data: dict = request.get_json(silent=True) or {}

    suggestion_id = data.get("suggestion_id", None)
    response_text = data.get("response", "").strip()

    if suggestion_id is None:
        return jsonify({"error": "Missing required field: suggestion_id"}), 400

    valid_responses = ("I'll do it", "Not possible today")
    if response_text not in valid_responses:
        return jsonify(
            {"error": f"Invalid response. Must be one of: {valid_responses}"}), 400

    conn = get_db_connection()
    try:
        if not _verify_user(user_id, conn):
            return jsonify({"error": "User not found"}), 404

        cursor = conn.cursor()

        # Fetch the suggestion row — must belong to this user
        cursor.execute(
            """
            SELECT id, user_id, suggestion_text, category, co2_saved_kg, difficulty
            FROM suggestions
            WHERE id = ? AND user_id = ?;
            """,
            (suggestion_id, user_id)
        )
        suggestion_row = cursor.fetchone()

        if not suggestion_row:
            return jsonify(
                {"error": "Suggestion not found or does not belong to this user"}), 404

        today_str = datetime.now().strftime("%Y-%m-%d")
        acted_on = 1 if response_text == "I'll do it" else 0

        # Update suggestions table with user response
        conn.execute(
            """
            UPDATE suggestions
            SET user_response = ?, acted_on = ?
            WHERE id = ? AND user_id = ?;
            """,
            (response_text, acted_on, suggestion_id, user_id)
        )

        # If confirmed, write a HIGH confidence event — same tier as a manually logged event
        # Per PRD: user explicitly validated on the same day → HIGH confidence,
        # not MEDIUM
        if acted_on:
            category = suggestion_row["category"]
            co2_saved = suggestion_row["co2_saved_kg"]

            # Map suggestion category to a representative subtype for the event
            # record
            subtype_map = {
                "transport": "suggestion_confirmed",
                "food": "suggestion_confirmed",
                "energy": "suggestion_confirmed"
            }
            subtype = subtype_map.get(category, "suggestion_confirmed")

            conn.execute(
                """
                INSERT INTO events (
                    user_id, category, subtype, value, unit,
                    co2_kg, confidence, event_date
                ) VALUES (?, ?, ?, ?, 'suggestion', ?, 'HIGH', ?);
                """,
                (
                    user_id,
                    category,
                    subtype,
                    co2_saved,
                    co2_saved,   # value == co2_saved_kg; unit is 'suggestion'
                    today_str
                )
            )

        conn.commit()
    except Exception as e:
        return jsonify({"error": f"Response save failed: {str(e)}"}), 500
    finally:
        conn.close()

    return jsonify({
        "status": "response recorded",
        "suggestion_id": suggestion_id,
        "response": response_text,
        "acted_on": bool(acted_on)
    }), 200
