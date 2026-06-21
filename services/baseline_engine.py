from datetime import datetime, timedelta
from typing import Dict
from services.db import get_db_connection


def recalculate_baseline(user_id: str, reference_date_str: str = None) -> bool:
    """
    Recalculate adaptive baseline for a user based on the prior 7 days of events.

    If a deviation pattern in transport mode or food pattern repeats for >= 4 of the 7 days,
    it updates the user's default configuration and inserts a new 'adaptive' baseline_history record.
    AC usage remains unchanged.

    :param user_id: The unique session user UUID
    :param reference_date_str: Reference date string (format YYYY-MM-DD), defaults to today
    :return: True if a baseline adaptation was triggered and written, False otherwise
    """
    if reference_date_str is None:
        reference_date = datetime.now()
    else:
        try:
            reference_date = datetime.strptime(reference_date_str, "%Y-%m-%d")
        except ValueError:
            reference_date = datetime.now()

    # Determine the prior 7-day range (e.g. yesterday down to 7 days ago)
    end_date = reference_date - timedelta(days=1)
    start_date = reference_date - timedelta(days=7)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    week_start_str = start_str

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Fetch current user profile configuration
        cursor.execute(
            "SELECT default_commute, commute_fuel_type, diet, ac_usage FROM users WHERE id = ?;",
            (user_id,)
        )
        user_row = cursor.fetchone()
        if not user_row:
            return False

        current_commute = user_row["default_commute"]
        current_fuel = user_row["commute_fuel_type"]
        current_diet = user_row["diet"]
        current_ac = user_row["ac_usage"]

        # --- TRANSPORT ADAPTATION ---
        # Query distinct transport events logged by the user in the 7-day window
        cursor.execute(
            """
            SELECT event_date, subtype
            FROM events
            WHERE user_id = ? AND category = 'transport' AND event_date >= ? AND event_date <= ?;
            """,
            (user_id, start_str, end_str)
        )
        transport_logs = cursor.fetchall()

        # Group transport subtype occurrences by unique days
        transport_days: Dict[str, set] = {}  # subtype -> set of event_dates
        for log in transport_logs:
            date = log["event_date"]
            subtype = log["subtype"]

            # Subtype is stored as 'car_petrol', 'car_diesel', etc. or basic mode like 'metro'
            # Parse transport mode and fuel from subtype
            if subtype.startswith("car_"):
                mode = "car"
            elif subtype.startswith("uber_ola_") or subtype in ("uber_ola", "uber", "ola"):
                mode = "uber_ola"
            else:
                mode = subtype

            if mode not in transport_days:
                transport_days[mode] = set()
            transport_days[mode].add(date)

        # Check if any transport mode occurred on >= 4 distinct days
        adapted_commute = current_commute
        adapted_fuel = current_fuel

        for mode, dates in transport_days.items():
            if len(dates) >= 4:
                adapted_commute = mode
                # If the adapted mode is car/uber_ola, aggregate its fuel type
                if mode in ("car", "uber_ola"):
                    fuel_days: Dict[str, set] = {}
                    for log in transport_logs:
                        date = log["event_date"]
                        subtype = log["subtype"]
                        # Determine fuel type suffix
                        fuel = "petrol"  # default fallback
                        if subtype.startswith(f"{mode}_"):
                            fuel = subtype.replace(f"{mode}_", "")

                        if fuel not in fuel_days:
                            fuel_days[fuel] = set()
                        fuel_days[fuel].add(date)

                    # Check if a specific fuel was used on >= 4 days or is dominant
                    for fuel, f_dates in fuel_days.items():
                        if len(f_dates) >= 4:
                            adapted_fuel = fuel
                            break
                else:
                    adapted_fuel = None  # Non-car modes don't have fuel baseline defaults
                break

        # --- DIET ADAPTATION ---
        # Query distinct food events logged by the user in the 7-day window
        cursor.execute(
            """
            SELECT event_date, subtype
            FROM events
            WHERE user_id = ? AND category = 'food' AND event_date >= ? AND event_date <= ?;
            """,
            (user_id, start_str, end_str)
        )
        food_logs = cursor.fetchall()

        food_days: Dict[str, set] = {}  # pattern -> set of event_dates
        for log in food_logs:
            date = log["event_date"]
            subtype = log["subtype"]

            # Map event subtypes ('vegetarian_day', etc.) to profile storage format
            if subtype == "vegetarian_day":
                pattern = "veg"
            elif subtype == "non_vegetarian_day":
                pattern = "non-veg"
            elif subtype == "vegan_day":
                pattern = "vegan"
            elif subtype == "mixed":
                pattern = "mixed"
            else:
                pattern = subtype

            if pattern not in food_days:
                food_days[pattern] = set()
            food_days[pattern].add(date)

        adapted_diet = current_diet
        for pattern, dates in food_days.items():
            if len(dates) >= 4:
                adapted_diet = pattern
                break

        # --- UPDATE VERIFICATION ---
        # Check if anything changed from current baseline
        commute_changed = (adapted_commute != current_commute)
        fuel_changed = (adapted_fuel != current_fuel)
        diet_changed = (adapted_diet != current_diet)

        if commute_changed or fuel_changed or diet_changed:
            # Insert record to baseline_history
            cursor.execute(
                """
                INSERT INTO baseline_history (
                    user_id, week_start_date, transport_mode, transport_fuel_type,
                    food_pattern, ac_usage, source
                ) VALUES (?, ?, ?, ?, ?, ?, 'adaptive');
                """,
                (user_id,
                 week_start_str,
                 adapted_commute,
                 adapted_fuel,
                 adapted_diet,
                 current_ac))

            # Update users table default configurations
            cursor.execute(
                """
                UPDATE users
                SET default_commute = ?, commute_fuel_type = ?, diet = ?
                WHERE id = ?;
                """,
                (adapted_commute, adapted_fuel, adapted_diet, user_id)
            )

            conn.commit()
            return True

        return False
    finally:
        conn.close()
