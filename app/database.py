import sqlite3
from datetime import datetime

def init_db():
    """Initialize the SQLite database with all required tables."""
    conn = sqlite3.connect('drinks_tally.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            pin TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Drinks table - records each drink consumed
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drinks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            billing_period_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (billing_period_id) REFERENCES billing_periods (id)
        )
    ''')
    
    # Billing periods table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS billing_periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date TEXT NOT NULL,
            end_date TEXT,
            price_per_drink REAL NOT NULL,
            is_closed INTEGER DEFAULT 0,
            closed_at TEXT
        )
    ''')
    
    # Settings table for general configuration
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Check if default admin exists, if not create one
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (name, pin, is_admin) VALUES (?, ?, ?)",
            ("admin", "0000", 1)
        )
    
    # Check if there's an open billing period, if not create one
    cursor.execute("SELECT COUNT(*) FROM billing_periods WHERE is_closed = 0")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO billing_periods (start_date, price_per_drink) VALUES (?, ?)",
            (datetime.now().isoformat(), 1.0)
        )
    
    # Set default price if not exists
    cursor.execute("SELECT value FROM settings WHERE key = 'default_price'")
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("default_price", "1.0")
        )
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")
