from flask import Blueprint, render_template, redirect, url_for, session, current_app as app
from bson.objectid import ObjectId
from datetime import datetime

bp = Blueprint('sales', __name__, url_prefix='/sales')

@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
   
    sales = list(app.db.sales.find().sort("date", -1))
    
    
    products = {str(p['_id']): p['name'] for p in app.db.products.find()}
    
    for sale in sales:
        for item in sale['items']:
            item['product_name'] = products.get(item['product_id'], 'Unknown')
            item['line_total'] = item['quantity'] * item['selling_price']
    
    return render_template('sales.html', sales=sales)  