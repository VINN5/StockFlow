from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from datetime import datetime
from bson.objectid import ObjectId

from pymongo import MongoClient
from flask_bcrypt import Bcrypt


from .config import Config
from .models.user import User
from .routes.products import bp as products_bp
from .routes.suppliers import bp as suppliers_bp
from .routes.purchases import bp as purchases_bp
from .routes.pos import bp as pos_bp
from .routes.sales import bp as sales_bp


app = Flask(
    __name__,
    template_folder='../frontend/templates',
    static_folder='../frontend/static'
)

app.config.from_object(Config)
app.secret_key = app.config['SECRET_KEY']

bcrypt = Bcrypt(app)
client = MongoClient(app.config["MONGODB_URI"])
db = client.stockflow
app.db = db

app.register_blueprint(products_bp)
app.register_blueprint(suppliers_bp)
app.register_blueprint(purchases_bp)
app.register_blueprint(pos_bp)
app.register_blueprint(sales_bp)


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = db.users.find_one({"username": username})
        if user and bcrypt.check_password_hash(user['password_hash'], password):
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['role'] = user['role']
            
            
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


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if db.users.find_one({"username": username}):
            flash('Username already exists', 'error')
        else:
            role = "super_admin" if db.users.count_documents({}) == 0 else "cashier"
            user = User(username, password, role)
            user_dict = user.to_dict()
            if role != "super_admin":
                user_dict['business_id'] = None  
            db.users.insert_one(user_dict)
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    products = list(db.products.find())

    total_products = len(products)
    total_stock_value = sum(
        p.get('current_quantity', 0) * p.get('purchase_price', 0)
        for p in products
    )
    potential_sales_value = sum(
        p.get('current_quantity', 0) * p.get('selling_price', 0)
        for p in products
    )

    low_stock_items = [
        p for p in products if p.get('current_quantity', 0) < p.get('min_stock', 10)
    ]

    return render_template(
        'dashboard.html',
        total_products=total_products,
        total_stock_value=total_stock_value,
        potential_sales_value=potential_sales_value,
        total_sales=0,
        low_stock_count=len(low_stock_items),
        low_stock_items=low_stock_items,
        business_name=session.get('business_name', 'StockFlow')
    )


@app.route('/users')
def users():
    if 'user_id' not in session or session.get('role') not in ['admin', 'super_admin']:
        flash('Admin access required', 'danger')
        return redirect(url_for('dashboard'))

    all_users = list(db.users.find())
    return render_template('users.html', users=all_users)


@app.route('/users/add', methods=['POST'])
def add_user():
    if 'user_id' not in session or session.get('role') not in ['admin', 'super_admin']:
        return redirect(url_for('login'))

    username = request.form['username']
    password = request.form['password']
    role = request.form['role']

    if db.users.find_one({"username": username}):
        flash('Username already exists', 'danger')
    else:
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = {
            "username": username,
            "password_hash": hashed,
            "role": role,
            "created_at": datetime.utcnow(),
            "business_id": None 
        }
        db.users.insert_one(new_user)
        flash('User added successfully!', 'success')

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


# ==================== SUPER ADMIN: BUSINESSES MANAGEMENT ====================

@app.route('/businesses')
def businesses():
    if 'user_id' not in session or session.get('role') != 'super_admin':
        flash('Access denied: Super Admin only', 'danger')
        return redirect(url_for('dashboard'))
    
    # Fetch all businesses, sorted newest first
    all_businesses = list(db.businesses.find().sort("created_at", -1))
    
    # Build enriched list with admin usernames
    businesses_with_admins = []
    for biz in all_businesses:
        admins = list(db.users.find(
            {"business_id": biz['_id'], "role": "admin"},
            {"username": 1, "_id": 0}
        ))
        admin_usernames = [admin['username'] for admin in admins]
        
        businesses_with_admins.append({
            "business": biz,
            "admins": admin_usernames
        })
    
    return render_template('businesses.html', businesses=businesses_with_admins)


@app.route('/businesses/create', methods=['POST'])
def create_business():
    if 'user_id' not in session or session.get('role') != 'super_admin':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    business_name = request.form.get('business_name', '').strip()
    location = request.form.get('location', '').strip()
    admin_username = request.form.get('admin_username', '').strip()
    admin_password = request.form.get('admin_password', '')
    
    if not all([business_name, admin_username, admin_password]):
        flash('All fields are required', 'danger')
        return redirect(url_for('businesses'))
    
    if db.users.find_one({"username": admin_username}):
        flash('Username already exists', 'danger')
        return redirect(url_for('businesses'))
    
    
    business_result = db.businesses.insert_one({
        "name": business_name,
        "location": location,
        "created_at": datetime.utcnow()
    })
    business_id = business_result.inserted_id
    
    
    hashed = bcrypt.generate_password_hash(admin_password).decode('utf-8')
    db.users.insert_one({
        "username": admin_username,
        "password_hash": hashed,
        "role": "admin",
        "business_id": business_id,
        "created_at": datetime.utcnow()
    })
    
    flash(f'Business "{business_name}" created with admin "{admin_username}"!', 'success')
    return redirect(url_for('businesses') + '?t=' + str(int(datetime.utcnow().timestamp())))


@app.route('/businesses/delete/<business_id>', methods=['POST'])
def delete_business(business_id):
    if 'user_id' not in session or session.get('role') != 'super_admin':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        obj_id = ObjectId(business_id)
    except:
        flash('Invalid business ID', 'danger')
        return redirect(url_for('businesses'))
    
    
    business = db.businesses.find_one({"_id": obj_id})
    if not business:
        flash('Business not found', 'danger')
        return redirect(url_for('businesses'))
    
    business_name = business['name']
    
    
    delete_admins_result = db.users.delete_many({
        "business_id": obj_id,
        "role": "admin"
    })
    admins_deleted = delete_admins_result.deleted_count
    
    
    db.businesses.delete_one({"_id": obj_id})
    
    flash(f'Business "{business_name}" deleted successfully. '
          f'{admins_deleted} branch admin(s) also removed.', 'success')
    
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