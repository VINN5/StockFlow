from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app as app, jsonify
from bson.objectid import ObjectId
from datetime import datetime

bp = Blueprint('purchases', __name__, url_prefix='/purchases')

@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    purchases = list(app.db.purchases.find().sort("date", -1))
    suppliers = {str(s['_id']): s['name'] for s in app.db.suppliers.find()}
    products = {str(p['_id']): p['name'] for p in app.db.products.find()}
    
    
    for purchase in purchases:
        purchase['supplier_name'] = suppliers.get(str(purchase['supplier_id']), 'Unknown')
        for item in purchase['items']:
            item['product_name'] = products.get(item['product_id'], 'Unknown')
    
    return render_template('purchases.html', purchases=purchases)

@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 401
    
    data = request.get_json()
    supplier_id = data['supplier_id']
    items = data['items']
    total_cost = sum(item['quantity'] * item['cost_price'] for item in items)
    
    
    for item in items:
        product_id = ObjectId(item['product_id'])
        app.db.products.update_one(
            {"_id": product_id},
            {"$inc": {"current_quantity": item['quantity']}}
        )
    
    
    purchase = {
        "supplier_id": ObjectId(supplier_id),
        "items": items,
        "total_cost": total_cost,
        "date": datetime.utcnow()
    }
    result = app.db.purchases.insert_one(purchase)
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
    
    suppliers = list(app.db.suppliers.find())
    products = list(app.db.products.find())
    return render_template('purchase_new.html', suppliers=suppliers, products=products)

@bp.route('/receipt/<purchase_id>')
def receipt(purchase_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    purchase = app.db.purchases.find_one({"_id": ObjectId(purchase_id)})
    if not purchase:
        flash('Purchase not found', 'danger')
        return redirect(url_for('purchases.index'))
    
    supplier = app.db.suppliers.find_one({"_id": purchase['supplier_id']})
    supplier_name = supplier['name'] if supplier else 'Unknown'
    
    
    for item in purchase['items']:
        product = app.db.products.find_one({"_id": ObjectId(item['product_id'])})
        item['product_name'] = product['name'] if product else 'Unknown'
        item['line_total'] = item['quantity'] * item['cost_price']
    
    return render_template('purchase_receipt.html',
                           purchase=purchase,
                           supplier_name=supplier_name)