from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from bson.objectid import ObjectId
from datetime import datetime

bp = Blueprint('clients', __name__, url_prefix='/clients')

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
    clients = list(current_app.db.clients.find(query).sort("name", 1))
    return render_template('clients.html', clients=clients)

@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    name = request.form['name'].strip()
    contact = request.form.get('contact', '').strip()
    kra_pin = request.form.get('kra_pin', '').strip()
    
    if not name:
        flash('Client name is required', 'danger')
        return redirect(url_for('clients.index'))
    
    client_data = {
        "name": name,
        "contact": contact,
        "kra_pin": kra_pin,
        "balance": 0.0,
        "created_at": datetime.utcnow()
    }
    
    if session.get('role') != 'super_admin':
        business_id = session.get('business_id')
        if business_id:
            client_data['business_id'] = ObjectId(business_id)
    
    current_app.db.clients.insert_one(client_data)
    flash('Client added successfully!', 'success')
    return redirect(url_for('clients.index'))