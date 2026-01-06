from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from bson.objectid import ObjectId
from datetime import datetime

bp = Blueprint('products', __name__, url_prefix='/products')

def get_business_query():
    """Return MongoDB query filter for business_id based on user role"""
    if session.get('role') == 'super_admin':
        return {}
    business_id = session.get('business_id')
    if business_id:
        try:
            return {"business_id": ObjectId(business_id)}
        except:
            return {}
    return {}

@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    query = get_business_query()
    products = list(current_app.db.products.find(query).sort("name", 1))
    return render_template('products.html', products=products)

@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        purchase_price = float(request.form['purchase_price'])
        selling_price = float(request.form['selling_price'])
        min_stock = int(request.form['min_stock'])
        current_quantity = int(request.form.get('current_quantity', 0))
        max_stock = int(request.form.get('max_stock')) if request.form.get('max_stock') else None
    except ValueError:
        flash('Invalid number format', 'danger')
        return redirect(url_for('products.index'))
    
    product_data = {
        "name": request.form['name'].strip(),
        "description": request.form.get('description', '').strip(),
        "unit": request.form['unit'],
        "purchase_price": purchase_price,
        "selling_price": selling_price,
        "min_stock": min_stock,
        "max_stock": max_stock,
        "current_quantity": current_quantity,
        "created_at": datetime.utcnow()
    }
    
    # Add business_id for non-super_admin
    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            try:
                product_data['business_id'] = ObjectId(business_id)
            except:
                flash('Invalid business context', 'danger')
                return redirect(url_for('products.index'))
    
    current_app.db.products.insert_one(product_data)
    flash('Product added successfully!', 'success')
    return redirect(url_for('products.index'))

@bp.route('/edit/<product_id>', methods=['GET', 'POST'])
def edit(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        obj_id = ObjectId(product_id)
    except:
        flash('Invalid product ID', 'danger')
        return redirect(url_for('products.index'))
    
    query = {"_id": obj_id}
    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            try:
                query['business_id'] = ObjectId(business_id)
            except:
                flash('Access denied', 'danger')
                return redirect(url_for('products.index'))
    
    product = current_app.db.products.find_one(query)
    if not product:
        flash('Product not found or access denied', 'danger')
        return redirect(url_for('products.index'))
    
    if request.method == 'POST':
        try:
            updated = {
                "name": request.form['name'].strip(),
                "description": request.form.get('description', '').strip(),
                "unit": request.form['unit'],
                "purchase_price": float(request.form['purchase_price']),
                "selling_price": float(request.form['selling_price']),
                "min_stock": int(request.form['min_stock']),
                "max_stock": int(request.form.get('max_stock')) if request.form.get('max_stock') else None,
                "current_quantity": int(request.form.get('current_quantity', product.get('current_quantity', 0)))
            }
            current_app.db.products.update_one({"_id": obj_id}, {"$set": updated})
            flash('Product updated successfully!', 'success')
        except ValueError:
            flash('Invalid input - check numbers', 'danger')
        
        return redirect(url_for('products.index'))
    
    return render_template('product_edit.html', product=product)

@bp.route('/delete/<product_id>')
def delete(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        obj_id = ObjectId(product_id)
    except:
        flash('Invalid product ID', 'danger')
        return redirect(url_for('products.index'))
    
    query = {"_id": obj_id}
    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            try:
                query['business_id'] = ObjectId(business_id)
            except:
                flash('Access denied', 'danger')
                return redirect(url_for('products.index'))
    
    result = current_app.db.products.delete_one(query)
    if result.deleted_count:
        flash('Product deleted', 'info')
    else:
        flash('Product not found or access denied', 'danger')
    
    return redirect(url_for('products.index'))