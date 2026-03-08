from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app as app, jsonify
from ..models.supplier import Supplier
from bson.objectid import ObjectId
from datetime import datetime  

bp = Blueprint('suppliers', __name__, url_prefix='/suppliers')


def get_business_query():
    """Return MongoDB query filter for business_id based on user role"""
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
    suppliers = list(app.db.suppliers.find(query))
    return render_template('suppliers.html', suppliers=suppliers)


@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Build the supplier dict and inject business_id
    def build_supplier_dict(name, contact_person, phone, email, address):
        supplier = Supplier(
            name=name,
            contact_person=contact_person,
            phone=phone,
            email=email,
            address=address
        )
        data = supplier.to_dict()
        # Attach business_id for non-super_admin
        if session.get('role') != 'super_admin':
            business_id = session.get('business_id')
            if business_id:
                try:
                    data['business_id'] = ObjectId(business_id)
                except:
                    pass
        return data

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
        return jsonify({
            'success': True,
            'message': 'Supplier added successfully!',
            'supplier_id': str(result.inserted_id)
        })

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
    except:
        flash('Invalid supplier ID', 'danger')
        return redirect(url_for('suppliers.index'))

    # Enforce business ownership on lookup
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
        # Use the ownership query to prevent editing another business's supplier
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
    except:
        flash('Invalid supplier ID', 'danger')
        return redirect(url_for('suppliers.index'))

    # Enforce business ownership on delete
    query = {"_id": obj_id, **get_business_query()}
    result = app.db.suppliers.delete_one(query)
    if result.deleted_count:
        flash('Supplier deleted', 'info')
    else:
        flash('Supplier not found or access denied', 'danger')
    return redirect(url_for('suppliers.index'))