import os
import sqlite3

DB_PATH = os.getenv(
    "DATABASE_PATH",
    os.path.abspath(
        os.path.join(
            os.path.dirname(
                os.path.dirname(__file__)),
            "carbontread.db")
    )
)


def get_db_connection() -> sqlite3.Connection:
    """Connect to SQLite database and enforce foreign key constraints."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Create database tables if they do not already exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        city TEXT NOT NULL,
        default_commute TEXT NOT NULL,
        commute_fuel_type TEXT,
        default_distance REAL NOT NULL,
        diet TEXT NOT NULL,
        ac_usage TEXT NOT NULL,
        cooking_fuel TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create baseline_history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS baseline_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        week_start_date TEXT NOT NULL,
        transport_mode TEXT NOT NULL,
        transport_fuel_type TEXT,
        food_pattern TEXT NOT NULL,
        ac_usage TEXT NOT NULL,
        source TEXT CHECK(source IN ('onboarding', 'adaptive')) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Create events table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        category TEXT NOT NULL,
        subtype TEXT NOT NULL,
        value REAL NOT NULL,
        unit TEXT NOT NULL,
        co2_kg REAL,
        confidence TEXT CHECK(confidence IN ('HIGH', 'MEDIUM', 'LOW')) NOT NULL,
        counterfactual_alt TEXT,
        counterfactual_co2_kg REAL,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        event_date TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Create suggestions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        suggestion_text TEXT NOT NULL,
        category TEXT NOT NULL,
        co2_saved_kg REAL NOT NULL,
        difficulty TEXT CHECK(difficulty IN ('easy', 'medium', 'hard')) NOT NULL,
        reasoning TEXT NOT NULL,
        shown_date TEXT NOT NULL,
        user_response TEXT CHECK(user_response IN ('I''ll do it', 'Not possible today', 'Pending')) DEFAULT 'Pending',
        acted_on INTEGER CHECK(acted_on IN (0, 1)) DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Create weekly_narratives table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weekly_narratives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        week_start_date TEXT NOT NULL,
        narrative_text TEXT NOT NULL,
        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()
