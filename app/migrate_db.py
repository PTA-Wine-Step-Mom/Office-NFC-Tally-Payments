"""
Database migration script for Admin User Management System
This adds:
- role field to users table (replacing is_admin)
- adjustment_log table
- custom_price_per_drink field to users table
"""
import sqlite3
from datetime import datetime

DATABASE = 'drinks_tally.db'

def migrate_db():
    """Run database migrations."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    print("Starting database migration...")
    
    # Check if role column already exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'role' not in columns:
        print("Adding 'role' column to users table...")
        # Add role column (default: 'user', admins will be 'admin')
        cursor.execute('ALTER TABLE users ADD COLUMN role TEXT DEFAULT "user"')
        
        # Migrate existing is_admin values to role
        cursor.execute('UPDATE users SET role = "admin" WHERE is_admin = 1')
        cursor.execute('UPDATE users SET role = "user" WHERE is_admin = 0')
        
        print("✓ Role column added and data migrated")
    else:
        print("✓ Role column already exists")
    
    if 'custom_price_per_drink' not in columns:
        print("Adding 'custom_price_per_drink' column to users table...")
        cursor.execute('ALTER TABLE users ADD COLUMN custom_price_per_drink REAL DEFAULT NULL')
        print("✓ Custom price column added")
    else:
        print("✓ Custom price column already exists")
    
    # Create adjustment_log table
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
    print("✓ Adjustment log table created")
    
    # Create csrf_tokens table for CSRF protection
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS csrf_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    print("✓ CSRF tokens table created")
    
    conn.commit()
    conn.close()
    print("Database migration completed successfully!")

if __name__ == '__main__':
    migrate_db()
