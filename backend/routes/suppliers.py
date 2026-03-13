from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app as app, jsonify
from ..models.supplier import Supplier
from bson.objectid import ObjectId
from datetime import datetime
from .excel_io import export_suppliers, import_suppliers, resolve_supplier_duplicate
import json

bp = Blueprint('suppliers', __name__, url_prefix='/suppliers')


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
    suppliers = list(app.db.suppliers.find(query))
    grouped = group_by_business(suppliers, app.db) if is_super_admin else None

    pending = session.pop('import_duplicates', None)
    import_summary = session.pop('import_summary', None)

    return render_template('suppliers.html',
                           suppliers=suppliers,
                           grouped=grouped,
                           is_super_admin=is_super_admin,
                           pending_duplicates=pending,
                           import_summary=import_summary)


def build_supplier_dict(name, contact_person, phone, email, address):
    supplier = Supplier(name=name, contact_person=contact_person,
                        phone=phone, email=email, address=address)
    data = supplier.to_dict()
    bid_obj = get_business_id_obj()
    if bid_obj:
        data['business_id'] = bid_obj
    return data


@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.is_json:
        body = request.get_json()
        supplier_dict = build_supplier_dict(
            name=body['name'],
            contact_person=body.get('contact_person', ''),
            phone=body.get('phone', ''),
            email=body.get('email', ''),
            address=body.get('address', '')
        )
        result = app.db.suppliers.insert_one(supplier_dict)
        return jsonify({'success': True, 'message': 'Supplier added successfully!',
                        'supplier_id': str(result.inserted_id)})

    supplier_dict = build_supplier_dict(
        name=request.form['name'],
        contact_person=request.form.get('contact_person', ''),
        phone=request.form.get('phone', ''),
        email=request.form.get('email', ''),
        address=request.form.get('address', '')
    )
    app.db.suppliers.insert_one(supplier_dict)
    flash('Supplier added successfully!', 'success')
    return redirect(url_for('suppliers.index'))


@bp.route('/edit/<supplier_id>', methods=['GET', 'POST'])
def edit(supplier_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        obj_id = ObjectId(supplier_id)
    except Exception:
        flash('Invalid supplier ID', 'danger')
        return redirect(url_for('suppliers.index'))

    query = {"_id": obj_id, **get_business_query()}
    supplier = app.db.suppliers.find_one(query)
    if not supplier:
        flash('Supplier not found or access denied', 'danger')
        return redirect(url_for('suppliers.index'))

    if request.method == 'POST':
        updated = {
            "name": request.form['name'],
            "contact_person": request.form.get('contact_person', ''),
            "phone": request.form.get('phone', ''),
            "email": request.form.get('email', ''),
            "address": request.form.get('address', '')
        }
        app.db.suppliers.update_one(query, {"$set": updated})
        flash('Supplier updated successfully!', 'success')
        return redirect(url_for('suppliers.index'))

    return render_template('supplier_edit.html', supplier=supplier)


@bp.route('/delete/<supplier_id>')
def delete(supplier_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        obj_id = ObjectId(supplier_id)
    except Exception:
        flash('Invalid supplier ID', 'danger')
        return redirect(url_for('suppliers.index'))

    query = {"_id": obj_id, **get_business_query()}
    result = app.db.suppliers.delete_one(query)
    flash('Supplier deleted' if result.deleted_count else 'Supplier not found or access denied',
          'info' if result.deleted_count else 'danger')
    return redirect(url_for('suppliers.index'))


# ── Excel export ──────────────────────────────────────────────────────────────
@bp.route('/export')
def export():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    suppliers = list(app.db.suppliers.find(get_business_query()))
    return export_suppliers(suppliers)


# ── Excel import ──────────────────────────────────────────────────────────────
@bp.route('/import', methods=['POST'])
def import_excel():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file = request.files.get('excel_file')
    if not file or not file.filename.endswith('.xlsx'):
        flash('Please upload a valid .xlsx file', 'danger')
        return redirect(url_for('suppliers.index'))

    bid_obj = get_business_id_obj()
    inserted, duplicates, errors = import_suppliers(file, app.db, bid_obj)

    summary = {'inserted': inserted, 'errors': errors}
    if duplicates:
        session['import_duplicates'] = duplicates
        session['import_summary'] = summary
        flash(f'Import paused: {len(duplicates)} duplicate(s) found. Please review below.', 'warning')
    else:
        flash(f'Import complete: {len(inserted)} added, {len(errors)} error(s).', 'success' if not errors else 'warning')
        for e in errors:
            flash(e, 'danger')

    return redirect(url_for('suppliers.index'))


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
            if resolve_supplier_duplicate(app.db, existing_id, data, action):
                overwritten += 1
            else:
                skipped += 1

    flash(f'Duplicates resolved: {overwritten} updated, {skipped} skipped.', 'success')
    return redirect(url_for('suppliers.index'))