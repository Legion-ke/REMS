from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Rental, Payment, Property, Maintenance
from extensions import db
from datetime import datetime
from sqlalchemy import func
from datetime import timedelta
from decorators import client_required
from utils import generate_transaction_reference, generate_mpesa_reference

client = Blueprint('client', __name__, url_prefix='/client')

@client.route('/rentals')
@login_required
@client_required
def my_rentals():
    # Get active rentals
    active_rentals = Rental.query.filter_by(
        tenant_id=current_user.id,
        status='active'
    ).order_by(Rental.start_date.desc()).all()

    # Get past rentals
    past_rentals = Rental.query.filter(
        Rental.tenant_id == current_user.id,
        Rental.status.in_(['expired', 'terminated'])
    ).order_by(Rental.end_date.desc()).all()

    # Add next payment info to active rentals
    for rental in active_rentals:
        last_payment = Payment.query.filter_by(
            rental_id=rental.id
        ).order_by(Payment.payment_date.desc()).first()
        
        if last_payment:
            next_due_date = last_payment.payment_date + timedelta(days=30)
        else:
            # Convert date to datetime at midnight
            start_datetime = datetime.combine(rental.start_date, datetime.min.time())
            next_due_date = start_datetime + timedelta(days=30)
            
        current_time = datetime.now()
        if next_due_date > current_time:
            rental.next_payment = {
                'due_date': next_due_date,
                'is_overdue': False
            }
        else:
            rental.next_payment = {
                'due_date': next_due_date,
                'is_overdue': True
            }

    return render_template('client/my_rentals.html',
                         active_rentals=active_rentals,
                         past_rentals=past_rentals)

@client.route('/rent/<int:property_id>', methods=['GET', 'POST'])
@login_required
@client_required
def rent_property(property_id):
    property_item = Property.query.get_or_404(property_id)
    
    if property_item.status != 'available':
        flash('This property is not available for rent.')
        return redirect(url_for('property.view_property', id=property_id))
    
    if request.method == 'POST':
        try:
            # Convert form dates to datetime objects
            start_date = datetime.strptime(request.form.get('start_date'), '%d/%m/%Y')
            end_date = datetime.strptime(request.form.get('end_date'), '%d/%m/%Y')
            payment_method = request.form.get('payment_method')
            
            # Get current date without time for comparison
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Validate dates
            if start_date < today:
                flash('Start date cannot be in the past')
                return redirect(url_for('client.rent_property', property_id=property_id))
            
            if end_date <= start_date:
                flash('End date must be after start date')
                return redirect(url_for('client.rent_property', property_id=property_id))
            
            if (end_date - start_date).days < 30:
                flash('Minimum rental period is 1 month')
                return redirect(url_for('client.rent_property', property_id=property_id))
            
            # Create rental record
            rental = Rental(
                property_id=property_id,
                tenant_id=current_user.id,
                start_date=start_date,
                end_date=end_date,
                rent_amount=property_item.price,
                status='pending'
            )
            db.session.add(rental)
            
            # Create initial payment record
            payment = Payment(
                rental_id=rental.id,
                amount=property_item.price * 2,  # First month + deposit
                payment_date=datetime.now(),
                payment_method=payment_method,
                status='pending'
            )
            db.session.add(payment)
            
            # Update property status
            property_item.status = 'pending'
            
            db.session.commit()
            
            # Redirect to payment
            return redirect(url_for('client.make_payment', rental_id=rental.id))
            
        except ValueError:
            flash('Invalid date format')
            return redirect(url_for('client.rent_property', property_id=property_id))
    
    return render_template('client/rent_property.html', property=property_item)

