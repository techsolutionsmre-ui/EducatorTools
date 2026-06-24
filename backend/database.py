import sqlite3
import os
import bcrypt
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
    
    # 3. Create default Administrator if it doesn't exist
    cursor.execute("SELECT id FROM users WHERE email = 'admin@educatortools.co.za'")
    admin = cursor.fetchone()
    if not admin:
        admin_hash = hash_password("AdminPassword123!") # Default secure fallback password
        cursor.execute(
            "INSERT INTO users (email, password_hash, profession, status) VALUES (?, ?, ?, ?)",
            ('admin@educatortools.co.za', admin_hash, 'Admin', 'active')
        )
        print("Default administrator created (admin@educatortools.co.za / AdminPassword123!)")
        
    conn.commit()
    conn.close()

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
def create_user(email: str, password_plain: str, profession: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        pw_hash = hash_password(password_plain)
        cursor.execute(
            "INSERT INTO users (email, password_hash, profession, status) VALUES (?, ?, ?, ?)",
            (email.strip().lower(), pw_hash, profession, 'trial')
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
