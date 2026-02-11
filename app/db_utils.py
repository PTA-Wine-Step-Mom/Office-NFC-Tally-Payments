import sqlite3
import secrets
from functools import wraps
from datetime import datetime, timedelta
from flask import g, session, redirect, url_for, request, abort

DATABASE = 'drinks_tally.db'

def get_db():
    """Get database connection, reuse if exists in Flask's g object."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def query_db(query, args=(), one=False):
    """Execute a query and return results."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    """Execute a query that modifies the database."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id

def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        
        user = query_db('SELECT is_admin, role FROM users WHERE id = ?', 
                       [session['user_id']], one=True)
        # Check both is_admin (legacy) and role (new) fields
        if not user or (not user['is_admin'] and user.get('role') != 'admin'):
            return "Unauthorized", 403
        
        return f(*args, **kwargs)
    return decorated_function

def generate_csrf_token():
    """Generate a CSRF token for the current user session.
    
    Uses 32 bytes (256 bits of entropy) which exceeds OWASP's 
    recommendation of 128 bits for CSRF token security.
    """
    if 'user_id' not in session:
        return None
    
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(hours=1)).isoformat()
    
    # Clean up expired tokens
    execute_db('DELETE FROM csrf_tokens WHERE expires_at < ?', [datetime.now().isoformat()])
    
    # Store new token
    execute_db('INSERT INTO csrf_tokens (token, user_id, expires_at) VALUES (?, ?, ?)',
              [token, session['user_id'], expires_at])
    
    return token

def verify_csrf_token(token):
    """Verify a CSRF token."""
    if 'user_id' not in session or not token:
        return False
    
    # Check if token exists and is valid
    result = query_db(
        'SELECT * FROM csrf_tokens WHERE token = ? AND user_id = ? AND expires_at > ?',
        [token, session['user_id'], datetime.now().isoformat()],
        one=True
    )
    
    if result:
        # Delete used token (one-time use)
        execute_db('DELETE FROM csrf_tokens WHERE token = ?', [token])
        return True
    
    return False

def csrf_protect(f):
    """Decorator to protect routes with CSRF tokens."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            token = request.form.get('csrf_token')
            if not verify_csrf_token(token):
                abort(403, "Invalid or expired CSRF token")
        return f(*args, **kwargs)
    return decorated_function
