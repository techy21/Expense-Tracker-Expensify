import os
import sqlite3
from datetime import date, datetime

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

DATE_RANGE_CONDITION = "AND (? IS NULL OR date >= ?) AND (? IS NULL OR date <= ?) "


def date_range_params(user_id, start_date, end_date):
    """Return parameters for "WHERE user_id = ?" followed by DATE_RANGE_CONDITION."""
    return (user_id, start_date, start_date, end_date, end_date)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_user_by_email(email):
    conn = get_db()
    user = conn.execute(
        "SELECT id, name, email, password_hash, created_at FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()
    return user


def create_user(name, email, password):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_profile(user_id):
    conn = get_db()
    user = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if user is None:
        return None
    return {
        "name": user["name"],
        "email": user["email"],
        "initials": "".join(word[0] for word in user["name"].split()[:2]).upper(),
        "member_since": datetime.fromisoformat(user["created_at"]).strftime("%B %Y"),
    }


def get_user_transactions(user_id, start_date=None, end_date=None):
    conn = get_db()
    rows = conn.execute(
        "SELECT date, description, category, amount FROM expenses "
        "WHERE user_id = ? " + DATE_RANGE_CONDITION + "ORDER BY date DESC, id DESC",
        date_range_params(user_id, start_date, end_date),
    ).fetchall()
    conn.close()
    return [
        {
            "date": date.fromisoformat(row["date"]).strftime("%d %b %Y"),
            "description": row["description"] or "",
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in rows
    ]


def get_user_categories(user_id, start_date=None, end_date=None):
    conn = get_db()
    rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? " + DATE_RANGE_CONDITION +
        "GROUP BY category ORDER BY total DESC, category ASC",
        date_range_params(user_id, start_date, end_date),
    ).fetchall()
    conn.close()
    overall = sum(row["total"] for row in rows)
    return [
        {
            "name": row["category"],
            "total": row["total"],
            "percent": round(row["total"] / overall * 100) if overall else 0,
        }
        for row in rows
    ]


def get_user_stats(user_id, start_date=None, end_date=None):
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE user_id = ? " + DATE_RANGE_CONDITION,
        date_range_params(user_id, start_date, end_date),
    ).fetchone()
    conn.close()
    categories = get_user_categories(user_id, start_date, end_date)
    return {
        "total_spent": row["total"],
        "transaction_count": row["count"],
        "top_category": categories[0]["name"] if categories else "—",
    }


def create_expense(user_id, amount, category, expense_date, description):
    """Insert one expense and return its new id."""
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, expense_date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      REAL NOT NULL,
            category    TEXT NOT NULL,
            date        TEXT NOT NULL,
            description TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        conn.close()
        return

    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@expensify.com", generate_password_hash("demo123")),
    )
    user_id = cursor.lastrowid

    today = date.today()

    def day(d):
        return today.replace(day=d).isoformat()

    expenses = [
        (user_id, 12.50, "Food", day(1), "Lunch"),
        (user_id, 25.00, "Transport", day(3), "Bus pass"),
        (user_id, 80.00, "Bills", day(5), "Electricity"),
        (user_id, 15.75, "Health", day(8), "Pharmacy"),
        (user_id, 30.00, "Entertainment", day(12), "Movie night"),
        (user_id, 49.99, "Shopping", day(15), "New shoes"),
        (user_id, 10.00, "Other", day(20), "Gift wrap"),
        (user_id, 42.30, "Food", day(25), "Groceries"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()
