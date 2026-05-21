from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from datetime import datetime, timedelta
from bson.objectid import ObjectId

from pymongo import MongoClient, ASCENDING, DESCENDING
from flask_bcrypt import Bcrypt

from .config import Config
from .models.user import User
from .routes.products import bp as products_bp
from .routes.suppliers import bp as suppliers_bp
from .routes.purchases import bp as purchases_bp
from .routes.pos import bp as pos_bp
from .routes.sales import bp as sales_bp
from .routes.clients import bp as clients_bp
from .routes.payments import bp as payments_bp
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


app = Flask(
    __name__,
    template_folder='../frontend/templates',
    static_folder='../frontend/static'
)

app.config.from_object(Config)
app.secret_key = app.config['SECRET_KEY']

# ── Session config — stay logged in for 24 hours ──────────────────────────────
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_SAMESITE']    = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY']    = True  # prevent JS access to cookie

bcrypt = Bcrypt(app)
mongo_client = MongoClient(
    app.config["MONGODB_URI"],
    maxPoolSize=10,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=10000,
)
db = mongo_client.stockflow
app.db = db

# ── Rate limiter ───────────────────────────────────────────────────────────────
# Default: 200 requests/day, 50/hour for all routes.
# Sensitive routes get tighter per-route limits defined below.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    # Store state in memory (switch to Redis in production for multi-worker support)
    # storage_uri="redis://localhost:6379"
)

# ── Create indexes on startup for fast queries ────────────────────────────────
def create_indexes():
    try:
        db.sales.create_index([("business_id", ASCENDING), ("date", DESCENDING)])
        db.products.create_index([("business_id", ASCENDING)])
        db.purchases.create_index([("business_id", ASCENDING), ("date", DESCENDING)])
        db.clients.create_index([("business_id", ASCENDING)])
        db.users.create_index([("business_id", ASCENDING)])
        db.suppliers.create_index([("business_id", ASCENDING)])
    except Exception:
        pass  # Don't crash if indexes already exist


with app.app_context():
    create_indexes()

