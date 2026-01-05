from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from bson.objectid import ObjectId
from datetime import datetime

bp = Blueprint('pos', __name__, url_prefix='/pos')

def get_business_query():
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
    
    products = list(current_app.db.products.find({
        **query,
        "current_quantity": {"$gt": 0}
    }).sort("name", 1))
    
    clients = list(current_app.db.clients.find(query).sort("name", 1))
    
    return render_template('pos.html', products=products, clients=clients)

@bp.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 401
    
    data = request.get_json()
    items = data['items']
    total_amount = sum(item['quantity'] * item['selling_price'] for item in items)
    payment_method = data.get('payment_method', 'cash')
    client_id = data.get('client_id')
    
    # Validate and deduct stock
    for item in items:
        product_id = ObjectId(item['product_id'])
        result = current_app.db.products.update_one(
            {"_id": product_id, "current_quantity": {"$gte": item['quantity']}},
            {"$inc": {"current_quantity": -item['quantity']}}
        )
        if result.modified_count == 0:
            product = current_app.db.products.find_one({"_id": product_id})
            name = product['name'] if product else 'Unknown'
            return jsonify({'success': False, 'message': f'Not enough stock for {name}'}), 400
    
    # Create sale document
    sale = {
        "items": items,
        "total_amount": total_amount,
        "payment_method": payment_method,
        "date": datetime.utcnow(),
        "cashier_id": session['user_id'],
        "cashier_name": session['username']
    }
    
    if client_id:
        sale['client_id'] = ObjectId(client_id)
    
    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            try:
                sale['business_id'] = ObjectId(business_id)
            except:
                pass
    
    result = current_app.db.sales.insert_one(sale)
    sale_id = str(result.inserted_id)
    
    # Update client balance on credit sale
    if payment_method == 'credit' and client_id:
        current_app.db.clients.update_one(
            {"_id": ObjectId(client_id)},
            {"$inc": {"balance": total_amount}}
        )
    
    # Use _external=True to get full absolute URL (critical for redirect from JS)
    receipt_url = url_for('pos.receipt', sale_id=sale_id, _external=True)
    
    return jsonify({
        'success': True,
        'message': 'Sale completed!',
        'redirect': receipt_url
    })

@bp.route('/receipt/<sale_id>')
def receipt(sale_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        obj_id = ObjectId(sale_id)
    except:
        flash('Invalid sale ID', 'danger')
        return redirect(url_for('pos.index'))
    
    query = {"_id": obj_id}
    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            try:
                query['business_id'] = ObjectId(business_id)
            except:
                flash('Access denied', 'danger')
                return redirect(url_for('pos.index'))
    
    sale = current_app.db.sales.find_one(query)
    if not sale:
        flash('Sale not found or access denied', 'danger')
        return redirect(url_for('pos.index'))
    
    client_name = None
    client_contact = None
    client_kra_pin = None
    previous_balance = 0.0
    new_balance = 0.0
    
    if sale.get('client_id'):
        client = current_app.db.clients.find_one({"_id": sale['client_id']})
        if client:
            client_name = client.get('name', 'Unknown Client')
            client_contact = client.get('contact')
            client_kra_pin = client.get('kra_pin')
            if sale.get('payment_method') == 'credit':
                previous_balance = client.get('balance', 0.0) - sale.get('total_amount', 0.0)
                new_balance = client.get('balance', 0.0)
            else:
                previous_balance = client.get('balance', 0.0)
                new_balance = previous_balance
    
    for item in sale['items']:
        product = current_app.db.products.find_one({"_id": ObjectId(item['product_id'])})
        item['product_name'] = product['name'] if product else 'Unknown'
        item['line_total'] = item['quantity'] * item['selling_price']
    
    return render_template('pos_receipt.html', 
                           sale=sale, 
                           client_name=client_name,
                           client_contact=client_contact,
                           client_kra_pin=client_kra_pin,
                           previous_balance=previous_balance,
                           new_balance=new_balance)