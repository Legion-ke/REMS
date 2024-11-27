from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from models import Property, Rental, Maintenance, Payment
from extensions import db
from sqlalchemy import func
from datetime import datetime, timedelta

main = Blueprint('main', __name__, url_prefix='/')

@main.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'client':
            return redirect(url_for('client.dashboard'))
        elif current_user.role in ['admin', 'agent']:
            return redirect(url_for('agent.dashboard'))
    return render_template('index.html')

@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        properties = Property.query.all()
        rentals = Rental.query.all()
        payments = Payment.query.all()
        return render_template('dashboard/admin.html', 
                             properties=properties,
                             rentals=rentals,
                             payments=payments)
    elif current_user.role == 'agent':
        properties = Property.query.filter_by(owner_id=current_user.id).all()
        return render_template('dashboard/agent.html', properties=properties)
    else:
        rentals = Rental.query.filter_by(tenant_id=current_user.id).all()
        return render_template('dashboard/tenant.html', rentals=rentals)

@main.route('/profile')
@login_required
def profile():
    if current_user.role in ['admin', 'agent']:
        # Get property statistics for admin/agent
        properties = Property.query.filter_by(owner_id=current_user.id).all()
        properties_count = len(properties)
        available_count = sum(1 for p in properties if p.status == 'available')
        rented_count = sum(1 for p in properties if p.status == 'rented')
        
        # Initialize client-specific variables
        rentals_count = None
        maintenance_count = None
        total_payments = None
    else:
        # Get rental statistics for client
        properties_count = None
        available_count = None
        rented_count = None
        
        rentals = Rental.query.filter_by(tenant_id=current_user.id).all()
        rentals_count = len(rentals)
        maintenance_count = Maintenance.query.filter_by(
            reported_by=current_user.id,
            status='pending'
        ).count()
        total_payments = db.session.query(func.sum(Payment.amount)).join(Rental).filter(
            Rental.tenant_id == current_user.id,
            Payment.status == 'completed'
        ).scalar() or 0
        
    # Get recent activity
    recent_activity = []
    
    if current_user.role in ['admin', 'agent']:
        # Get recent property listings and rentals
        recent_properties = Property.query.filter_by(owner_id=current_user.id).order_by(
            Property.created_at.desc()
        ).limit(5).all()
        for prop in recent_properties:
            recent_activity.append({
                'description': f'Listed property: {prop.title}',
                'date': prop.created_at,
                'status': prop.status,
                'status_color': 'success' if prop.status == 'available' else 'warning'
            })
    else:
        # Get recent rentals and maintenance requests
        recent_rentals = Rental.query.filter_by(tenant_id=current_user.id).order_by(
            Rental.created_at.desc()
        ).limit(3).all()
        for rental in recent_rentals:
            recent_activity.append({
                'description': f'Rented: {rental.property.title}',
                'date': rental.created_at,
                'status': rental.status,
                'status_color': 'success' if rental.status == 'active' else 'warning'
            })
            
        recent_maintenance = Maintenance.query.filter_by(reported_by=current_user.id).order_by(
            Maintenance.created_at.desc()
        ).limit(2).all()
        for maint in recent_maintenance:
            recent_activity.append({
                'description': f'Maintenance request: {maint.issue[:50]}...',
                'date': maint.created_at,
                'status': maint.status,
                'status_color': 'danger' if maint.status == 'pending' else 'success'
            })
    
    # Sort activity by date
    recent_activity.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('profile.html',
                         properties_count=properties_count,
                         available_count=available_count,
                         rented_count=rented_count,
                         rentals_count=rentals_count,
                         maintenance_count=maintenance_count,
                         total_payments="{:,.2f}".format(total_payments) if total_payments is not None else None,
                         recent_activity=recent_activity)
