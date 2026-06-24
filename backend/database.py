import sqlite3
import os
import bcrypt
from datetime import datetime, timedelta
import config

def get_db_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        profession TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'trial',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    _ensure_column(cursor, "users", "email_verified", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(cursor, "users", "verification_code_hash", "TEXT")
    _ensure_column(cursor, "users", "verification_expires_at", "TIMESTAMP")
    
    # 2. Create conversions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        page_count INTEGER NOT NULL,
        file_size INTEGER NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)
    
    # 3. Ensure the configured administrator exists and the legacy default is removed.
    cursor.execute("SELECT id FROM users WHERE email = ?", (config.ADMIN_EMAIL,))
    admin = cursor.fetchone()
    admin_hash = hash_password(config.ADMIN_PASSWORD)
    if not admin:
        cursor.execute(
            "INSERT INTO users (email, password_hash, profession, status, email_verified) VALUES (?, ?, ?, ?, ?)",
            (config.ADMIN_EMAIL, admin_hash, 'Admin', 'active', 1)
        )
        print(f"Default administrator created ({config.ADMIN_EMAIL})")
    else:
        cursor.execute(
            """
            UPDATE users
            SET password_hash = ?, profession = 'Admin', status = 'active', email_verified = 1,
                verification_code_hash = NULL, verification_expires_at = NULL
            WHERE email = ?
            """,
            (admin_hash, config.ADMIN_EMAIL)
        )

    cursor.execute(
        "DELETE FROM users WHERE email = ? AND profession = 'Admin'",
        ("admin@educatortools.co.za",)
    )
        
    conn.commit()
    conn.close()

def _ensure_column(cursor, table: str, column: str, definition: str):
    cursor.execute(f"PRAGMA table_info({table})")
    existing_columns = {row["name"] for row in cursor.fetchall()}
    if column not in existing_columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

# Password Helpers
def hash_password(password: str) -> str:
    # Hash password using bcrypt
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Verify password using bcrypt
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

# User Helpers
def create_user(email: str, password_plain: str, profession: str, verification_code: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        pw_hash = hash_password(password_plain)
        verification_hash = hash_password(verification_code)
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        cursor.execute(
            """
            INSERT INTO users (
                email, password_hash, profession, status, email_verified,
                verification_code_hash, verification_expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (email.strip().lower(), pw_hash, profession, 'trial', 0, verification_hash, expires_at.isoformat())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user_by_email(email: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def list_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, profession, status, created_at FROM users WHERE profession != 'Admin' ORDER BY created_at DESC")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def update_user_status(user_id: int, status: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
    conn.commit()
    rows_changed = cursor.rowcount > 0
    conn.close()
    return rows_changed

def set_verification_code(email: str, code: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    verification_hash = hash_password(code)
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    cursor.execute(
        """
        UPDATE users
        SET verification_code_hash = ?, verification_expires_at = ?
        WHERE email = ? AND email_verified = 0
        """,
        (verification_hash, expires_at.isoformat(), email.strip().lower())
    )
    conn.commit()
    rows_changed = cursor.rowcount > 0
    conn.close()
    return rows_changed

def verify_email_code(email: str, code: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, verification_code_hash, verification_expires_at FROM users WHERE email = ?",
        (email.strip().lower(),)
    )
    user = cursor.fetchone()
    if not user or not user["verification_code_hash"] or not user["verification_expires_at"]:
        conn.close()
        return False

    try:
        expires_at = datetime.fromisoformat(user["verification_expires_at"])
    except ValueError:
        conn.close()
        return False

    if expires_at < datetime.utcnow() or not verify_password(code, user["verification_code_hash"]):
        conn.close()
        return False

    cursor.execute(
        """
        UPDATE users
        SET email_verified = 1, verification_code_hash = NULL, verification_expires_at = NULL
        WHERE id = ?
        """,
        (user["id"],)
    )
    conn.commit()
    conn.close()
    return True

# Conversion Helpers
def add_conversion(user_id: int, filename: str, page_count: int, file_size: int, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversions (user_id, filename, page_count, file_size, status) VALUES (?, ?, ?, ?, ?)",
        (user_id, filename, page_count, file_size, status)
    )
    conn.commit()
    conn.close()

def get_user_conversions(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conversions WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_user_monthly_usage(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COALESCE(SUM(page_count), 0) AS page_count
        FROM conversions
        WHERE user_id = ?
          AND status = 'success'
          AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
        """,
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return {
        "page_count": row["page_count"] if row else 0,
    }
