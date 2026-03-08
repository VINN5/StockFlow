from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from functools import wraps

from .services import send_stk_push, send_sms, build_whatsapp_link, build_payment_message

bp = Blueprint('payments', __name__, url_prefix='/payments')


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


def require_admin(f):
    """Decorator: branch admins only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Access denied: Branch Admin only', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────
#  EXISTING ROUTES
# ─────────────────────────────────────────────────────────

@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    is_super_admin = session.get('role') == 'super_admin'
    query = get_business_query()
    payments = list(current_app.db.payments.find(query).sort("date", -1))

    client_ids = {p['client_id'] for p in payments if 'client_id' in p}
    clients = {}
    if client_ids:
        clients = {str(c['_id']): c['name']
                   for c in current_app.db.clients.find({"_id": {"$in": list(client_ids)}})}
    for payment in payments:
        payment['client_name'] = clients.get(str(payment.get('client_id', '')), 'Unknown')

    grouped = group_by_business(payments, current_app.db) if is_super_admin else None

    return render_template('payments.html',
                           payments=payments,
                           grouped=grouped,
                           is_super_admin=is_super_admin)


@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        client_id = ObjectId(request.form['client_id'])
        amount    = float(request.form['amount'])
        method    = request.form.get('method', 'Cash')
    except Exception:
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
    flash(f'Payment of KSh {amount:.2f} recorded successfully!', 'success')
    return redirect(url_for('payments.index'))


@bp.route('/new')
def new():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    query = get_business_query()
    clients = list(current_app.db.clients.find(query).sort("name", 1))
    return render_template('payment_new.html', clients=clients)


# ─────────────────────────────────────────────────────────
#  PAYMENT REQUEST ROUTES
# ─────────────────────────────────────────────────────────

@bp.route('/request/<client_id>')
@require_admin
def request_payment(client_id):
    """Show the payment request page for a specific client."""
    try:
        obj_id = ObjectId(client_id)
    except Exception:
        flash('Invalid client ID', 'danger')
        return redirect(url_for('clients.index'))

    client = current_app.db.clients.find_one({"_id": obj_id, **get_business_query()})
    if not client:
        flash('Client not found or access denied', 'danger')
        return redirect(url_for('clients.index'))

    if client.get('balance', 0) <= 0:
        flash(f'{client["name"]} has no outstanding balance.', 'info')
        return redirect(url_for('clients.index'))

    # Fetch this client's credit sales
    credit_sales = list(current_app.db.sales.find({
        "client_id": obj_id,
        "payment_method": "credit",
        **get_business_query()
    }).sort("date", -1))

    # Enrich each sale with product names
    for sale in credit_sales:
        enriched = []
        for item in sale.get('items', []):
            try:
                product = current_app.db.products.find_one({"_id": ObjectId(item['product_id'])})
            except Exception:
                product = None
            enriched.append({
                'product_name': product['name'] if product else 'Unknown',
                'quantity': item.get('quantity', 0),
                'selling_price': item.get('selling_price', 0),
                'line_total': item.get('quantity', 0) * item.get('selling_price', 0)
            })
        sale['enriched_items'] = enriched

    due_date = (datetime.utcnow() + timedelta(days=7)).strftime('%d %b %Y')

    # Pre-build WhatsApp link if client has a phone number
    wa_link = None
    if client.get('contact'):
        message = build_payment_message(
            client_name=client['name'],
            business_name=session.get('business_name', 'Our Business'),
            balance=client.get('balance', 0),
            due_date=due_date,
            credit_sales=credit_sales
        )
        wa_link = build_whatsapp_link(client['contact'], message)

    return render_template('payment_request.html',
                           client=client,
                           credit_sales=credit_sales,
                           due_date=due_date,
                           wa_link=wa_link,
                           business_name=session.get('business_name', 'StockFlow'))


@bp.route('/request/<client_id>/sms', methods=['POST'])
@require_admin
def send_payment_sms(client_id):
    """Send SMS payment reminder via Africa's Talking."""
    try:
        obj_id = ObjectId(client_id)
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid client ID'}), 400

    client = current_app.db.clients.find_one({"_id": obj_id, **get_business_query()})
    if not client:
        return jsonify({'success': False, 'message': 'Client not found'}), 404

    if not client.get('contact'):
        return jsonify({'success': False, 'message': 'Client has no phone number on record'}), 400

    data = request.get_json() or {}
    due_date = data.get('due_date', (datetime.utcnow() + timedelta(days=7)).strftime('%d %b %Y'))

    credit_sales = list(current_app.db.sales.find({
        "client_id": obj_id,
        "payment_method": "credit",
        **get_business_query()
    }).sort("date", -1))

    message = build_payment_message(
        client_name=client['name'],
        business_name=session.get('business_name', 'StockFlow'),
        balance=client.get('balance', 0),
        due_date=due_date,
        credit_sales=credit_sales
    )

    success, msg = send_sms(client['contact'], message, current_app.config)

    if success:
        current_app.db.payment_reminders.insert_one({
            "client_id": obj_id,
            "method": "sms",
            "amount": client.get('balance', 0),
            "due_date": due_date,
            "sent_by": session['username'],
            "sent_at": datetime.utcnow(),
            "business_id": ObjectId(session['business_id']) if session.get('business_id') else None
        })

    return jsonify({'success': success, 'message': msg})


