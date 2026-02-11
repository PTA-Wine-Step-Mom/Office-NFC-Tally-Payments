import os
import secrets
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, g
from db_utils import get_db, query_db, execute_db, login_required, admin_required

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Long-lived cookie

@app.teardown_appcontext
def close_connection(exception):
    """Close database connection at the end of each request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    """Home page - show statistics or redirect to tap page."""
    if 'user_id' in session:
        user = query_db('SELECT * FROM users WHERE id = ?', [session['user_id']], one=True)
        
        # Get current billing period
        billing_period = query_db(
            'SELECT * FROM billing_periods WHERE is_closed = 0 ORDER BY id DESC LIMIT 1',
            one=True
        )
        
        if user and billing_period:
            # Get user's drink count for current period
            drink_count = query_db(
                'SELECT COUNT(*) as count FROM drinks WHERE user_id = ? AND billing_period_id = ?',
                [user['id'], billing_period['id']], one=True
            )['count']
            
            total_cost = drink_count * billing_period['price_per_drink']
            
            return render_template('index.html', 
                                 user=user, 
                                 drink_count=drink_count,
                                 total_cost=total_cost,
                                 price_per_drink=billing_period['price_per_drink'])
    
    return render_template('index.html', user=None)

@app.route('/tap', methods=['GET', 'POST'])
def tap():
    """NFC tap endpoint - increment drink or show login."""
    if request.method == 'GET':
        # Check if user is logged in
        if 'user_id' in session:
            # User is logged in, show quick tap page
            user = query_db('SELECT * FROM users WHERE id = ?', [session['user_id']], one=True)
            return render_template('tap_logged_in.html', user=user)
        else:
            # User not logged in, show user selection and PIN
            users = query_db('SELECT id, name FROM users WHERE is_admin = 0 ORDER BY name')
            return render_template('tap_login.html', users=users)
    
    # POST request - handle tap action
    if 'user_id' in session:
        # Logged in user - instant increment
        user_id = session['user_id']
    else:
        # Not logged in - validate PIN
        user_id = request.form.get('user_id')
        pin = request.form.get('pin')
        remember = request.form.get('remember_me') == 'on'
        
        if not user_id or not pin:
            flash('Please select a user and enter PIN', 'error')
            return redirect(url_for('tap'))
        
        # Validate user and PIN
        user = query_db('SELECT * FROM users WHERE id = ? AND pin = ?', 
                       [user_id, pin], one=True)
        
        if not user:
            flash('Invalid PIN', 'error')
            return redirect(url_for('tap'))
        
        # Set session if remember me is checked
        if remember:
            session['user_id'] = user['id']
            session.permanent = True
    
    # Get current billing period
    billing_period = query_db(
        'SELECT * FROM billing_periods WHERE is_closed = 0 ORDER BY id DESC LIMIT 1',
        one=True
    )
    
    if not billing_period:
        flash('No active billing period. Please contact admin.', 'error')
        return redirect(url_for('index'))
    
    # Record the drink
    execute_db(
        'INSERT INTO drinks (user_id, billing_period_id) VALUES (?, ?)',
        [user_id, billing_period['id']]
    )
    
    # Get updated count
    drink_count = query_db(
        'SELECT COUNT(*) as count FROM drinks WHERE user_id = ? AND billing_period_id = ?',
        [user_id, billing_period['id']], one=True
    )['count']
    
    user = query_db('SELECT name FROM users WHERE id = ?', [user_id], one=True)
    
    return render_template('tap_success.html', 
                         user=user, 
                         drink_count=drink_count,
                         total_cost=drink_count * billing_period['price_per_drink'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page."""
    if request.method == 'POST':
        name = request.form.get('name')
        pin = request.form.get('pin')
        remember = request.form.get('remember_me') == 'on'
        
        user = query_db('SELECT * FROM users WHERE name = ? AND pin = ?', 
                       [name, pin], one=True)
        
        if user:
            session['user_id'] = user['id']
            if remember:
                session.permanent = True
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout current user."""
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard."""
    users = query_db('SELECT * FROM users WHERE is_admin = 0 ORDER BY name')
    billing_period = query_db(
        'SELECT * FROM billing_periods WHERE is_closed = 0 ORDER BY id DESC LIMIT 1',
        one=True
    )
    
    # Get drink statistics for current period
    if billing_period:
        stats = query_db('''
            SELECT u.name, COUNT(d.id) as drink_count, 
                   COUNT(d.id) * ? as total_cost
            FROM users u
            LEFT JOIN drinks d ON u.id = d.user_id AND d.billing_period_id = ?
            WHERE u.is_admin = 0
            GROUP BY u.id, u.name
            ORDER BY drink_count DESC
        ''', [billing_period['price_per_drink'], billing_period['id']])
        
        total_drinks = sum(s['drink_count'] for s in stats)
        total_revenue = sum(s['total_cost'] for s in stats)
    else:
        stats = []
        total_drinks = 0
        total_revenue = 0
    
    return render_template('admin_dashboard.html', 
                         users=users,
                         billing_period=billing_period,
                         stats=stats,
                         total_drinks=total_drinks,
                         total_revenue=total_revenue)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    """Add a new user."""
    if request.method == 'POST':
        name = request.form.get('name')
        pin = request.form.get('pin')
        is_admin = 1 if request.form.get('is_admin') == 'on' else 0
        
        if not name or not pin:
            flash('Name and PIN are required', 'error')
        else:
            try:
                execute_db('INSERT INTO users (name, pin, is_admin) VALUES (?, ?, ?)',
                          [name, pin, is_admin])
                flash(f'User {name} added successfully', 'success')
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                flash(f'Error adding user: {str(e)}', 'error')
    
    return render_template('add_user.html')

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit an existing user."""
    user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        pin = request.form.get('pin')
        
        if not name or not pin:
            flash('Name and PIN are required', 'error')
        else:
            try:
                execute_db('UPDATE users SET name = ?, pin = ? WHERE id = ?',
                          [name, pin, user_id])
                flash(f'User {name} updated successfully', 'success')
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                flash(f'Error updating user: {str(e)}', 'error')
    
    return render_template('edit_user.html', user=user)

@app.route('/admin/billing/close', methods=['POST'])
@admin_required
def close_billing_period():
    """Close current billing period and create a new one."""
    # Get current open period
    current_period = query_db(
        'SELECT * FROM billing_periods WHERE is_closed = 0 ORDER BY id DESC LIMIT 1',
        one=True
    )
    
    if not current_period:
        flash('No open billing period found', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # Close current period
    execute_db(
        'UPDATE billing_periods SET is_closed = 1, end_date = ?, closed_at = ? WHERE id = ?',
        [datetime.now().isoformat(), datetime.now().isoformat(), current_period['id']]
    )
    
    # Create new period with same price
    price = request.form.get('price', current_period['price_per_drink'])
    execute_db(
        'INSERT INTO billing_periods (start_date, price_per_drink) VALUES (?, ?)',
        [datetime.now().isoformat(), price]
    )
    
    flash('Billing period closed successfully. New period started.', 'success')
    return redirect(url_for('billing_report', period_id=current_period['id']))

@app.route('/admin/billing/report/<int:period_id>')
@admin_required
def billing_report(period_id):
    """Show detailed report for a closed billing period."""
    period = query_db('SELECT * FROM billing_periods WHERE id = ?', [period_id], one=True)
    
    if not period:
        flash('Billing period not found', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # Get per-user totals
    user_totals = query_db('''
        SELECT u.name, COUNT(d.id) as drink_count, 
               COUNT(d.id) * ? as total_cost
        FROM users u
        LEFT JOIN drinks d ON u.id = d.user_id AND d.billing_period_id = ?
        WHERE u.is_admin = 0
        GROUP BY u.id, u.name
        HAVING drink_count > 0
        ORDER BY u.name
    ''', [period['price_per_drink'], period_id])
    
    total_drinks = sum(u['drink_count'] for u in user_totals)
    total_revenue = sum(u['total_cost'] for u in user_totals)
    
    return render_template('billing_report.html',
                         period=period,
                         user_totals=user_totals,
                         total_drinks=total_drinks,
                         total_revenue=total_revenue)

@app.route('/admin/billing/history')
@admin_required
def billing_history():
    """Show all billing periods."""
    periods = query_db('SELECT * FROM billing_periods ORDER BY id DESC')
    return render_template('billing_history.html', periods=periods)

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    """Admin settings page."""
    if request.method == 'POST':
        price = request.form.get('default_price')
        
        if price:
            try:
                execute_db('UPDATE settings SET value = ? WHERE key = ?',
                          [price, 'default_price'])
                
                # Update current billing period price
                execute_db(
                    'UPDATE billing_periods SET price_per_drink = ? WHERE is_closed = 0',
                    [price]
                )
                
                flash('Settings updated successfully', 'success')
            except Exception as e:
                flash(f'Error updating settings: {str(e)}', 'error')
        
        return redirect(url_for('admin_settings'))
    
    default_price = query_db('SELECT value FROM settings WHERE key = ?', 
                            ['default_price'], one=True)
    
    return render_template('admin_settings.html', 
                         default_price=default_price['value'] if default_price else '1.0')

if __name__ == '__main__':
    # Initialize database on first run
    from database import init_db
    init_db()
    
    # Run the app
    app.run(host='0.0.0.0', port=5000, debug=False)
