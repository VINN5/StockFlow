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

@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    query = get_business_query()
    sales = list(current_app.db.sales.find(query).sort("date", -1))
    
    products = {str(p['_id']): p['name'] for p in current_app.db.products.find(get_business_query())}
    
    for sale in sales:
        for item in sale['items']:
            item['product_name'] = products.get(str(item['product_id']), 'Unknown')
            item['line_total'] = item['quantity'] * item['selling_price']
    
    return render_template('sales.html', sales=sales)