@client.route('/payment', defaults={'rental_id': None}, methods=['GET'])
@client.route('/payment/<int:rental_id>', methods=['GET', 'POST'])
@login_required
@client_required
def make_payment(rental_id):
    if rental_id is None:
        # Show list of rentals with pending payments
        rentals = Rental.query.filter_by(
            tenant_id=current_user.id,
            status='active'
        ).all()
        
        rentals_with_payments = []
        for rental in rentals:
            # Get the last payment for this rental
            last_payment = Payment.query.filter_by(
                rental_id=rental.id
            ).order_by(Payment.payment_date.desc()).first()
            
            next_payment_due = False
            if last_payment:
                next_due_date = last_payment.payment_date + timedelta(days=30)
                if next_due_date <= datetime.now():
                    next_payment_due = True
            else:
                # Convert date to datetime at midnight
                start_datetime = datetime.combine(rental.start_date, datetime.min.time())
                first_due_date = start_datetime + timedelta(days=30)
                if first_due_date <= datetime.now():
                    next_payment_due = True
            
            if next_payment_due:
                # Calculate days overdue
                current_time = datetime.now()
                if last_payment:
                    days_overdue = (current_time - next_due_date).days
                else:
                    days_overdue = (current_time - first_due_date).days
                
                rentals_with_payments.append({
                    'rental': rental,
                    'property': rental.property,
                    'amount': rental.rent_amount,
                    'days_overdue': days_overdue
                })
        
        return render_template('client/payment_select.html', rentals=rentals_with_payments)
    
    rental = Rental.query.get_or_404(rental_id)
    
    # Verify ownership
    if rental.tenant_id != current_user.id:
        flash('Unauthorized access')
        return redirect(url_for('main.index'))
    
    # Get pending payment
    payment = Payment.query.filter_by(
        rental_id=rental.id,
        status='pending'
    ).first()
    
    if not payment:
        # Calculate next payment date
        last_payment = Payment.query.filter_by(
            rental_id=rental.id
        ).order_by(Payment.payment_date.desc()).first()
        
        if last_payment:
            due_date = last_payment.payment_date + timedelta(days=30)
        else:
            due_date = datetime.combine(rental.start_date, datetime.min.time()) + timedelta(days=30)
        
        # Create new payment record
        payment = Payment(
            rental_id=rental.id,
            amount=rental.rent_amount,
            status='pending',
            payment_date=datetime.now(),
            due_date=due_date,
            total_amount=rental.rent_amount  # Will be updated if there's a late fee
        )

        # Generate appropriate reference based on payment method
        payment_method = request.form.get('payment_method')
        if payment_method == 'mpesa':
            payment.reference = generate_mpesa_reference()
            payment.phone_number = request.form.get('phone_number')
        else:  # bank_transfer or card
            payment.reference = generate_transaction_reference('PAY')
        
        db.session.add(payment)
        db.session.commit()
        
        # Calculate late fee if applicable
        current_time = datetime.now()
        if payment.due_date < current_time:
            days_overdue = (current_time - payment.due_date).days
            late_fee = payment.amount * 0.1  # 10% late fee
            payment.late_fee = late_fee
            payment.days_overdue = days_overdue
            payment.total_amount = payment.amount + late_fee
            db.session.commit()
    
    # Calculate late fee if applicable
    current_time = datetime.now()
    if payment.due_date < current_time:
        days_overdue = (current_time - payment.due_date).days
        payment.late_fee = payment.amount * 0.1  # 10% late fee
        payment.days_overdue = days_overdue
        payment.total_amount = payment.amount + payment.late_fee
    else:
        payment.late_fee = 0
        payment.days_overdue = 0
        payment.total_amount = payment.amount
    
    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        
        if payment_method == 'mpesa':
            # Handle M-PESA payment
            phone_number = request.form.get('phone_number')
            if not phone_number:
                flash('Please provide your M-PESA phone number')
                return redirect(url_for('client.make_payment', rental_id=rental_id))
                
            # TODO: Integrate with M-PESA API
            payment.status = 'pending_mpesa'
            payment.payment_method = 'mpesa'
            payment.phone_number = phone_number
            db.session.commit()
            flash('M-PESA payment request sent. Please check your phone for the STK push.')
            return redirect(url_for('client.my_rentals'))
            
        elif payment_method == 'bank':
            # Handle bank transfer
            reference = request.form.get('reference')
            if not reference:
                flash('Please provide the transaction reference')
                return redirect(url_for('client.make_payment', rental_id=rental_id))
            
            payment.reference = reference
            payment.status = 'pending_verification'
            payment.payment_method = 'bank'
            db.session.commit()
            flash('Payment pending verification')
            return redirect(url_for('client.my_rentals'))
            
        elif payment_method == 'card':
            # Handle card payment
            # TODO: Integrate with card payment gateway
            payment.status = 'pending_card'
            payment.payment_method = 'card'
            db.session.commit()
            flash('Card payment integration coming soon')
            return redirect(url_for('client.my_rentals'))
    
    return render_template('client/make_payment.html', 
                         rental=rental,
                         payment=payment)

