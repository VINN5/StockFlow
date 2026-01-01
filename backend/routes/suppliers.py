from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app as app, jsonify
from ..models.supplier import Supplier
from bson.objectid import ObjectId
from datetime import datetime  

bp = Blueprint('suppliers', __name__, url_prefix='/suppliers')

@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    suppliers = list(app.db.suppliers.find())
    return render_template('suppliers.html', suppliers=suppliers)


@bp.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    
    if request.is_json:
        data = request.get_json()
        supplier = Supplier(
            name=data['name'],
            contact_person=data.get('contact_person', ''),
            phone=data.get('phone', ''),
            email=data.get('email', ''),
            address=data.get('address', '')
        )
        result = app.db.suppliers.insert_one(supplier.to_dict())
        return jsonify({
            'success': True,
            'message': 'Supplier added successfully!',
            'supplier_id': str(result.inserted_id)
        })
    
    
    supplier = Supplier(
        name=request.form['name'],
        contact_person=request.form.get('contact_person', ''),
        phone=request.form.get('phone', ''),
        email=request.form.get('email', ''),
        address=request.form.get('address', '')
    )
    app.db.suppliers.insert_one(supplier.to_dict())
    flash('Supplier added successfully!', 'success')
    return redirect(url_for('suppliers.index'))

@bp.route('/edit/<supplier_id>', methods=['GET', 'POST'])
def edit(supplier_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    supplier = app.db.suppliers.find_one({"_id": ObjectId(supplier_id)})
    if not supplier:
        flash('Supplier not found', 'danger')
        return redirect(url_for('suppliers.index'))
    
    if request.method == 'POST':
        updated = {
            "name": request.form['name'],
            "contact_person": request.form.get('contact_person', ''),
            "phone": request.form.get('phone', ''),
            "email": request.form.get('email', ''),
            "address": request.form.get('address', '')
        }
        app.db.suppliers.update_one({"_id": ObjectId(supplier_id)}, {"$set": updated})
        flash('Supplier updated successfully!', 'success')
        return redirect(url_for('suppliers.index'))
    
    return render_template('supplier_edit.html', supplier=supplier)

@bp.route('/delete/<supplier_id>')
def delete(supplier_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    app.db.suppliers.delete_one({"_id": ObjectId(supplier_id)})
    flash('Supplier deleted', 'info')
    return redirect(url_for('suppliers.index'))