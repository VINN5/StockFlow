from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from bson.objectid import ObjectId
from datetime import datetime

bp = Blueprint('payments', __name__, url_prefix='/payments')

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
    payments = list(current_app.db.payments.find(query).sort("date", -1))
    
    
    client_ids = {p['client_id'] for p in payments if 'client_id' in p}
    clients = {}
    if client_ids:
        clients = {str(c['_id']): c['name'] for c in current_app.db.clients.find({"_id": {"$in": list(client_ids)}})}
    
    for payment in payments:
        payment['client_name'] = clients.get(str(payment['client_id']), 'Unknown')
    
    return render_template('payments.html', payments=payments)

@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        client_id = ObjectId(request.form['client_id'])
        amount = float(request.form['amount'])
        method = request.form.get('method', 'Cash')
    except:
        flash('Invalid input', 'danger')
        return redirect(url_for('payments.index'))
    
    if amount <= 0:
        flash('Amount must be greater than zero', 'danger')
        return redirect(url_for('payments.index'))
    
    
    result = current_app.db.clients.update_one(
        {"_id": client_id},
        {"$inc": {"balance": -amount}}
    )
    
    if result.modified_count == 0:
        flash('Client not found or no change', 'danger')
        return redirect(url_for('payments.index'))
    
    
    payment = {
        "client_id": client_id,
        "amount": amount,
        "method": method,
        "date": datetime.utcnow(),
        "recorded_by": session['username']
    }
    
    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            payment['business_id'] = ObjectId(business_id)
    
    current_app.db.payments.insert_one(payment)
    flash(f'Payment of KSh {amount:.2f} from client recorded!', 'success')
    return redirect(url_for('payments.index'))

@bp.route('/new')
def new():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    query = get_business_query()
    clients = list(current_app.db.clients.find(query).sort("name", 1))
    return render_template('payment_new.html', clients=clients)