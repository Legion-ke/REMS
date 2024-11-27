from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Property, Rental, Maintenance
from extensions import db
from datetime import datetime

property = Blueprint('property', __name__, url_prefix='/property')

@property.route('/list')
def list_properties():
    # Show all available properties for clients
    if current_user.is_authenticated and current_user.role == 'client':
        properties = Property.query.filter_by(status='available').all()
    # Show all properties for agents (including their own)
    elif current_user.is_authenticated and current_user.role == 'agent':
        properties = Property.query.filter_by(agent_id=current_user.id).all()
    # Show all available properties for non-logged in users
    else:
        properties = Property.query.filter_by(status='available').all()
    
    return render_template('property/list.html', properties=properties)

@property.route('/add', methods=['GET', 'POST'])
@login_required
def add_property():
    if current_user.role not in ['admin', 'agent']:
        flash('Unauthorized access')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        try:
            # Get form values
            rent_amount = request.form.get('rent_amount', '').strip()
            bedrooms = request.form.get('bedrooms', '').strip()
            bathrooms = request.form.get('bathrooms', '').strip()
            
            # Validate rent amount
            if not rent_amount or float(rent_amount) <= 0:
                flash('Please enter a valid rent amount (e.g., 25000 for KES 25,000 per month)')
                return redirect(url_for('property.add_property'))
            
            # Validate bedrooms
            if not bedrooms or not bedrooms.isdigit() or int(bedrooms) < 0:
                flash('Please enter a valid number of bedrooms (e.g., 2 for a 2-bedroom property)')
                return redirect(url_for('property.add_property'))
                
            # Validate bathrooms
            if not bathrooms or float(bathrooms) < 0:
                flash('Please enter a valid number of bathrooms (e.g., 1.5 for one and a half bathrooms)')
                return redirect(url_for('property.add_property'))
                
            new_property = Property(
                title=request.form.get('name'),
                description=request.form.get('description'),
                address=request.form.get('address'),
                price=float(rent_amount),
                bedrooms=int(bedrooms),
                bathrooms=float(bathrooms),
                status='available',
                agent_id=current_user.id,  # Set the agent_id since it's required
                owner_id=current_user.id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(new_property)
            db.session.commit()
            
            flash('Property added successfully')
            return redirect(url_for('property.list_properties'))
        except ValueError:
            flash('Invalid input. Examples of valid values:\n'
                  '- Rent Amount: 25000 (for KES 25,000)\n'
                  '- Bedrooms: 2 (for 2 bedrooms)\n'
                  '- Bathrooms: 1.5 (for one and a half bathrooms)')
            return redirect(url_for('property.add_property'))
    
    return render_template('property/add.html')

@property.route('/<int:id>')
def view_property(id):
    property_item = Property.query.get_or_404(id)
    return render_template('property/view.html', property=property_item)

@property.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_property(id):
    property_item = Property.query.get_or_404(id)
    
    if current_user.role not in ['admin', 'agent'] or property_item.owner_id != current_user.id:
        flash('Unauthorized access')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        try:
            # Get form values
            rent_amount = request.form.get('rent_amount', '').strip()
            bedrooms = request.form.get('bedrooms', '').strip()
            bathrooms = request.form.get('bathrooms', '').strip()
            
            # Validate rent amount
            if not rent_amount or float(rent_amount) <= 0:
                flash('Please enter a valid rent amount (e.g., 25000 for KES 25,000 per month)')
                return redirect(url_for('property.edit_property', id=id))
            
            # Validate bedrooms
            if not bedrooms or not bedrooms.isdigit() or int(bedrooms) < 0:
                flash('Please enter a valid number of bedrooms (e.g., 2 for a 2-bedroom property)')
                return redirect(url_for('property.edit_property', id=id))
                
            # Validate bathrooms
            if not bathrooms or float(bathrooms) < 0:
                flash('Please enter a valid number of bathrooms (e.g., 1.5 for one and a half bathrooms)')
                return redirect(url_for('property.edit_property', id=id))
            
            # Update property fields
            property_item.title = request.form.get('name')
            property_item.description = request.form.get('description')
            property_item.address = request.form.get('address')
            property_item.price = float(rent_amount)
            property_item.bedrooms = int(bedrooms)
            property_item.bathrooms = float(bathrooms)
            property_item.status = request.form.get('status')
            
            db.session.commit()
            flash('Property updated successfully')
            return redirect(url_for('property.view_property', id=id))
        except ValueError:
            flash('Invalid input. Examples of valid values:\n'
                  '- Rent Amount: 25000 (for KES 25,000)\n'
                  '- Bedrooms: 2 (for 2 bedrooms)\n'
                  '- Bathrooms: 1.5 (for one and a half bathrooms)')
            return redirect(url_for('property.edit_property', id=id))
    
    return render_template('property/edit.html', property=property_item)

@property.route('/maintenance', defaults={'id': None})
@property.route('/<int:id>/maintenance', methods=['GET', 'POST'])
@login_required
def report_maintenance(id):
    if id is None:
        # Show list of properties the client is renting
        rentals = Rental.query.filter_by(
            tenant_id=current_user.id,
            status='active'
        ).all()
        
        properties = []
        for rental in rentals:
            properties.append({
                'property': rental.property,
                'rental': rental,
                'maintenance_count': Maintenance.query.filter_by(
                    property_id=rental.property_id,
                    status='pending'
                ).count()
            })
        
        return render_template('property/maintenance_select.html', properties=properties)
    
    property_item = Property.query.get_or_404(id)
    rental = Rental.query.filter_by(property_id=id, tenant_id=current_user.id, status='active').first()
    
    if not rental:
        flash('You can only report maintenance for properties you are currently renting')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        new_maintenance = Maintenance(
            property_id=id,
            reported_by=current_user.id,
            issue=request.form.get('issue'),
            priority=request.form.get('priority'),
            status='pending',
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_maintenance)
        db.session.commit()
        
        flash('Maintenance request submitted successfully')
        return redirect(url_for('property.view_property', id=id))
    
    return render_template('property/maintenance.html', property=property_item)
