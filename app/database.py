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
            role TEXT DEFAULT 'user',
            custom_price_per_drink REAL DEFAULT NULL,
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
    
    # Adjustment log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS adjustment_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            billing_period_id INTEGER NOT NULL,
            adjustment_amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            admin_user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (billing_period_id) REFERENCES billing_periods (id),
            FOREIGN KEY (admin_user_id) REFERENCES users (id)
        )
    ''')
    
    # CSRF tokens table for security
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS csrf_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Check if default admin exists, if not create one
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (name, pin, is_admin, role) VALUES (?, ?, ?, ?)",
            ("admin", "0000", 1, "admin")
        )
    
    # Migrate existing users to have role field if needed
    cursor.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1 AND (role IS NULL OR role = '')")
    cursor.execute("UPDATE users SET role = 'user' WHERE is_admin = 0 AND (role IS NULL OR role = '')")
    
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
