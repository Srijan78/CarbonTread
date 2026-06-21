import sqlite3
from flask import request
from services.carbon_calculator import (
    calculate_transport_co2,
    calculate_diet_co2,
    calculate_ac_co2,
    calculate_cooking_co2,
    GRID_FACTOR
)


def _get_user_id() -> str:
    """Extract and return the X-User-ID header from the current request."""
    return request.headers.get("X-User-ID", "").strip()


def _verify_user(user_id: str, conn: sqlite3.Connection) -> bool:
    """Return True if the given user_id exists in the users table."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?;", (user_id,))
    return cursor.fetchone() is not None


def _build_baseline_estimate(user_row: dict) -> dict:
    """
    Compute a full-day LOW-confidence baseline from the user's default profile.

    Returns a dict with category totals and confidence tier 'LOW'.
    """
    transport_co2 = calculate_transport_co2(
        mode=user_row["default_commute"],
        distance_km=float(user_row["default_distance"]),
        fuel_type=user_row["commute_fuel_type"]
    )
    food_co2 = calculate_diet_co2(user_row["diet"])
    ac_co2 = calculate_ac_co2(user_row["ac_usage"])
    cooking_co2 = calculate_cooking_co2(user_row["cooking_fuel"])
    energy_co2 = ac_co2 + cooking_co2

    return {
        "transport": {"co2_kg": round(transport_co2, 3), "confidence": "LOW"},
        "food": {"co2_kg": round(food_co2, 3), "confidence": "LOW"},
        "energy": {"co2_kg": round(energy_co2, 3), "confidence": "LOW"}
    }


def _merge_events_into_categories(events: list, baseline: dict) -> dict:
    """
    Overlay logged events (HIGH or MEDIUM confidence) onto the LOW baseline.

    For each category that has at least one logged event, replace the
    baseline estimate with the sum of logged events and raise the confidence
    tier to the highest tier present among that category's events.
    """
    TIER_RANK = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}

    # Start from baseline
    categories = {
        "transport": {
            "co2_kg": baseline["transport"]["co2_kg"], "confidence": "LOW"},
        "food": {
            "co2_kg": baseline["food"]["co2_kg"], "confidence": "LOW"},
        "energy": {
            "co2_kg": baseline["energy"]["co2_kg"], "confidence": "LOW"}
    }

    logged_totals: dict = {}   # category -> {"co2_kg": float, "confidence": str}

    for ev in events:
        category = ev["category"]
        if category == "other":
            continue  # 'other' events excluded from numeric total per PRD

        co2 = float(ev["co2_kg"]) if ev["co2_kg"] is not None else 0.0
        tier = ev["confidence"]

        if category not in logged_totals:
            logged_totals[category] = {"co2_kg": 0.0, "confidence": "LOW"}

        logged_totals[category]["co2_kg"] += co2

        # Elevate confidence tier if this event's tier is higher
        if TIER_RANK.get(
                tier,
                0) > TIER_RANK.get(
                logged_totals[category]["confidence"],
                0):
            logged_totals[category]["confidence"] = tier

    # Override baseline categories that have at least one logged event
    for category, totals in logged_totals.items():
        if category in categories:
            categories[category] = {
                "co2_kg": round(totals["co2_kg"], 3),
                "confidence": totals["confidence"]
            }

    return categories


def _calculate_event_co2(
        category: str,
        subtype: str,
        value: float,
        fuel_type: str = None) -> float:
    """
    Dispatch CO2 calculation to the correct calculator function based on category and subtype.

    Returns 0.0 for 'other' category events — they are logged but not scored.
    """
    if category == "transport":
        # Map subtype to mode understood by calculator
        mode = subtype.replace(
            f"_{fuel_type}",
            "") if fuel_type and subtype.endswith(
            f"_{fuel_type}") else subtype
        return calculate_transport_co2(
            mode=mode, distance_km=value, fuel_type=fuel_type)

    elif category == "food":
        return calculate_diet_co2(diet_type=subtype)

    elif category == "energy":
        if subtype == "electricity_bill":
            # value is kWh units consumed
            return round(value * GRID_FACTOR, 3)
        elif subtype == "lpg_refill":
            # value is number of cylinders (1 cylinder = 14.2 kg, factor =
            # 2.984 kg CO2/kg)
            return round(value * 14.2 * 2.984, 3)
        elif subtype == "png_usage":
            # value is cubic metres (m3) of piped gas consumed
            # IPCC default: ~2.13 kg CO2/m3 natural gas
            return round(value * 2.13, 3)
        elif subtype == "ac_usage":
            # value is hours of AC use — 2 kWh/hour assumed for typical 1.5T AC
            return round(value * 2.0 * GRID_FACTOR, 3)
        else:
            return 0.0

    return 0.0  # 'other' category or unrecognized
