from flask import Blueprint, render_template, redirect, url_for, session, current_app, request
from bson.objectid import ObjectId
from datetime import datetime
from .excel_io import export_sales

bp = Blueprint('sales', __name__, url_prefix='/sales')


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


@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    is_super_admin = session.get('role') == 'super_admin'
    query = get_business_query()

    date_str = request.args.get('date', '')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.utcnow()
    except ValueError:
        selected_date = datetime.utcnow()

    day_start = selected_date.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    day_end   = selected_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    all_sales = list(current_app.db.sales.find(query).sort("date", -1))
    day_sales = list(current_app.db.sales.find(
        {**query, "date": {"$gte": day_start, "$lte": day_end}}
    ).sort("date", 1))

    products = {str(p['_id']): p for p in current_app.db.products.find(query)}

    def enrich(sales_list):
        for sale in sales_list:
            for item in sale.get('items', []):
                pid     = str(item.get('product_id', ''))
                product = products.get(pid, {})
                cost    = float(product.get('purchase_price', 0))
                qty     = float(item.get('quantity', 0))
                price   = float(item.get('selling_price', 0))
                item['product_name']   = product.get('name', 'Unknown')
                item['purchase_price'] = cost
                item['line_total']     = qty * price
                item['line_profit']    = qty * (price - cost)
        return sales_list

    all_sales = enrich(all_sales)
    day_sales = enrich(day_sales)

    total_revenue = sum(float(s.get('total_amount', 0)) for s in day_sales)
    total_profit  = sum(
        sum(float(i.get('line_profit', 0)) for i in s.get('items', []))
        for s in day_sales
    )

    breakdown = {'cash': 0.0, 'mpesa': 0.0, 'credit': 0.0}
    for s in day_sales:
        method = s.get('payment_method', 'cash').lower()
        breakdown[method] = breakdown.get(method, 0.0) + float(s.get('total_amount', 0))

    try:
        low_stock = list(current_app.db.products.find({
            **query,
            "$expr": {"$lt": ["$current_quantity", {"$ifNull": ["$min_stock", 5]}]}
        }).sort("current_quantity", 1))
    except Exception:
        low_stock = []

    grouped = group_by_business(all_sales, current_app.db) if is_super_admin else None

    return render_template('sales.html',
                           sales=all_sales,
                           grouped=grouped,
                           is_super_admin=is_super_admin,
                           day_sales=day_sales,
                           selected_date=selected_date.strftime('%Y-%m-%d'),
                           selected_date_display=selected_date.strftime('%d %B %Y'),
                           printed_at=datetime.utcnow().strftime('%d %b %Y %H:%M'),
                           total_revenue=total_revenue,
                           total_profit=round(total_profit, 2),
                           breakdown=breakdown,
                           low_stock=low_stock)


# ── Excel export ──────────────────────────────────────────────────────────────
@bp.route('/export')
def export():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    query = get_business_query()
    all_sales = list(current_app.db.sales.find(query).sort("date", -1))
    products  = {str(p['_id']): p for p in current_app.db.products.find(query)}

    for sale in all_sales:
        for item in sale.get('items', []):
            pid = str(item.get('product_id', ''))
            item['product_name'] = products.get(pid, {}).get('name', 'Unknown')

    return export_sales(all_sales)