app.register_blueprint(products_bp)
app.register_blueprint(suppliers_bp)
app.register_blueprint(purchases_bp)
app.register_blueprint(pos_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(clients_bp)
app.register_blueprint(payments_bp)


def get_business_query():
    if session.get('role') == 'super_admin':
        return {}
    business_id = session.get('business_id')
    if business_id:
        try:
            return {"business_id": ObjectId(business_id)}
        except Exception:
            return {}
    return {}


@app.route('/health')
def health():
    return 'OK', 200


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


# ── Login: 10 attempts/minute per IP to slow brute-force attacks ──────────────
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    # Already logged in — go straight to dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = db.users.find_one({"username": username})
        if user and bcrypt.check_password_hash(user['password_hash'], password):
            session.permanent = True   # persist for 24 hours
            session['user_id']     = str(user['_id'])
            session['username']    = user['username']
            session['role']        = user['role']
            session['business_id'] = str(user['business_id']) if user.get('business_id') else None

            if user.get('business_id'):
                business = db.businesses.find_one({"_id": ObjectId(user['business_id'])})
                session['business_name'] = business['name'] if business else "Unknown Business"
            else:
                session['business_name'] = "All Businesses (Super Admin)"

            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid username or password', 'error')

    return render_template('login.html')


# ── Signup: 5 attempts/hour — one-time setup route, no need to hammer it ──────
@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"])
def signup():
    if db.users.count_documents({}) > 0:
        flash('Signup is disabled. New users must be created by an administrator.', 'info')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        if not username or not password:
            flash('Username and password are required', 'danger')
            return render_template('signup.html')

        if db.users.find_one({"username": username}):
            flash('Username already exists', 'danger')
            return render_template('signup.html')

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        db.users.insert_one({
            "username":      username,
            "password_hash": hashed,
            "role":          "super_admin",
            "created_at":    datetime.utcnow()
        })

        flash('Initial super admin account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_role = session.get('role')

    # ── Super admin dashboard ─────────────────────────────────────────────────
    if user_role == 'super_admin':
        total_businesses = db.businesses.count_documents({})
        total_users      = db.users.count_documents({})

        all_users = list(db.users.find({}, {
            "username": 1, "role": 1, "business_id": 1, "created_at": 1
        }).sort("created_at", DESCENDING).limit(50))

        # Batch fetch all businesses in one query instead of one per user
        all_biz = {str(b['_id']): b['name'] for b in db.businesses.find({}, {"name": 1})}

        users_with_business = []
        for user in all_users:
            business_name = "—"
            if user.get('business_id'):
                business_name = all_biz.get(str(user['business_id']), 'Deleted')
            users_with_business.append({
                "username": user.get('username', 'Unknown'),
                "role":     user.get('role', 'Unknown'),
                "business": business_name,
                "created":  user.get('created_at', datetime.utcnow()).strftime('%b %d, %Y')
            })

        all_businesses = list(db.businesses.find().sort("created_at", DESCENDING))

        return render_template('dashboard.html',
                               is_super_admin=True,
                               total_businesses=total_businesses,
                               total_users=total_users,
                               users=users_with_business,
                               businesses=all_businesses,
                               business_name="System Control Panel")

    # ── Branch dashboard ──────────────────────────────────────────────────────
    query = get_business_query()

    # Fetch products once with only needed fields
    products = list(db.products.find(query, {
        "current_quantity": 1, "min_stock": 1,
        "purchase_price": 1, "selling_price": 1
    }))

    total_products  = len(products)
    low_stock_count = sum(
        1 for p in products
        if p.get('current_quantity', 0) < p.get('min_stock', 10)
    )

    now         = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    year_start  = today_start.replace(month=1, day=1)

    # Fetch only this year's sales with only needed fields
    sales_query = {**query, "date": {"$gte": year_start}}
    all_sales   = list(db.sales.find(sales_query, {
        "date": 1, "total_amount": 1,
        "items": 1, "client_id": 1, "payment_method": 1
    }))

    daily_sales   = 0.0
    weekly_sales  = 0.0
    monthly_sales = 0.0
    yearly_sales  = 0.0
    today_sales   = []

    for s in all_sales:
        amt = s.get('total_amount', 0.0)
        yearly_sales += amt
        if s['date'] >= month_start:
            monthly_sales += amt
        if s['date'] >= week_start:
            weekly_sales += amt
        if s['date'] >= today_start:
            daily_sales += amt
            today_sales.append(s)

    today_sales_total = daily_sales

    # Batch fetch clients for today's sales in one query
    client_ids  = [s['client_id'] for s in today_sales if s.get('client_id')]
    clients_map = {}
    if client_ids:
        for c in db.clients.find({"_id": {"$in": client_ids}}, {"name": 1}):
            clients_map[str(c['_id'])] = c.get('name', 'Unknown Client')

    for sale in today_sales:
        sale['client_name'] = 'Cash Sale'
        if sale.get('client_id'):
            sale['client_name'] = clients_map.get(str(sale['client_id']), 'Unknown Client')
        sale['items_count'] = len(sale.get('items', []))

    # ── Profit calculation using already-fetched products ─────────────────────
    is_branch_admin       = (user_role == 'admin')
    daily_profit          = 0.0
    weekly_profit         = 0.0
    monthly_profit        = 0.0
    current_stock_value   = 0.0
    potential_sales_value = 0.0

    if is_branch_admin:
        # Build product price map from already-fetched products (no extra DB calls)
        product_price_map = {str(p['_id']): p.get('purchase_price', 0.0) for p in products}

        for sale in all_sales:
            sale_profit = 0.0
            for item in sale.get('items', []):
                pid        = str(item.get('product_id', ''))
                cost_price = product_price_map.get(pid, 0.0)
                sale_profit += item.get('quantity', 0) * (
                    item.get('selling_price', 0.0) - cost_price
                )
            if sale['date'] >= today_start:
                daily_profit += sale_profit
            if sale['date'] >= week_start:
                weekly_profit += sale_profit
            if sale['date'] >= month_start:
                monthly_profit += sale_profit

        current_stock_value   = sum(
            p.get('current_quantity', 0) * p.get('purchase_price', 0.0)
            for p in products
        )
        potential_sales_value = sum(
            p.get('current_quantity', 0) * p.get('selling_price', 0.0)
            for p in products
        )

    return render_template('dashboard.html',
                           is_super_admin=False,
                           is_branch_admin=is_branch_admin,
                           total_products=total_products,
                           low_stock_count=low_stock_count,
                           today_sales_total=today_sales_total,
                           daily_sales=daily_sales,
                           weekly_sales=weekly_sales,
                           monthly_sales=monthly_sales,
                           yearly_sales=yearly_sales,
                           daily_profit=round(daily_profit, 2),
                           weekly_profit=round(weekly_profit, 2),
                           monthly_profit=round(monthly_profit, 2),
                           today_sales=today_sales,
                           current_stock_value=current_stock_value,
                           potential_sales_value=potential_sales_value,
                           business_name=session.get('business_name', 'Your Branch'))


@app.route('/users')
def users():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_role = session.get('role')
    if user_role not in ['admin', 'super_admin']:
        flash('Access denied: Admin required', 'danger')
        return redirect(url_for('dashboard'))

    if user_role == 'super_admin':
        all_users = list(db.users.find().sort("created_at", DESCENDING))
    else:
        query     = get_business_query()
        all_users = list(db.users.find(query).sort("created_at", DESCENDING))

    # Batch fetch all businesses in one query
    all_biz = {str(b['_id']): b['name'] for b in db.businesses.find({}, {"name": 1})}
    for user in all_users:
        user['business_name'] = all_biz.get(str(user.get('business_id', '')), '—')

    return render_template('users.html', users=all_users)


# ── Add user: 20/hour — admin action, occasional use ─────────────────────────
@app.route('/users/add', methods=['POST'])
@limiter.limit("20 per hour", methods=["POST"])
def add_user():
    if 'user_id' not in session or session.get('role') not in ['admin', 'super_admin']:
        flash('Access denied', 'danger')
        return redirect(url_for('login'))

    username = request.form['username'].strip()
    password = request.form['password']
    role     = request.form['role']

    if not username or not password:
        flash('Username and password are required', 'danger')
        return redirect(url_for('users'))

    if db.users.find_one({"username": username}):
        flash('Username already exists', 'danger')
        return redirect(url_for('users'))

    hashed   = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = {
        "username":      username,
        "password_hash": hashed,
        "role":          role,
        "created_at":    datetime.utcnow()
    }

    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            try:
                new_user['business_id'] = ObjectId(business_id)
            except Exception:
                flash('Invalid business assignment', 'danger')
                return redirect(url_for('users'))

    db.users.insert_one(new_user)
    flash(f'User "{username}" added successfully!', 'success')
    return redirect(url_for('users'))


@app.route('/users/delete/<user_id>')
def delete_user(user_id):
    if 'user_id' not in session or session.get('role') not in ['admin', 'super_admin']:
        return redirect(url_for('login'))

    if user_id == session['user_id']:
        flash('You cannot delete yourself!', 'danger')
        return redirect(url_for('users'))

    db.users.delete_one({"_id": ObjectId(user_id)})
    flash('User deleted', 'info')
    return redirect(url_for('users'))


# ── Password reset: 10/hour — sensitive credential change ────────────────────
@app.route('/users/reset_password/<user_id>', methods=['POST'])
@limiter.limit("10 per hour", methods=["POST"])
def reset_user_password(user_id):
    if 'user_id' not in session or session.get('role') != 'super_admin':
        flash('Access denied: Super Admin only', 'danger')
        return redirect(url_for('dashboard'))

    new_password = request.form.get('new_password')
    if not new_password or len(new_password) < 6:
        flash('Password must be at least 6 characters', 'danger')
        return redirect(url_for('users'))

    hashed = bcrypt.generate_password_hash(new_password).decode('utf-8')
    result = db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password_hash": hashed}}
    )

    flash(
        'Password reset successfully!' if result.modified_count else 'User not found or error occurred',
        'success' if result.modified_count else 'danger'
    )
    return redirect(url_for('users'))


# ── BUSINESSES ────────────────────────────────────────────────────────────────

@app.route('/businesses')
def businesses():
    if 'user_id' not in session or session.get('role') != 'super_admin':
        flash('Access denied: Super Admin only', 'danger')
        return redirect(url_for('dashboard'))

    all_businesses = list(db.businesses.find().sort("created_at", DESCENDING))
    business_ids   = [b['_id'] for b in all_businesses]

    # Batch fetch all admins in one query instead of one per business
    all_admins = list(db.users.find(
        {"business_id": {"$in": business_ids}, "role": "admin"},
        {"username": 1, "business_id": 1}
    ))
    admins_map = {}
    for a in all_admins:
        bid = str(a['business_id'])
        admins_map.setdefault(bid, []).append(a['username'])

    businesses_with_admins = []
    for biz in all_businesses:
        businesses_with_admins.append({
            "business": biz,
            "admins":   admins_map.get(str(biz['_id']), [])
        })

    return render_template('businesses.html', businesses=businesses_with_admins)


# ── Create business: 10/hour — infrequent super-admin action ─────────────────
@app.route('/businesses/create', methods=['POST'])
@limiter.limit("10 per hour", methods=["POST"])
def create_business():
    if 'user_id' not in session or session.get('role') != 'super_admin':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    business_name  = request.form.get('business_name', '').strip()
    location       = request.form.get('location', '').strip()
    admin_username = request.form.get('admin_username', '').strip()
    admin_password = request.form.get('admin_password', '')

    if not all([business_name, admin_username, admin_password]):
        flash('All fields are required', 'danger')
        return redirect(url_for('businesses'))

    if db.users.find_one({"username": admin_username}):
        flash('Username already exists', 'danger')
        return redirect(url_for('businesses'))

    biz_result  = db.businesses.insert_one({
        "name":       business_name,
        "location":   location,
        "created_at": datetime.utcnow()
    })
    business_id = biz_result.inserted_id

    hashed = bcrypt.generate_password_hash(admin_password).decode('utf-8')
    db.users.insert_one({
        "username":      admin_username,
        "password_hash": hashed,
        "role":          "admin",
        "business_id":   business_id,
        "created_at":    datetime.utcnow()
    })

    flash(f'Business "{business_name}" created with admin "{admin_username}"!', 'success')
    return redirect(url_for('businesses'))


# ── Delete business: 5/hour — destructive super-admin action ─────────────────
@app.route('/businesses/delete/<business_id>', methods=['POST'])
@limiter.limit("5 per hour", methods=["POST"])
def delete_business(business_id):
    if 'user_id' not in session or session.get('role') != 'super_admin':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    try:
        obj_id = ObjectId(business_id)
    except Exception:
        flash('Invalid business ID', 'danger')
        return redirect(url_for('businesses'))

    business = db.businesses.find_one({"_id": obj_id})
    if not business:
        flash('Business not found', 'danger')
        return redirect(url_for('businesses'))

    business_name = business['name']
    deleted = db.users.delete_many({"business_id": obj_id}).deleted_count
    db.businesses.delete_one({"_id": obj_id})

    flash(f'Business "{business_name}" deleted. {deleted} user(s) also removed.', 'success')
    return redirect(url_for('businesses'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)