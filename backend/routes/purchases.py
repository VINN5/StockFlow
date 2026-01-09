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
    
    # Get suppliers and products (filtered)
    supplier_query = get_business_query()
    product_query = get_business_query()
    
    suppliers = {str(s['_id']): s['name'] for s in current_app.db.suppliers.find(supplier_query)}
    products = {str(p['_id']): p['name'] for p in current_app.db.products.find(product_query)}
    
    # Safe enrichment
    for purchase in purchases:
        supplier_id_str = str(purchase.get('supplier_id', '')) if purchase.get('supplier_id') else ''
        purchase['supplier_name'] = suppliers.get(supplier_id_str, 'Unknown Supplier')
        
        # Convert items to list (critical fix!)
        purchase_items = list(purchase.get('items', []))
        for item in purchase_items:
            product_id_str = str(item.get('product_id', '')) if item.get('product_id') else ''
            item['product_name'] = products.get(product_id_str, 'Unknown Product')
        
        # Replace with list to make it iterable in template
        purchase['items'] = purchase_items
    
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
    
    # Safe supplier name
    supplier_name = 'Unknown Supplier'
    if purchase.get('supplier_id'):
        supplier = current_app.db.suppliers.find_one(purchase['supplier_id'])
        if supplier:
            supplier_name = supplier.get('name', 'Unknown Supplier')
    
    # Convert items to list and enrich
    enriched_items = []
    for item in list(purchase.get('items', [])):  # ← convert to list here
        product_name = 'Unknown Product'
        if item.get('product_id'):
            product = current_app.db.products.find_one(ObjectId(item['product_id']))
            if product:
                product_name = product.get('name', 'Unknown Product')
        
        enriched_items.append({
            'product_name': product_name,
            'quantity': item.get('quantity', 0),
            'cost_price': item.get('cost_price', 0.0),
            'line_total': item.get('quantity', 0) * item.get('cost_price', 0.0)
        })
    
    # Safe context
    context = {
        'purchase_id': str(purchase['_id']),
        'date_formatted': purchase['date'].strftime('%d %B %Y, %H:%M') if 'date' in purchase else 'Unknown Date',
        'supplier_name': supplier_name,
        'total_cost': purchase.get('total_cost', 0.0),
        'items': enriched_items,  # ← now a real list
        'business_name': session.get('business_name', 'StockFlow Business')
    }
    
    return render_template('purchase_receipt.html', **context)