@client.route('/payments/<int:rental_id>')
@login_required
@client_required
def view_payments(rental_id):
    rental = Rental.query.get_or_404(rental_id)
    
    # Verify ownership
    if rental.tenant_id != current_user.id:
        flash('Unauthorized access')
        return redirect(url_for('main.index'))
    
    payments = Payment.query.filter_by(rental_id=rental.id).order_by(Payment.payment_date.desc()).all()
    
    return render_template('client/payment_history.html', rental=rental, payments=payments)

@client.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'client':
        flash('Access denied. Clients only.', 'danger')
        return redirect(url_for('main.index'))
    
    # Get active rentals with next payment dates
    rentals = Rental.query.filter_by(
        tenant_id=current_user.id,
        status='active'
    ).all()
    
    active_rentals_count = len(rentals)
    pending_payments = 0
    
    for rental in rentals:
        # Get the last payment for this rental
        last_payment = Payment.query.filter_by(
            rental_id=rental.id
        ).order_by(Payment.payment_date.desc()).first()
        
        if last_payment:
            # If there was a previous payment, next payment is due 30 days after
            rental.next_payment_date = last_payment.payment_date + timedelta(days=30)
            if rental.next_payment_date <= datetime.now():
                pending_payments += rental.property.price
        else:
            # If no payments made yet, next payment is due 30 days after start date
            rental.next_payment_date = rental.start_date + timedelta(days=30)
            if rental.next_payment_date <= datetime.now().date():
                pending_payments += rental.property.price
    
    # Get maintenance requests
    maintenance_requests = Maintenance.query.join(
        Property, Property.id == Maintenance.property_id
    ).join(
        Rental, 
        (Rental.property_id == Property.id) & (Rental.tenant_id == current_user.id)
    ).filter(
        Maintenance.status != 'completed'
    ).order_by(Maintenance.created_at.desc()).all()
    
    # Format maintenance requests with status and priority colors
    maintenance_list = []
    for request in maintenance_requests:
        status_color = {
            'pending': 'warning',
            'in_progress': 'info',
            'completed': 'success'
        }.get(request.status, 'secondary')
        
        priority_color = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger'
        }.get(request.priority, 'secondary')
        
        maintenance_list.append({
            'property': request.property,
            'issue': request.issue,
            'status': request.status,
            'priority': request.priority,
            'created_at': request.created_at,
            'status_color': status_color,
            'priority_color': priority_color
        })
    
    return render_template('client/dashboard.html',
                         active_rentals=active_rentals_count,
                         pending_payments=pending_payments,
                         maintenance_count=len(maintenance_requests),
                         rentals=rentals,
                         maintenance_list=maintenance_list[:5])

@client.route('/profile', methods=['GET', 'POST'])
@login_required
@client_required
def view_profile():
    if request.method == 'POST':
        # Update profile information
        current_user.name = request.form.get('name')
        current_user.email = request.form.get('email')
        current_user.phone = request.form.get('phone')
        
        # Only update password if provided
        new_password = request.form.get('new_password')
        if new_password:
            current_user.set_password(new_password)
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('client.view_profile'))
    
    # Get statistics
    active_rentals = Rental.query.filter_by(
        tenant_id=current_user.id,
        status='active'
    ).count()
    
    total_payments = Payment.query.join(Rental).filter(
        Rental.tenant_id == current_user.id
    ).count()
    
    maintenance_requests = Maintenance.query.join(Property).join(Rental).filter(
        Rental.tenant_id == current_user.id
    ).count()
    
    return render_template('client/profile.html',
                         user=current_user,
                         stats={
                             'active_rentals': active_rentals,
                             'total_payments': total_payments,
                             'maintenance_requests': maintenance_requests
                         })
