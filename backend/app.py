from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from datetime import datetime
from bson.objectid import ObjectId

from pymongo import MongoClient
from flask_bcrypt import Bcrypt

# ✅ Proper relative imports
from .config import Config
from .models.user import User
from .routes.products import bp as products_bp
from .routes.suppliers import bp as suppliers_bp
from .routes.purchases import bp as purchases_bp
from .routes.pos import bp as pos_bp


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
            role = "admin" if db.users.count_documents({}) == 0 else "cashier"
            user = User(username, password, role)
            db.users.insert_one(user.to_dict())
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
        low_stock_items=low_stock_items
    )


@app.route('/users')
def users():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('dashboard'))

    all_users = list(db.users.find())
    return render_template('users.html', users=all_users)


@app.route('/users/add', methods=['POST'])
def add_user():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    username = request.form['username']
    password = request.form['password']
    role = request.form['role']

    if db.users.find_one({"username": username}):
        flash('Username already exists', 'danger')
    else:
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        db.users.insert_one({
            "username": username,
            "password_hash": hashed,
            "role": role,
            "created_at": datetime.utcnow()
        })
        flash('User added successfully!', 'success')

    return redirect(url_for('users'))


@app.route('/users/delete/<user_id>')
def delete_user(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    if user_id == session['user_id']:
        flash('You cannot delete yourself!', 'danger')
        return redirect(url_for('users'))

    db.users.delete_one({"_id": ObjectId(user_id)})
    flash('User deleted', 'info')
    return redirect(url_for('users'))


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