@bp.route('/request/<client_id>/stk', methods=['POST'])
@require_admin
def send_stk(client_id):
    """Initiate M-Pesa STK Push to client's phone."""
    try:
        obj_id = ObjectId(client_id)
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid client ID'}), 400

    client = current_app.db.clients.find_one({"_id": obj_id, **get_business_query()})
    if not client:
        return jsonify({'success': False, 'message': 'Client not found'}), 404

    if not client.get('contact'):
        return jsonify({'success': False, 'message': 'Client has no phone number on record'}), 400

    data = request.get_json() or {}
    try:
        amount = float(data.get('amount', client.get('balance', 0)))
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid amount'}), 400

    if amount <= 0:
        return jsonify({'success': False, 'message': 'Amount must be greater than zero'}), 400

    success, msg, resp_data = send_stk_push(
        phone=client['contact'],
        amount=amount,
        account_ref=client['name'],
        description='Balance Payment',
        config=current_app.config
    )

    if success:
        current_app.db.payment_reminders.insert_one({
            "client_id": obj_id,
            "method": "stk_push",
            "amount": amount,
            "checkout_request_id": resp_data.get('CheckoutRequestID'),
            "sent_by": session['username'],
            "sent_at": datetime.utcnow(),
            "status": "pending",
            "business_id": ObjectId(session['business_id']) if session.get('business_id') else None
        })

    return jsonify({'success': success, 'message': msg})


@bp.route('/mpesa/callback', methods=['POST'])
def mpesa_callback():
    """Receive M-Pesa STK callback and update client balance automatically."""
    data = request.get_json(silent=True) or {}
    try:
        body        = data['Body']['stkCallback']
        checkout_id = body.get('CheckoutRequestID')
        result_code = body.get('ResultCode')
        status      = 'completed' if result_code == 0 else 'failed'

        current_app.db.payment_reminders.update_one(
            {"checkout_request_id": checkout_id},
            {"$set": {"status": status, "callback_data": body}}
        )

        if result_code == 0:
            metadata = body.get('CallbackMetadata', {}).get('Item', [])
            amount = next((i['Value'] for i in metadata if i['Name'] == 'Amount'), None)
            phone  = next((i['Value'] for i in metadata if i['Name'] == 'PhoneNumber'), None)

            if amount and phone:
                phone_str = str(phone)
                if phone_str.startswith('254'):
                    phone_str = '0' + phone_str[3:]
                client = current_app.db.clients.find_one({"contact": phone_str})
                if client:
                    current_app.db.clients.update_one(
                        {"_id": client['_id']},
                        {"$inc": {"balance": -float(amount)}}
                    )
                    current_app.db.payments.insert_one({
                        "client_id": client['_id'],
                        "amount": float(amount),
                        "method": "M-Pesa STK",
                        "date": datetime.utcnow(),
                        "recorded_by": "system (STK Push)",
                        "business_id": client.get('business_id')
                    })
    except Exception as e:
        current_app.logger.error(f'M-Pesa callback error: {e}')

    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})