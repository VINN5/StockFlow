from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from bson.objectid import ObjectId
from datetime import datetime

bp = Blueprint('purchases', __name__, url_prefix='/purchases')

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
    
    # Filter purchases by business
    query = get_business_query()
    purchases = list(current_app.db.purchases.find(query).sort("date", -1))
    
    # Get suppliers and products (filtered for non-super_admin)
    supplier_query = get_business_query()
    product_query = get_business_query()
    
    suppliers = {str(s['_id']): s['name'] for s in current_app.db.suppliers.find(supplier_query)}
    products = {str(p['_id']): p['name'] for p in current_app.db.products.find(product_query)}
    
    for purchase in purchases:
        purchase['supplier_name'] = suppliers.get(str(purchase['supplier_id']), 'Unknown')
        for item in purchase['items']:
            item['product_name'] = products.get(str(item['product_id']), 'Unknown')
    
    return render_template('purchases.html', purchases=purchases)

@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 401
    
    data = request.get_json()
    supplier_id = data['supplier_id']
    items = data['items']
    total_cost = sum(item['quantity'] * item['cost_price'] for item in items)
    
    # Update stock for each product
    for item in items:
        product_id = ObjectId(item['product_id'])
        current_app.db.products.update_one(
            {"_id": product_id},
            {"$inc": {"current_quantity": item['quantity']}}
        )
    
    # Create purchase document
    purchase = {
        "supplier_id": ObjectId(supplier_id),
        "items": items,
        "total_cost": total_cost,
        "date": datetime.utcnow()
    }
    
    # Add business_id for non-super_admin
    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            try:
                purchase['business_id'] = ObjectId(business_id)
            except:
                return jsonify({'success': False, 'message': 'Invalid business context'}), 400
    
    result = current_app.db.purchases.insert_one(purchase)
    purchase_id = str(result.inserted_id)
    
    receipt_url = url_for('purchases.receipt', purchase_id=purchase_id)
    return jsonify({
        'success': True,
        'message': 'Purchase recorded successfully!',
        'redirect': receipt_url
    })

@bp.route('/new')
def new():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Filter suppliers and products by business
    query = get_business_query()
    suppliers = list(current_app.db.suppliers.find(query))
    products = list(current_app.db.products.find(query))
    
    return render_template('purchase_new.html', suppliers=suppliers, products=products)

@bp.route('/receipt/<purchase_id>')
def receipt(purchase_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        obj_id = ObjectId(purchase_id)
    except:
        flash('Invalid purchase ID', 'danger')
        return redirect(url_for('purchases.index'))
    
    # Filter receipt by business_id
    query = {"_id": obj_id}
    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            try:
                query['business_id'] = ObjectId(business_id)
            except:
                flash('Access denied', 'danger')
                return redirect(url_for('purchases.index'))
    
    purchase = current_app.db.purchases.find_one(query)
    if not purchase:
        flash('Purchase not found or access denied', 'danger')
        return redirect(url_for('purchases.index'))
    
    supplier = current_app.db.suppliers.find_one({"_id": purchase['supplier_id']})
    supplier_name = supplier['name'] if supplier else 'Unknown'
    
    for item in purchase['items']:
        product = current_app.db.products.find_one({"_id": ObjectId(item['product_id'])})
        item['product_name'] = product['name'] if product else 'Unknown'
        item['line_total'] = item['quantity'] * item['cost_price']
    
    return render_template('purchase_receipt.html',
                           purchase=purchase,
                           supplier_name=supplier_name)