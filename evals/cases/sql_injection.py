import sqlite3


def find_user(db_path: str, username: str):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, email FROM users WHERE username = '{username}'")
        return cursor.fetchone()
    finally:
        conn.close()
