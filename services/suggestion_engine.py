import os
import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Optional, List, Dict, Any

from services.db import get_db_connection
from services.gemini_service import generate_suggestions

logger = logging.getLogger(__name__)

OPENWEATHER_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# Rolling window for suggestion deduplication (number of days to look back)
SUGGESTION_DEDUP_WINDOW_DAYS = 14


def _fetch_weather(city: str) -> Optional[Dict[str, Any]]:
    """
    Fetch current weather data for a given city from OpenWeatherMap.

    Returns a simplified weather dict on success, or None on any failure.
    A None return signals the suggestion engine to skip weather-dependent
    suggestions entirely — never default to a fabricated weather state.
    """
    if not OPENWEATHER_API_KEY:
        logger.warning(
            "OPENWEATHERMAP_API_KEY not set. Skipping weather-dependent suggestions.")
        return None

    try:
        url = (
            f"{OPENWEATHER_BASE_URL}"
            f"?q={urllib.parse.quote(city)}"
            f"&appid={OPENWEATHER_API_KEY}"
            f"&units=metric"
        )
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            return {
                "condition": data["weather"][0]["main"],
                "description": data["weather"][0]["description"],
                "temp_c": data["main"]["temp"],
                "humidity": data["main"]["humidity"]
            }
    except Exception as e:
        logger.error(f"OpenWeatherMap fetch failed for city '{city}': {e}")
        return None


def _get_shown_suggestion_texts(user_id: str, conn) -> List[str]:
    """
    Retrieve suggestion texts shown to the user within the rolling dedup window.

    Returns a list of suggestion_text strings to pass to Gemini as exclusion context.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT suggestion_text FROM suggestions
        WHERE user_id = ?
          AND shown_date >= date('now', ?)
        ORDER BY shown_date DESC;
        """,
        (user_id, f"-{SUGGESTION_DEDUP_WINDOW_DAYS} days")
    )
    rows = cursor.fetchall()
    return [row["suggestion_text"] for row in rows]


def _get_cached_suggestions_for_today(
        user_id: str, conn) -> Optional[List[Dict]]:
    """
    Check if suggestions have already been generated for the user today.

    Returns a list of suggestion dicts if cached for today, else None.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, suggestion_text, category, co2_saved_kg, difficulty, reasoning, user_response, acted_on
        FROM suggestions
        WHERE user_id = ? AND shown_date = ?
        ORDER BY co2_saved_kg DESC;
        """,
        (user_id, today_str)
    )
    rows = cursor.fetchall()
    if rows:
        return [dict(row) for row in rows]
    return None


def _save_suggestions(user_id: str, suggestions: List[Dict], conn) -> None:
    """
    Persist a list of generated suggestion dicts to the suggestions table.

    Each row is written with today's date and a default 'Pending' response status.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor = conn.cursor()
    for s in suggestions:
        cursor.execute(
            """
            INSERT INTO suggestions (
                user_id, suggestion_text, category, co2_saved_kg,
                difficulty, reasoning, shown_date, user_response, acted_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', 0);
            """,
            (
                user_id,
                s.get("action", ""),
                s.get("category", "transport"),
                s.get("co2_saved_kg", 0.0),
                s.get("difficulty", "easy"),
                s.get("reasoning", ""),
                today_str
            )
        )
    conn.commit()


def get_daily_suggestions(user_id: str) -> List[Dict[str, Any]]:
    """
    Return today's suggestions for the user, generating via Gemini if not yet cached.

    Follows the strict fallback rule: if OpenWeatherMap is unavailable,
    weather is passed as None and Gemini is instructed to skip weather-dependent
    recommendations. Suggestions are deduplicated against a rolling window.
    """
    conn = get_db_connection()

    # 1. Return cached suggestions if already generated today
    cached = _get_cached_suggestions_for_today(user_id, conn)
    if cached:
        conn.close()
        return cached

    # 2. Build context: user profile
    cursor = conn.cursor()
    cursor.execute(
        "SELECT city, default_commute, commute_fuel_type, default_distance, diet, ac_usage, cooking_fuel FROM users WHERE id = ?;",
        (user_id,)
    )
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        logger.error(f"User {user_id} not found when generating suggestions.")
        return []

    profile = dict(user_row)

    # 3. Fetch recent events (last 7 days) as history context
    cursor.execute(
        """
        SELECT category, subtype, value, unit, co2_kg, event_date
        FROM events
        WHERE user_id = ? AND event_date >= date('now', '-7 days')
        ORDER BY event_date DESC;
        """,
        (user_id,)
    )
    history_events = [dict(row) for row in cursor.fetchall()]

    # 4. Retrieve rolling dedup history
    suggestion_history = _get_shown_suggestion_texts(user_id, conn)

    # 5. Fetch weather — None on any failure, never a placeholder
    weather = _fetch_weather(profile.get("city", ""))

    # 6. Day of week for context
    day_of_week = datetime.now().strftime("%A")

    # 7. Invoke Gemini Call 2
    result = generate_suggestions(
        profile=profile,
        history_events=history_events,
        suggestion_history=suggestion_history,
        weather=weather,
        day_of_week=day_of_week
    )

    suggestions = result.get("suggestions", [])[:3]

    # 8. Persist generated suggestions
    if suggestions:
        _save_suggestions(user_id, suggestions, conn)

    # Re-fetch from database to guarantee they have IDs and default statuses
    suggestions_with_ids = _get_cached_suggestions_for_today(user_id, conn)
    conn.close()
    return suggestions_with_ids or []
