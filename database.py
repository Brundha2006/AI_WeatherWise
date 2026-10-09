# database.py
# Handles all database operations for the weather search history (SQLite)

import sqlite3
from datetime import datetime

DB_NAME = "weather.db"


def init_db():
    """Creates the database and all required tables if they don't already exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            temperature REAL,
            weather_condition TEXT,
            humidity INTEGER,
            wind_speed REAL,
            search_time TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            whatsapp_number TEXT NOT NULL,
            whatsapp_opt_in INTEGER DEFAULT 0,
            preferred_city TEXT,
            created_at TEXT
        )
    """)
    # Migration: add columns to a users table created by an older version of this app
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    if "whatsapp_opt_in" not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN whatsapp_opt_in INTEGER DEFAULT 0")
    if "preferred_city" not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN preferred_city TEXT")

    conn.commit()
    conn.close()


def add_search(city, temperature, weather_condition, humidity, wind_speed):
    """Saves one weather search into the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    search_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO history (city, temperature, weather_condition, humidity, wind_speed, search_time)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (city, temperature, weather_condition, humidity, wind_speed, search_time))
    conn.commit()
    conn.close()


def get_all_history():
    """Returns all past searches, most recent first."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT city, temperature, weather_condition, humidity, wind_speed, search_time FROM history ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


def clear_history():
    """Deletes all history records."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history")
    conn.commit()
    conn.close()


# ---------------- User account functions ----------------

def create_user(name, email, password_hash, whatsapp_number, whatsapp_opt_in, preferred_city):
    """Creates a new user account. Raises sqlite3.IntegrityError if the email is already used."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO users (name, email, password_hash, whatsapp_number, whatsapp_opt_in, preferred_city, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, email, password_hash, whatsapp_number, whatsapp_opt_in, preferred_city, created_at))
    conn.commit()
    conn.close()


def _row_to_user(row):
    if row is None:
        return None
    return {
        "id": row[0], "name": row[1], "email": row[2], "password_hash": row[3],
        "whatsapp_number": row[4], "whatsapp_opt_in": bool(row[5]), "preferred_city": row[6],
    }


USER_SELECT_COLUMNS = "id, name, email, password_hash, whatsapp_number, whatsapp_opt_in, preferred_city"


def get_user_by_email(email):
    """Returns a user as a dict, or None."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"SELECT {USER_SELECT_COLUMNS} FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_user(row)


def get_user_by_id(user_id):
    """Returns a user as a dict, or None."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"SELECT {USER_SELECT_COLUMNS} FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_user(row)


def get_opted_in_users():
    """Returns all users who agreed to receive WhatsApp updates and have a preferred city set."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT {USER_SELECT_COLUMNS} FROM users
        WHERE whatsapp_opt_in = 1 AND preferred_city IS NOT NULL AND preferred_city != ''
    """)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_user(r) for r in rows]
