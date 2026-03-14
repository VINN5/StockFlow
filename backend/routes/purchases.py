from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from bson.objectid import ObjectId
from datetime import datetime
from .excel_io import export_purchases

bp = Blueprint('purchases', __name__, url_prefix='/purchases')


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


def group_by_business(items, db):
    businesses = {str(b['_id']): b['name'] for b in db.businesses.find()}
    grouped = {}
    for item in items:
        bid = str(item.get('business_id', ''))
        bname = businesses.get(bid, 'Unassigned')
        grouped.setdefault(bname, []).append(item)
    return grouped


def enrich_purchases(purchases, db, query):
    suppliers = {str(s['_id']): s['name'] for s in db.suppliers.find(query)}
    products  = {str(p['_id']): p['name'] for p in db.products.find(query)}
    for purchase in purchases:
        # Ensure date is always a datetime object
        if isinstance(purchase.get('date'), str):
            try:
                purchase['date'] = datetime.fromisoformat(purchase['date'])
            except Exception:
                purchase['date'] = None
        elif not isinstance(purchase.get('date'), datetime):
            purchase['date'] = None

        sid = str(purchase['supplier_id']) if purchase.get('supplier_id') else ''
        purchase['supplier_name'] = suppliers.get(sid, 'Unknown Supplier')
        for item in purchase.get('items', []):
            pid = str(item.get('product_id', '')) if item.get('product_id') else ''
            item['product_name'] = products.get(pid, 'Unknown Product')


@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    is_super_admin = session.get('role') == 'super_admin'
    query = get_business_query()
    purchases = list(current_app.db.purchases.find(query).sort("date", -1))
    enrich_purchases(purchases, current_app.db, query)
    grouped = group_by_business(purchases, current_app.db) if is_super_admin else None

    return render_template('purchases.html',
                           purchases=purchases,
                           grouped=grouped,
                           is_super_admin=is_super_admin)


@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 401

    data = request.get_json()
    supplier_id = data['supplier_id']
    items = data['items']
    total_cost = sum(item['quantity'] * item['cost_price'] for item in items)

    business_query = get_business_query()
    for item in items:
        product_id = ObjectId(item['product_id'])
        current_app.db.products.update_one(
            {"_id": product_id, **business_query},
            {"$inc": {"current_quantity": item['quantity']}}
        )

    purchase = {
        "supplier_id": ObjectId(supplier_id),
        "items": items,
        "total_cost": total_cost,
        "date": datetime.utcnow()
    }

    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            try:
                purchase['business_id'] = ObjectId(business_id)
            except Exception:
                return jsonify({'success': False, 'message': 'Invalid business context'}), 400

    result = current_app.db.purchases.insert_one(purchase)
    receipt_url = url_for('purchases.receipt', purchase_id=str(result.inserted_id))
    return jsonify({'success': True, 'message': 'Purchase recorded successfully!', 'redirect': receipt_url})


@bp.route('/new')
def new():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    query = get_business_query()
    suppliers = list(current_app.db.suppliers.find(query))
    products  = list(current_app.db.products.find(query))
    return render_template('purchase_new.html', suppliers=suppliers, products=products)


@bp.route('/receipt/<purchase_id>')
def receipt(purchase_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        obj_id = ObjectId(purchase_id)
    except Exception:
        flash('Invalid purchase ID', 'danger')
        return redirect(url_for('purchases.index'))

    query = {"_id": obj_id}
    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            try:
                query['business_id'] = ObjectId(business_id)
            except Exception:
                flash('Access denied', 'danger')
                return redirect(url_for('purchases.index'))

    purchase = current_app.db.purchases.find_one(query)
    if not purchase:
        flash('Purchase not found or access denied', 'danger')
        return redirect(url_for('purchases.index'))

    supplier_name = 'Unknown Supplier'
    if purchase.get('supplier_id'):
        supplier = current_app.db.suppliers.find_one(purchase['supplier_id'])
        if supplier:
            supplier_name = supplier.get('name', 'Unknown Supplier')

    enriched_items = []
    for item in purchase.get('items', []):
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

    # Safe date formatting
    purchase_date = purchase.get('date')
    if isinstance(purchase_date, str):
        try:
            purchase_date = datetime.fromisoformat(purchase_date)
        except Exception:
            purchase_date = None

    date_formatted = purchase_date.strftime('%d %B %Y, %H:%M') if purchase_date else 'Unknown'

    return render_template('purchase_receipt.html',
                           purchase_id=str(purchase['_id']),
                           date_formatted=date_formatted,
                           supplier_name=supplier_name,
                           total_cost=purchase.get('total_cost', 0.0),
                           items=enriched_items,
                           business_name=session.get('business_name', 'StockFlow Business'))


# ── Excel export ──────────────────────────────────────────────────────────────
@bp.route('/export')
def export():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    query = get_business_query()
    purchases = list(current_app.db.purchases.find(query).sort("date", -1))
    enrich_purchases(purchases, current_app.db, query)
    return export_purchases(purchases)