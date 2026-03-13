from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from bson.objectid import ObjectId
from datetime import datetime
from .excel_io import export_clients, import_clients, resolve_client_duplicate
import json

bp = Blueprint('clients', __name__, url_prefix='/clients')


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


def get_business_id_obj():
    if session.get('role') == 'super_admin':
        return None
    bid = session.get('business_id')
    try:
        return ObjectId(bid) if bid else None
    except Exception:
        return None


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
    clients = list(current_app.db.clients.find(query).sort("name", 1))
    grouped = group_by_business(clients, current_app.db) if is_super_admin else None

    pending = session.pop('import_duplicates', None)
    import_summary = session.pop('import_summary', None)

    return render_template('clients.html',
                           clients=clients,
                           grouped=grouped,
                           is_super_admin=is_super_admin,
                           pending_duplicates=pending,
                           import_summary=import_summary)


@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    name = request.form['name'].strip()
    if not name:
        flash('Client name is required', 'danger')
        return redirect(url_for('clients.index'))

    client_data = {
        "name": name,
        "contact": request.form.get('contact', '').strip(),
        "kra_pin": request.form.get('kra_pin', '').strip(),
        "balance": 0.0,
        "created_at": datetime.utcnow()
    }
    bid_obj = get_business_id_obj()
    if bid_obj:
        client_data['business_id'] = bid_obj

    current_app.db.clients.insert_one(client_data)
    flash('Client added successfully!', 'success')
    return redirect(url_for('clients.index'))


# ── Excel export ──────────────────────────────────────────────────────────────
@bp.route('/export')
def export():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    clients = list(current_app.db.clients.find(get_business_query()).sort("name", 1))
    return export_clients(clients)


# ── Excel import ──────────────────────────────────────────────────────────────
@bp.route('/import', methods=['POST'])
def import_excel():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file = request.files.get('excel_file')
    if not file or not file.filename.endswith('.xlsx'):
        flash('Please upload a valid .xlsx file', 'danger')
        return redirect(url_for('clients.index'))

    bid_obj = get_business_id_obj()
    inserted, duplicates, errors = import_clients(file, current_app.db, bid_obj)

    summary = {'inserted': inserted, 'errors': errors}
    if duplicates:
        session['import_duplicates'] = duplicates
        session['import_summary'] = summary
        flash(f'Import paused: {len(duplicates)} duplicate(s) found. Review below — balance is never overwritten.', 'warning')
    else:
        flash(f'Import complete: {len(inserted)} added, {len(errors)} error(s).', 'success' if not errors else 'warning')
        for e in errors:
            flash(e, 'danger')

    return redirect(url_for('clients.index'))


@bp.route('/import/resolve', methods=['POST'])
def resolve_duplicates():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    overwritten = skipped = 0
    for key, action in request.form.items():
        if key.startswith('action_'):
            existing_id = key[len('action_'):]
            try:
                data = json.loads(request.form.get(f'data_{existing_id}', '{}'))
            except Exception:
                continue
            if resolve_client_duplicate(current_app.db, existing_id, data, action):
                overwritten += 1
            else:
                skipped += 1

    flash(f'Duplicates resolved: {overwritten} updated, {skipped} skipped.', 'success')
    return redirect(url_for('clients.index'))