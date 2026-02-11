import os
import secrets
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, g
from db_utils import get_db, query_db, execute_db, login_required, admin_required, generate_csrf_token, csrf_protect

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Long-lived cookie

@app.template_filter('format_date')
def format_date(iso_string):
    """Format ISO date string to YYYY-MM-DD."""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except:
        return iso_string[:10]  # Fallback to slice

@app.template_filter('format_datetime')
def format_datetime(iso_string):
    """Format ISO datetime string to YYYY-MM-DD HH:MM."""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return iso_string[:16]  # Fallback to slice

@app.teardown_appcontext
def close_connection(exception):
    """Close database connection at the end of each request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.context_processor
def inject_csrf_token():
    """Make CSRF token available to all templates."""
    return dict(csrf_token=generate_csrf_token)

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
            
            # Use custom price if set, otherwise use billing period price
            price = user['custom_price_per_drink'] if user['custom_price_per_drink'] is not None else billing_period['price_per_drink']
            total_cost = drink_count * price
            
            return render_template('index.html', 
                                 user=user, 
                                 drink_count=drink_count,
                                 total_cost=total_cost,
                                 price_per_drink=price)
    
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
    
    user = query_db('SELECT name, custom_price_per_drink FROM users WHERE id = ?', [user_id], one=True)
    
    # Use custom price if set, otherwise use billing period price
    price = user['custom_price_per_drink'] if user['custom_price_per_drink'] is not None else billing_period['price_per_drink']
    
    return render_template('tap_success.html', 
                         user=user, 
                         drink_count=drink_count,
                         total_cost=drink_count * price)

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
    users = query_db('SELECT * FROM users WHERE role = "user" ORDER BY name')
    billing_period = query_db(
        'SELECT * FROM billing_periods WHERE is_closed = 0 ORDER BY id DESC LIMIT 1',
        one=True
    )
    
    # Get drink statistics for current period
    if billing_period:
        stats = []
        total_drinks = 0
        total_revenue = 0
        
        for user in users:
            drink_count = query_db(
                'SELECT COUNT(*) as count FROM drinks WHERE user_id = ? AND billing_period_id = ?',
                [user['id'], billing_period['id']], one=True
            )['count']
            
            # Use custom price if set, otherwise use billing period price
            price = user['custom_price_per_drink'] if user['custom_price_per_drink'] is not None else billing_period['price_per_drink']
            total_cost = drink_count * price
            
            stats.append({
                'name': user['name'],
                'drink_count': drink_count,
                'total_cost': total_cost
            })
            
            total_drinks += drink_count
            total_revenue += total_cost
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
@csrf_protect
def add_user():
    """Add a new user."""
    if request.method == 'POST':
        name = request.form.get('name')
        pin = request.form.get('pin')
        is_admin = 1 if request.form.get('is_admin') == 'on' else 0
        role = 'admin' if is_admin else 'user'
        
        if not name or not pin:
            flash('Name and PIN are required', 'error')
        else:
            try:
                execute_db('INSERT INTO users (name, pin, is_admin, role) VALUES (?, ?, ?, ?)',
                          [name, pin, is_admin, role])
                flash(f'User {name} added successfully', 'success')
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                flash(f'Error adding user: {str(e)}', 'error')
    
    return render_template('add_user.html')

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
@csrf_protect
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
@csrf_protect
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
    
    # Get all users
    users = query_db('SELECT * FROM users WHERE role = "user"')
    
    # Get per-user totals with custom pricing
    user_totals = []
    total_drinks = 0
    total_revenue = 0
    
    for user in users:
        drink_count = query_db(
            'SELECT COUNT(*) as count FROM drinks WHERE user_id = ? AND billing_period_id = ?',
            [user['id'], period_id], one=True
        )['count']
        
        if drink_count > 0:
            # Use custom price if set, otherwise use billing period price
            price = user['custom_price_per_drink'] if user['custom_price_per_drink'] is not None else period['price_per_drink']
            total_cost = drink_count * price
            
            user_totals.append({
                'name': user['name'],
                'drink_count': drink_count,
                'total_cost': total_cost
            })
            
            total_drinks += drink_count
            total_revenue += total_cost
    
    # Sort by name
    user_totals.sort(key=lambda x: x['name'])
    
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
@csrf_protect
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

@app.route('/admin/users/<int:user_id>/reset-pin', methods=['POST'])
@admin_required
@csrf_protect
def reset_user_pin(user_id):
    """Reset a user's PIN."""
    user = query_db('SELECT name FROM users WHERE id = ?', [user_id], one=True)
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('user_management'))
    
    new_pin = request.form.get('new_pin')
    
    if not new_pin or len(new_pin) < 4:
        flash('PIN must be at least 4 digits', 'error')
        return redirect(url_for('user_management'))
    
    try:
        execute_db('UPDATE users SET pin = ? WHERE id = ?', [new_pin, user_id])
        flash(f"PIN reset successfully for {user['name']}", 'success')
    except Exception as e:
        flash(f'Error resetting PIN: {str(e)}', 'error')
    
    return redirect(url_for('user_management'))

