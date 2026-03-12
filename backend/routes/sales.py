from flask import Blueprint, render_template, redirect, url_for, session, current_app, request
from bson.objectid import ObjectId
from datetime import datetime, timedelta

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

    # ── Date filter ──────────────────────────────────────────
    date_str = request.args.get('date', '')
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            selected_date = datetime.utcnow()
    else:
        selected_date = datetime.utcnow()

    day_start = selected_date.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    day_end   = selected_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    # All-time sales (for history table)
    all_sales = list(current_app.db.sales.find(query).sort("date", -1))

    # Day-filtered sales (for daily report)
    day_query = {**query, "date": {"$gte": day_start, "$lte": day_end}}
    day_sales = list(current_app.db.sales.find(day_query).sort("date", 1))

    # ── Enrich product names ──────────────────────────────────
    products = {str(p['_id']): p for p in current_app.db.products.find(query)}

    def enrich(sales_list):
        for sale in sales_list:
            for item in sale.get('items', []):
                pid = str(item.get('product_id', ''))
                product = products.get(pid, {})
                item['product_name']  = product.get('name', 'Unknown')
                item['purchase_price'] = product.get('purchase_price', 0)
                item['line_total']    = item.get('quantity', 0) * item.get('selling_price', 0)
                item['line_profit']   = item.get('quantity', 0) * (
                    item.get('selling_price', 0) - item.get('purchase_price', 0)
                )
        return sales_list

    all_sales = enrich(all_sales)
    day_sales = enrich(day_sales)

    # ── Daily report stats ────────────────────────────────────
    total_revenue = sum(s.get('total_amount', 0) for s in day_sales)
    total_profit  = sum(
        sum(i.get('line_profit', 0) for i in s.get('items', []))
        for s in day_sales
    )

    # Payment method breakdown
    breakdown = {'cash': 0.0, 'mpesa': 0.0, 'credit': 0.0}
    for s in day_sales:
        method = s.get('payment_method', 'cash').lower()
        breakdown[method] = breakdown.get(method, 0) + s.get('total_amount', 0)

    # Low stock alerts (threshold: current_quantity < min_stock or < 5)
    low_stock = list(current_app.db.products.find({
        **query,
        "$expr": {"$lt": ["$current_quantity", {"$ifNull": ["$min_stock", 5]}]}
    }).sort("current_quantity", 1))

    grouped = group_by_business(all_sales, current_app.db) if is_super_admin else None

    return render_template('sales.html',
                           sales=all_sales,
                           grouped=grouped,
                           is_super_admin=is_super_admin,
                           # Daily report
                           day_sales=day_sales,
                           selected_date=selected_date.strftime('%Y-%m-%d'),
                           selected_date_display=selected_date.strftime('%d %B %Y'),
                           total_revenue=total_revenue,
                           total_profit=round(total_profit, 2),
                           breakdown=breakdown,
                           low_stock=low_stock)