from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from bson.objectid import ObjectId
from datetime import datetime
from .excel_io import export_products, import_products, resolve_product_duplicate
import json

bp = Blueprint('products', __name__, url_prefix='/products')


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
    products = list(current_app.db.products.find(query).sort("name", 1))
    grouped = group_by_business(products, current_app.db) if is_super_admin else None

    # Pull pending duplicates from session
    pending = session.pop('import_duplicates', None)
    import_summary = session.pop('import_summary', None)

    return render_template('products.html',
                           products=products,
                           grouped=grouped,
                           is_super_admin=is_super_admin,
                           pending_duplicates=pending,
                           import_summary=import_summary)


@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        purchase_price   = float(request.form['purchase_price'])
        selling_price    = float(request.form['selling_price'])
        min_stock        = int(request.form['min_stock'])
        current_quantity = int(request.form.get('current_quantity', 0))
        max_stock        = int(request.form.get('max_stock')) if request.form.get('max_stock') else None
    except ValueError:
        flash('Invalid number format', 'danger')
        return redirect(url_for('products.index'))

    product_data = {
        "name": request.form['name'].strip(),
        "description": request.form.get('description', '').strip(),
        "unit": request.form['unit'],
        "purchase_price": purchase_price,
        "selling_price": selling_price,
        "min_stock": min_stock,
        "max_stock": max_stock,
        "current_quantity": current_quantity,
        "created_at": datetime.utcnow()
    }
    bid_obj = get_business_id_obj()
    if bid_obj:
        product_data['business_id'] = bid_obj

    current_app.db.products.insert_one(product_data)
    flash('Product added successfully!', 'success')
    return redirect(url_for('products.index'))


@bp.route('/edit/<product_id>', methods=['GET', 'POST'])
def edit(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        obj_id = ObjectId(product_id)
    except Exception:
        flash('Invalid product ID', 'danger')
        return redirect(url_for('products.index'))

    query = {"_id": obj_id}
    bid_obj = get_business_id_obj()
    if bid_obj:
        query['business_id'] = bid_obj

    product = current_app.db.products.find_one(query)
    if not product:
        flash('Product not found or access denied', 'danger')
        return redirect(url_for('products.index'))

    if request.method == 'POST':
        try:
            updated = {
                "name": request.form['name'].strip(),
                "description": request.form.get('description', '').strip(),
                "unit": request.form['unit'],
                "purchase_price": float(request.form['purchase_price']),
                "selling_price": float(request.form['selling_price']),
                "min_stock": int(request.form['min_stock']),
                "max_stock": int(request.form.get('max_stock')) if request.form.get('max_stock') else None,
                "current_quantity": int(request.form.get('current_quantity', product.get('current_quantity', 0)))
            }
            current_app.db.products.update_one({"_id": obj_id}, {"$set": updated})
            flash('Product updated successfully!', 'success')
        except ValueError as e:
            flash(f'Invalid number format: {e}', 'danger')
        except Exception:
            flash('Update failed', 'danger')
        return redirect(url_for('products.index'))

    return render_template('product_edit.html', product=product)


@bp.route('/delete/<product_id>')
def delete(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        obj_id = ObjectId(product_id)
    except Exception:
        flash('Invalid product ID', 'danger')
        return redirect(url_for('products.index'))

    query = {"_id": obj_id}
    bid_obj = get_business_id_obj()
    if bid_obj:
        query['business_id'] = bid_obj

    result = current_app.db.products.delete_one(query)
    flash('Product deleted' if result.deleted_count else 'Product not found or access denied',
          'info' if result.deleted_count else 'danger')
    return redirect(url_for('products.index'))


# ── Excel export ──────────────────────────────────────────────────────────────
@bp.route('/export')
def export():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    query = get_business_query()
    products = list(current_app.db.products.find(query).sort("name", 1))
    return export_products(products)


# ── Excel import ──────────────────────────────────────────────────────────────
@bp.route('/import', methods=['POST'])
def import_excel():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file = request.files.get('excel_file')
    if not file or not file.filename.endswith('.xlsx'):
        flash('Please upload a valid .xlsx file', 'danger')
        return redirect(url_for('products.index'))

    bid_obj = get_business_id_obj()
    inserted, updated, duplicates, errors = import_products(file, current_app.db, bid_obj)

    summary = {
        'inserted': inserted,
        'errors': errors,
        'total': len(inserted) + len(duplicates) + len(errors)
    }

    if duplicates:
        # Store duplicates in session for the confirmation modal
        session['import_duplicates'] = duplicates
        session['import_summary'] = summary
        flash(f'Import paused: {len(duplicates)} duplicate(s) found. Please review below.', 'warning')
    else:
        flash(f'Import complete: {len(inserted)} added, {len(errors)} error(s).', 'success' if not errors else 'warning')
        if errors:
            for e in errors:
                flash(e, 'danger')

    return redirect(url_for('products.index'))


@bp.route('/import/resolve', methods=['POST'])
def resolve_duplicates():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    bid_obj = get_business_id_obj()
    overwritten = 0
    skipped = 0

    # Each duplicate sends action_<existing_id> = overwrite|skip
    for key, action in request.form.items():
        if key.startswith('action_'):
            existing_id = key[len('action_'):]
            data_key = f'data_{existing_id}'
            data_raw = request.form.get(data_key, '{}')
            try:
                data = json.loads(data_raw)
            except Exception:
                continue
            result = resolve_product_duplicate(current_app.db, existing_id, data, bid_obj, action)
            if result:
                overwritten += 1
            else:
                skipped += 1

    flash(f'Duplicates resolved: {overwritten} updated, {skipped} skipped.', 'success')
    return redirect(url_for('products.index'))