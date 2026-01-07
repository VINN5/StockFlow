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
    items = data.get('items', [])
    if not items:
        return jsonify({'success': False, 'message': 'No items in cart'}), 400
    
    total_amount = 0.0
    for item in items:
        quantity = float(item.get('quantity', 0))
        price = float(item.get('selling_price', 0.0))
        total_amount += quantity * price
    
    payment_method = data.get('payment_method', 'cash')
    client_id_str = data.get('client_id')
    
    
    for item in items:
        try:
            product_id = ObjectId(item['product_id'])
        except:
            return jsonify({'success': False, 'message': 'Invalid product ID'}), 400
        
        quantity = int(item.get('quantity', 0))
        result = current_app.db.products.update_one(
            {"_id": product_id, "current_quantity": {"$gte": quantity}},
            {"$inc": {"current_quantity": -quantity}}
        )
        if result.modified_count == 0:
            product = current_app.db.products.find_one({"_id": product_id})
            name = product['name'] if product else 'Unknown'
            return jsonify({'success': False, 'message': f'Not enough stock for {name}'}), 400
    
    
    sale = {
        "items": items,
        "total_amount": total_amount,
        "payment_method": payment_method,
        "date": datetime.utcnow(),
        "cashier_id": session['user_id'],
        "cashier_name": session['username']
    }
    
    if client_id_str:
        try:
            sale['client_id'] = ObjectId(client_id_str)
        except:
            pass
    
    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            try:
                sale['business_id'] = ObjectId(business_id)
            except:
                pass
    
    result = current_app.db.sales.insert_one(sale)
    sale_id = str(result.inserted_id)
    
    
    if payment_method == 'credit' and client_id_str:
        try:
            current_app.db.clients.update_one(
                {"_id": ObjectId(client_id_str)},
                {"$inc": {"balance": total_amount}}
            )
        except:
            pass
    
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
    
  
    client_name = 'Cash Sale'
    client_contact = None
    client_kra_pin = None
    previous_balance = None
    new_balance = None
    
    client = None
    if sale.get('client_id'):
        try:
            client = current_app.db.clients.find_one(sale['client_id'])
        except:
            client = None
    
    if client:
        client_name = client.get('name', 'Unknown Client')
        client_contact = client.get('contact')
        client_kra_pin = client.get('kra_pin')
        current_balance = client.get('balance', 0.0)
        if sale.get('payment_method') == 'credit':
            previous_balance = current_balance - sale.get('total_amount', 0.0)
            new_balance = current_balance
    
   
    enriched_items = []
    for raw_item in sale.get('items', []):
        quantity = float(raw_item.get('quantity', 0))
        price = float(raw_item.get('selling_price', 0.0))
        line_total = quantity * price
        product_name = 'Unknown Product'
        
        product_id_str = raw_item.get('product_id')
        if product_id_str:
            try:
                product = current_app.db.products.find_one(ObjectId(product_id_str))
                if product:
                    product_name = product.get('name', 'Unknown Product')
            except:
                product_name = 'Deleted Product'
        
        enriched_items.append({
            'product_name': product_name,
            'quantity': quantity,
            'selling_price': price,
            'line_total': line_total
        })
    
    
    context = {
        'sale_id': str(sale['_id']),
        'payment_method': sale.get('payment_method', 'cash'),
        'total_amount': sale.get('total_amount', 0.0),
        'cashier_name': sale.get('cashier_name', 'Unknown'),
        'date_formatted': sale['date'].strftime('%d %B %Y, %H:%M') if 'date' in sale else 'Unknown Date',
        'items': enriched_items,
        'client_name': client_name,
        'client_contact': client_contact,
        'client_kra_pin': client_kra_pin,
        'previous_balance': previous_balance,
        'new_balance': new_balance,
        'business_name': session.get('business_name', 'StockFlow Shop')
    }
    
    return render_template('pos_receipt.html', **context)