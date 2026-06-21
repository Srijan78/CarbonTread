import pytest
import os
import tempfile
import services.db
from services.db import get_db_connection, init_db
from services.baseline_engine import recalculate_baseline


@pytest.fixture(autouse=True)
def temp_database():
    """Create and configure a clean temporary SQLite database for each test, then clean up."""
    db_fd, temp_db_path = tempfile.mkstemp()
    # Override global DB_PATH in services.db so all connections point here
    old_db_path = services.db.DB_PATH
    services.db.DB_PATH = temp_db_path

    # Initialize schema
    init_db()

    yield

    # Restore original path and unlink temp database file
    services.db.DB_PATH = old_db_path
    os.close(db_fd)
    try:
        os.unlink(temp_db_path)
    except OSError:
        pass


def _create_test_user(user_id: str) -> None:
    """Helper to insert a test user into the database."""
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO users (id, city, default_commute, commute_fuel_type,
                           default_distance, diet, ac_usage, cooking_fuel)
        VALUES (?, 'Mumbai', 'car', 'petrol', 10.0, 'non-veg', 'yes', 'lpg');
        """,
        (user_id,)
    )
    conn.commit()
    conn.close()


def test_baseline_no_change_without_events() -> None:
    """Verify that baseline does not adapt when there are no logged events."""
    user_id = "test-user-1"
    _create_test_user(user_id)

    # Recalculate baseline for today
    ref_date = "2026-06-21"
    changed = recalculate_baseline(user_id, ref_date)
    assert not changed

    # Verify defaults are unchanged
    conn = get_db_connection()
    row = conn.execute("SELECT default_commute, diet FROM users WHERE id = ?;", (user_id,)).fetchone()
    assert row["default_commute"] == "car"
    assert row["diet"] == "non-veg"
    conn.close()


def test_baseline_no_change_below_threshold() -> None:
    """Verify that baseline does not adapt if a pattern occurs less than 4 times."""
    user_id = "test-user-2"
    _create_test_user(user_id)

    # Log 3 metro events (below the 4/7 day threshold)
    # Range: 2026-06-14 to 2026-06-20
    conn = get_db_connection()
    for day in ("2026-06-14", "2026-06-15", "2026-06-16"):
        conn.execute(
            """
            INSERT INTO events (user_id, category, subtype, value, unit, co2_kg, confidence, event_date)
            VALUES (?, 'transport', 'metro', 10.0, 'km', 0.12, 'HIGH', ?);
            """,
            (user_id, day)
        )
    conn.commit()
    conn.close()

    changed = recalculate_baseline(user_id, "2026-06-21")
    assert not changed

    # Verify defaults are unchanged
    conn = get_db_connection()
    row = conn.execute("SELECT default_commute FROM users WHERE id = ?;", (user_id,)).fetchone()
    assert row["default_commute"] == "car"
    conn.close()


def test_baseline_adapts_transport_mode() -> None:
    """Verify that baseline commute mode adapts when logged on >= 4 days."""
    user_id = "test-user-3"
    _create_test_user(user_id)

    # Log 4 metro events
    conn = get_db_connection()
    for day in ("2026-06-14", "2026-06-15", "2026-06-16", "2026-06-17"):
        conn.execute(
            """
            INSERT INTO events (user_id, category, subtype, value, unit, co2_kg, confidence, event_date)
            VALUES (?, 'transport', 'metro', 10.0, 'km', 0.12, 'HIGH', ?);
            """,
            (user_id, day)
        )
    conn.commit()
    conn.close()

    changed = recalculate_baseline(user_id, "2026-06-21")
    assert changed

    # Verify defaults updated in users table
    conn = get_db_connection()
    row = conn.execute("SELECT default_commute, commute_fuel_type FROM users WHERE id = ?;", (user_id,)).fetchone()
    assert row["default_commute"] == "metro"
    assert row["commute_fuel_type"] is None  # metro doesn't carry a fuel type default

    # Verify baseline_history contains adaptive entry
    history = conn.execute(
        "SELECT * FROM baseline_history WHERE user_id = ? ORDER BY id DESC LIMIT 1;",
        (user_id,)
    ).fetchone()
    assert history["transport_mode"] == "metro"
    assert history["source"] == "adaptive"
    conn.close()


def test_baseline_adapts_diet_type() -> None:
    """Verify that baseline diet adapts when logged on >= 4 days."""
    user_id = "test-user-4"
    _create_test_user(user_id)

    # Log 4 vegetarian food events
    conn = get_db_connection()
    for day in ("2026-06-14", "2026-06-15", "2026-06-18", "2026-06-19"):
        conn.execute(
            """
            INSERT INTO events (user_id, category, subtype, value, unit, co2_kg, confidence, event_date)
            VALUES (?, 'food', 'vegetarian_day', 1.0, 'day', 0.724, 'HIGH', ?);
            """,
            (user_id, day)
        )
    conn.commit()
    conn.close()

    changed = recalculate_baseline(user_id, "2026-06-21")
    assert changed

    # Verify defaults updated in users table
    conn = get_db_connection()
    row = conn.execute("SELECT diet FROM users WHERE id = ?;", (user_id,)).fetchone()
    assert row["diet"] == "veg"
    conn.close()


def test_baseline_excludes_ac_adaptation() -> None:
    """Verify that AC configurations are explicitly excluded from adaptive baseline adjustments."""
    user_id = "test-user-5"
    _create_test_user(user_id)

    # Log 7 AC usage duration events (changing AC usage to 0 or no AC)
    conn = get_db_connection()
    for day in ("2026-06-14", "2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19", "2026-06-20"):
        conn.execute(
            """
            INSERT INTO events (user_id, category, subtype, value, unit, co2_kg, confidence, event_date)
            VALUES (?, 'energy', 'ac_usage', 0.0, 'hours', 0.0, 'HIGH', ?);
            """,
            (user_id, day)
        )
    conn.commit()
    conn.close()

    # Even with 7 days of 0 AC logs, baseline engine should not adapt AC
    changed = recalculate_baseline(user_id, "2026-06-21")
    assert not changed

    # Verify default AC remains 'yes'
    conn = get_db_connection()
    row = conn.execute("SELECT ac_usage FROM users WHERE id = ?;", (user_id,)).fetchone()
    assert row["ac_usage"] == "yes"
    conn.close()
