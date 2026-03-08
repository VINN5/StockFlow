from flask import Blueprint, render_template, redirect, url_for, session, current_app
from bson.objectid import ObjectId
from datetime import datetime

bp = Blueprint('sales', __name__, url_prefix='/sales')

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

def group_by_business(items, db):
    businesses = {str(b['_id']): b['name'] for b in db.businesses.find()}
    grouped = {}
    for item in items:
        bid = str(item.get('business_id', ''))
        bname = businesses.get(bid, 'Unassigned')
        grouped.setdefault(bname, []).append(item)
    return grouped

@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    is_super_admin = session.get('role') == 'super_admin'
    query = get_business_query()
    sales = list(current_app.db.sales.find(query).sort("date", -1))

    products = {str(p['_id']): p['name']
                for p in current_app.db.products.find(get_business_query())}

    for sale in sales:
        for item in sale.get('items', []):
            item['product_name'] = products.get(str(item.get('product_id', '')), 'Unknown')
            item['line_total'] = item.get('quantity', 0) * item.get('selling_price', 0)

    grouped = group_by_business(sales, current_app.db) if is_super_admin else None

    return render_template('sales.html',
                           sales=sales,
                           grouped=grouped,
                           is_super_admin=is_super_admin)