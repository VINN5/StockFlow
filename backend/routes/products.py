from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app as app
from models.product import Product
from bson.objectid import ObjectId  

bp = Blueprint('products', __name__, url_prefix='/products')

@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    products = list(app.db.products.find())
    return render_template('products.html', products=products)

@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    product = Product(
        name=request.form['name'],
        description=request.form.get('description', ''),
        unit=request.form['unit'],
        purchase_price=request.form['purchase_price'],
        selling_price=request.form['selling_price'],
        min_stock=request.form['min_stock'],
        max_stock=request.form.get('max_stock') or None,
        current_quantity=request.form.get('current_quantity', 0)
    )
    app.db.products.insert_one(product.to_dict())
    flash('Product added successfully!', 'success')
    return redirect(url_for('products.index'))

@bp.route('/edit/<product_id>', methods=['GET', 'POST'])
def edit(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    product = app.db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        flash('Product not found', 'danger')
        return redirect(url_for('products.index'))
    
    if request.method == 'POST':
        updated = {
            "name": request.form['name'],
            "description": request.form.get('description', ''),
            "unit": request.form['unit'],
            "purchase_price": float(request.form['purchase_price']),
            "selling_price": float(request.form['selling_price']),
            "min_stock": int(request.form['min_stock']),
            "max_stock": int(request.form['max_stock']) if request.form.get('max_stock') else None,
            "current_quantity": int(request.form.get('current_quantity', product['current_quantity']))
        }
        app.db.products.update_one({"_id": ObjectId(product_id)}, {"$set": updated})
        flash('Product updated successfully!', 'success')
        return redirect(url_for('products.index'))
    
    return render_template('product_edit.html', product=product)

@bp.route('/delete/<product_id>')
def delete(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    app.db.products.delete_one({"_id": ObjectId(product_id)})
    flash('Product deleted', 'info')
    return redirect(url_for('products.index'))