@app.route('/admin/users/<int:user_id>/adjust-drinks', methods=['POST'])
@admin_required
@csrf_protect
def adjust_user_drinks(user_id):
    """Adjust a user's drink count for the current billing period."""
    user = query_db('SELECT name FROM users WHERE id = ?', [user_id], one=True)
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('user_management'))
    
    # Get current billing period
    billing_period = query_db(
        'SELECT * FROM billing_periods WHERE is_closed = 0 ORDER BY id DESC LIMIT 1',
        one=True
    )
    
    if not billing_period:
        flash('No active billing period', 'error')
        return redirect(url_for('user_management'))
    
    adjustment = request.form.get('adjustment')
    reason = request.form.get('reason')
    
    if not adjustment or not reason:
        flash('Adjustment amount and reason are required', 'error')
        return redirect(url_for('user_management'))
    
    try:
        adjustment = int(adjustment)
    except ValueError:
        flash('Adjustment must be a number', 'error')
        return redirect(url_for('user_management'))
    
    try:
        # Log the adjustment
        execute_db(
            'INSERT INTO adjustment_log (user_id, billing_period_id, adjustment_amount, reason, admin_user_id) VALUES (?, ?, ?, ?, ?)',
            [user_id, billing_period['id'], adjustment, reason, session['user_id']]
        )
        
        # Apply the adjustment
        if adjustment > 0:
            # Add drinks
            for _ in range(adjustment):
                execute_db(
                    'INSERT INTO drinks (user_id, billing_period_id) VALUES (?, ?)',
                    [user_id, billing_period['id']]
                )
        else:
            # Remove drinks
            drinks_to_remove = abs(adjustment)
            drink_ids = query_db(
                'SELECT id FROM drinks WHERE user_id = ? AND billing_period_id = ? ORDER BY id DESC LIMIT ?',
                [user_id, billing_period['id'], drinks_to_remove]
            )
            for drink in drink_ids:
                execute_db('DELETE FROM drinks WHERE id = ?', [drink['id']])
        
        flash(f"Adjusted drink count by {adjustment:+d} for {user['name']}", 'success')
    except Exception as e:
        flash(f'Error adjusting drinks: {str(e)}', 'error')
    
    return redirect(url_for('user_management'))

@app.route('/admin/users/<int:user_id>/set-price', methods=['POST'])
@admin_required
@csrf_protect
def set_user_price(user_id):
    """Set a custom price per drink for a specific user."""
    user = query_db('SELECT name FROM users WHERE id = ?', [user_id], one=True)
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('user_management'))
    
    custom_price = request.form.get('custom_price')
    
    # If custom_price is empty or "default", set to NULL (use global price)
    if not custom_price or custom_price.lower() == 'default':
        try:
            execute_db('UPDATE users SET custom_price_per_drink = NULL WHERE id = ?', [user_id])
            flash(f"Reset {user['name']} to use global pricing", 'success')
        except Exception as e:
            flash(f'Error updating price: {str(e)}', 'error')
    else:
        try:
            price = float(custom_price)
            if price < 0:
                flash('Price cannot be negative', 'error')
                return redirect(url_for('user_management'))
            
            execute_db('UPDATE users SET custom_price_per_drink = ? WHERE id = ?', [price, user_id])
            flash(f"Set custom price ${price:.2f} for {user['name']}", 'success')
        except ValueError:
            flash('Invalid price format', 'error')
        except Exception as e:
            flash(f'Error updating price: {str(e)}', 'error')
    
    return redirect(url_for('user_management'))

@app.route('/admin/users/manage')
@admin_required
def user_management():
    """User management page with all admin functions."""
    users = query_db('SELECT * FROM users WHERE role = "user" ORDER BY name')
    
    # Get current billing period
    billing_period = query_db(
        'SELECT * FROM billing_periods WHERE is_closed = 0 ORDER BY id DESC LIMIT 1',
        one=True
    )
    
    # Get drink counts and adjustments for each user
    user_stats = []
    for user in users:
        drink_count = 0
        adjustments = []
        
        if billing_period:
            drink_count = query_db(
                'SELECT COUNT(*) as count FROM drinks WHERE user_id = ? AND billing_period_id = ?',
                [user['id'], billing_period['id']], one=True
            )['count']
            
            # Get adjustment history for current period
            adjustments = query_db(
                '''SELECT a.*, u.name as admin_name 
                   FROM adjustment_log a 
                   JOIN users u ON a.admin_user_id = u.id 
                   WHERE a.user_id = ? AND a.billing_period_id = ? 
                   ORDER BY a.created_at DESC''',
                [user['id'], billing_period['id']]
            )
        
        # Calculate price
        price = user['custom_price_per_drink'] if user['custom_price_per_drink'] is not None else (billing_period['price_per_drink'] if billing_period else 0)
        
        user_stats.append({
            'user': user,
            'drink_count': drink_count,
            'total_cost': drink_count * price,
            'price': price,
            'adjustments': adjustments
        })
    
    # Get global price setting
    default_price = query_db('SELECT value FROM settings WHERE key = ?', 
                            ['default_price'], one=True)
    
    return render_template('user_management.html', 
                         user_stats=user_stats,
                         billing_period=billing_period,
                         default_price=default_price['value'] if default_price else '1.0')

if __name__ == '__main__':
    # Initialize database on first run
    from database import init_db
    init_db()
    
    # Run the app
    app.run(host='0.0.0.0', port=5000, debug=False)
