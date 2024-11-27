from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, abort
from flask_login import login_required, current_user
from models import Property, Rental, Maintenance, Payment, User
from extensions import db, mail
from sqlalchemy import func, case
from datetime import datetime, timedelta
from io import BytesIO, StringIO
import csv
from functools import wraps
from flask_mail import Message
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

def agent_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'agent':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def generate_payment_receipt(payment):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from io import BytesIO
    from datetime import datetime

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    # Add title
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        spaceAfter=30
    )
    story.append(Paragraph("Payment Receipt", title_style))
    
    # Add payment details
    details_style = ParagraphStyle(
        'Details',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6
    )
    
    story.append(Paragraph(f"Receipt #: {payment.id}", details_style))
    story.append(Paragraph(f"Date: {payment.payment_date.strftime('%Y-%m-%d %H:%M')}", details_style))
    story.append(Paragraph(f"Property: {payment.rental.property.title}", details_style))
    story.append(Paragraph(f"Address: {payment.rental.property.address}", details_style))
    story.append(Paragraph(f"Tenant: {payment.rental.tenant.name}", details_style))
    story.append(Spacer(1, 20))
    
    # Format amounts
    def format_kes(amount):
        if amount is None:
            return "KES 0.00"
        return f"KES {amount:,.2f}"
    
    # Add payment table
    payment_data = [
        ['Description', 'Amount'],
        ['Rent Payment', format_kes(payment.amount)],
    ]
    
    # Add late fee if applicable
    if payment.late_fee and payment.late_fee > 0:
        payment_data.append(['Late Fee', format_kes(payment.late_fee)])
        payment_data.append(['Total Amount', format_kes(payment.total_amount)])
    
    payment_data.extend([
        ['Payment Method', payment.payment_method.title()],
        ['Reference', payment.reference or 'N/A'],
        ['Status', payment.status.replace('_', ' ').title()]
    ])
    
    t = Table(payment_data, colWidths=[300, 200])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    
    # Add footer
    story.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.gray
    )
    story.append(Paragraph("This is an electronically generated receipt.", footer_style))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

def send_payment_reminder_email(payment):
    subject = f"Payment Reminder - Rent Due for {payment.rental.property.title}"
    
    body = f"""
    Dear {payment.rental.tenant.name},

    This is a friendly reminder that your rent payment is due.

    Payment Details:
    - Amount: {format_kes(payment.amount)}
    - Due Date: {payment.due_date.strftime('%Y-%m-%d')}
    - Property: {payment.rental.property.title}
    - Address: {payment.rental.property.address}

    Please ensure to make the payment before the due date to avoid any late fees.

    If you have already made the payment, please disregard this reminder.

    Best regards,
    {payment.rental.property.owner.name}
    """
    
    msg = Message(
        subject,
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[payment.rental.tenant.email]
    )
    msg.body = body
    mail.send(msg)

def send_contractor_notification(maintenance, contractor):
    try:
        subject = f"New Maintenance Assignment - {maintenance.property.title}"
        body = f"""
            Hello {contractor.name},
            
            You have been assigned to a new maintenance:
            
            Property: {maintenance.property.title}
            Address: {maintenance.property.address}
            Issue: {maintenance.issue}
            Priority: {maintenance.priority}
            
            Please review the request and begin work as soon as possible.
            
            Best regards,
            {current_user.name}
        """
        
        msg = Message(
            subject=subject,
            recipients=[contractor.email],
            body=body
        )
        mail.send(msg)
    except Exception as e:
        print(f"Error sending contractor notification: {str(e)}")
        # Don't raise the exception - we don't want to roll back the contractor assignment
        # just because the email failed

agent = Blueprint('agent', __name__, url_prefix='/agent')

@agent.route('/dashboard')
@login_required
@agent_required
def dashboard():
    # Get total properties
    total_properties = Property.query.filter_by(agent_id=current_user.id).count()
    
    # Get available properties count
    properties_available = Property.query.filter_by(
        agent_id=current_user.id,
        status='available'
    ).count()
    
    # Get rented properties count
    properties_rented = Property.query.filter_by(
        agent_id=current_user.id,
        status='rented'
    ).count()
    
    # Get active rentals
    active_rentals = Rental.query.join(Property).filter(
        Property.agent_id == current_user.id,
        Rental.status == 'active'
    ).count()
    
    # Get pending maintenance
    pending_maintenance = Maintenance.query.join(Property).filter(
        Property.agent_id == current_user.id,
        Maintenance.status == 'pending'
    ).count()
    
    # Get recent maintenance requests
    recent_maintenance = Maintenance.query.join(Property).filter(
        Property.agent_id == current_user.id
    ).order_by(Maintenance.created_at.desc()).limit(5).all()
    
    # Add status colors for maintenance
    for maintenance in recent_maintenance:
        if maintenance.status == 'pending':
            maintenance.status_color = 'warning'
        elif maintenance.status == 'in_progress':
            maintenance.status_color = 'info'
        else:
            maintenance.status_color = 'success'
    
    # Get monthly revenue
    current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue = db.session.query(func.sum(Payment.amount)).join(Rental).join(Property).filter(
        Property.agent_id == current_user.id,
        Payment.status == 'completed',
        Payment.payment_date >= current_month
    ).scalar() or 0
    
    # Get recent properties
    recent_properties = Property.query.filter_by(agent_id=current_user.id).order_by(Property.created_at.desc()).limit(5).all()
    
    # Get recent activity (properties, rentals, and maintenance)
    recent_activity = []
    
    # Add recent properties
    for prop in recent_properties:
        recent_activity.append({
            'type': 'property',
            'title': f"New property listed: {prop.title}",
            'timestamp': prop.created_at,
            'status': prop.status,
            'icon': 'home',
            'color': 'primary'
        })
    
    # Add recent maintenance requests
    for req in recent_maintenance:
        recent_activity.append({
            'type': 'maintenance',
            'title': f"Maintenance request for {req.property.title}",
            'timestamp': req.created_at,
            'status': req.status,
            'icon': 'tools',
            'color': 'warning'
        })
    
    # Sort by timestamp
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:5]  # Keep only 5 most recent
    
    return render_template('agent/dashboard.html',
                         total_properties=total_properties,
                         properties_available=properties_available,
                         properties_rented=properties_rented,
                         active_rentals=active_rentals,
                         pending_maintenance=pending_maintenance,
                         monthly_revenue=monthly_revenue,
                         recent_properties=recent_properties,
                         recent_maintenance=recent_maintenance,
                         recent_activity=recent_activity)

@agent.route('/maintenance')
@login_required
@agent_required
def maintenance():
    # Get filter parameters
    status = request.args.get('status', 'all')
    priority = request.args.get('priority', 'all')
    
    # Base query
    query = Maintenance.query.join(Property).filter(
        Property.agent_id == current_user.id
    )
    
    # Apply filters
    if status != 'all':
        query = query.filter(Maintenance.status == status)
    if priority != 'all':
        query = query.filter(Maintenance.priority == priority)
    
    # Get maintenance ordered by priority and created date
    maintenance = query.order_by(
        case(
            (Maintenance.priority == 'high', 1),
            (Maintenance.priority == 'medium', 2),
            else_=3
        ),
        Maintenance.created_at.desc()
    ).all()
    
    return render_template('agent/maintenance.html',
        maintenance=maintenance,
        current_status=status,
        current_priority=priority
    )

@agent.route('/update-maintenance/<int:request_id>', methods=['GET', 'POST'])
@login_required
@agent_required
def update_maintenance(request_id):
    # Get the maintenance
    maintenance = Maintenance.query.join(Property).filter(
        Maintenance.id == request_id,
        Property.agent_id == current_user.id
    ).first_or_404()
    
    if request.method == 'POST':
        maintenance.status = request.form.get('status')
        maintenance.notes = request.form.get('notes')
        maintenance.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Maintenance request updated successfully', 'success')
        return redirect(url_for('agent.maintenance'))
    
    return render_template('agent/maintenance_detail.html', maintenance=maintenance)

@agent.route('/payment-history')
@login_required
@agent_required
def payment_history():
    # Get filter parameters
    status = request.args.get('status', 'all')
    date_range = request.args.get('date_range', '30')
    property_id = request.args.get('property_id')
    tenant_id = request.args.get('tenant_id')
    
    # Calculate date range
    end_date = datetime.utcnow()
    if date_range.isdigit():
        start_date = end_date - timedelta(days=int(date_range))
    else:
        start_date = end_date - timedelta(days=30)  # Default to 30 days
    
    # Base query
    query = Payment.query.join(
        Rental, Payment.rental_id == Rental.id
    ).join(
        Property, Rental.property_id == Property.id
    ).join(
        User, Rental.tenant_id == User.id
    ).filter(
        Property.agent_id == current_user.id
    )
    
    # Apply filters
    if status != 'all':
        query = query.filter(Payment.status == status)
        
    query = query.filter(Payment.created_at.between(start_date, end_date))
    
    if property_id:
        query = query.filter(Property.id == property_id)
    
    # Get payments ordered by date
    payments = query.order_by(Payment.created_at.desc()).all()
    
    # Calculate statistics
    total_revenue = sum(payment.amount for payment in payments if payment.status == 'completed')
    
    # Calculate monthly revenue
    current_month = datetime.now().month
    current_year = datetime.now().year
    monthly_revenue = sum(payment.amount for payment in payments 
                         if payment.status == 'completed' 
                         and payment.created_at.month == current_month
                         and payment.created_at.year == current_year)
    
    pending_amount = sum(payment.amount for payment in payments if payment.status == 'pending')
    overdue_amount = sum(payment.amount for payment in payments if payment.status == 'overdue')
    
    # Format currency values
    def format_currency(amount):
        return "{:,.2f}".format(float(amount if amount is not None else 0))
    
    # Get all properties and tenants for filter dropdowns
    properties = Property.query.filter_by(agent_id=current_user.id).all()
    tenants = User.query.join(Rental, User.id == Rental.tenant_id).join(Property, Rental.property_id == Property.id).filter(
        Property.agent_id == current_user.id,
        User.role == 'tenant'
    ).distinct().all()
    
    return render_template('agent/payment_history.html',
        payments=payments,
        total_revenue=format_currency(total_revenue),
        monthly_revenue=format_currency(monthly_revenue),
        pending_amount=format_currency(pending_amount),
        overdue_amount=format_currency(overdue_amount),
        properties=properties,
        tenants=tenants,
        selected_status=status,
        selected_date_range=date_range,
        selected_property_id=property_id,
        selected_tenant_id=tenant_id
    )

@agent.route('/view-payment/<int:payment_id>')
@login_required
@agent_required
def view_payment(payment_id):
    # Get the payment with related data
    payment = Payment.query.join(Rental, Payment.rental_id == Rental.id).join(Property, Rental.property_id == Property.id).filter(
        Payment.id == payment_id,
        Property.agent_id == current_user.id
    ).first_or_404()
    
    # Get payment history for this rental
    payment_history = Payment.query.filter(
        Payment.rental_id == payment.rental_id
    ).order_by(Payment.created_at.desc()).all()
    
    return render_template('agent/view_payment.html',
        payment=payment,
        payment_history=payment_history
    )

@agent.route('/rental-history/<int:property_id>')
@login_required
@agent_required
def rental_history(property_id):
    # Get the property
    property = Property.query.filter_by(
        id=property_id,
        agent_id=current_user.id
    ).first_or_404()
    
    # Get all rentals for this property
    rentals = Rental.query.filter_by(
        property_id=property_id
    ).order_by(Rental.start_date.desc()).all()
    
    # Calculate statistics
    total_revenue = db.session.query(func.sum(Payment.amount)).join(
        Rental, Payment.rental_id == Rental.id
    ).filter(
        Rental.property_id == property_id,
        Payment.status == 'completed'
    ).scalar() or 0
    
    avg_rental_duration = 0
    if rentals:
        durations = []
        for rental in rentals:
            if rental.end_date and rental.start_date:
                duration = (rental.end_date - rental.start_date).days
                durations.append(duration)
        if durations:
            avg_rental_duration = sum(durations) / len(durations)
    
    return render_template('agent/rental_history.html',
        property=property,
        rentals=rentals,
        total_revenue=total_revenue,
        avg_rental_duration=avg_rental_duration
    )

@agent.route('/assign-contractor', methods=['POST'])
@login_required
@agent_required
def assign_contractor():
    # Get request data
    request_id = request.form.get('request_id')
    contractor_id = request.form.get('contractor_id')
    
    if not request_id or not contractor_id:
        return jsonify({
            'success': False,
            'message': 'Missing required parameters'
        }), 400
    
    # Get the maintenance
    maintenance = Maintenance.query.join(Property).filter(
        Maintenance.id == request_id,
        Property.agent_id == current_user.id
    ).first_or_404()
    
    # Get the contractor
    contractor = User.query.filter_by(
        id=contractor_id,
        role='contractor'
    ).first_or_404()
    
    try:
        # Assign contractor
        maintenance.contractor_id = contractor.id
        maintenance.status = 'assigned'
        db.session.commit()
        
        # Send email notification to contractor
        send_contractor_notification(maintenance, contractor)
        
        return jsonify({
            'success': True,
            'message': f'Contractor {contractor.name} assigned successfully'
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error assigning contractor: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error assigning contractor'
        }), 500

@agent.route('/send-payment-reminder/<int:payment_id>', methods=['POST'])
@login_required
@agent_required
def send_payment_reminder(payment_id):
    # Get the payment
    payment = Payment.query.join(Rental, Payment.rental_id == Rental.id).join(Property, Rental.property_id == Property.id).filter(
        Payment.id == payment_id,
        Property.agent_id == current_user.id
    ).first_or_404()
    
    # Only send reminder for pending or overdue payments
    if payment.status not in ['pending', 'overdue']:
        return jsonify({
            'success': False,
            'message': 'Payment reminder can only be sent for pending or overdue payments'
        }), 400
    
    try:
        # Send reminder email
        send_payment_reminder_email(payment)
        
        # Update reminder sent timestamp
        payment.last_reminder_sent = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Payment reminder sent successfully'
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error sending payment reminder: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error sending payment reminder'
        }), 500

@agent.route('/mark-payment-paid/<int:payment_id>', methods=['POST'])
@login_required
@agent_required
def mark_payment_paid(payment_id):
    # Get the payment
    payment = Payment.query.join(Rental, Payment.rental_id == Rental.id).join(Property, Rental.property_id == Property.id).filter(
        Payment.id == payment_id,
        Property.agent_id == current_user.id
    ).first_or_404()
    
    # Only mark pending or overdue payments as paid
    if payment.status not in ['pending', 'overdue']:
        return jsonify({
            'success': False,
            'message': 'Only pending or overdue payments can be marked as paid'
        }), 400
    
    try:
        # Update payment status
        payment.status = 'completed'
        payment.paid_date = datetime.utcnow()
        payment.payment_method = request.form.get('payment_method', 'cash')
        payment.notes = request.form.get('notes', '')
        
        db.session.commit()
        
        # Generate and send receipt
        try:
            receipt_buffer = generate_payment_receipt(payment)
            send_payment_receipt_email(payment, receipt_buffer)
        except Exception as e:
            # Log error but don't fail the payment update
            print(f"Error sending payment receipt: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': 'Payment marked as paid successfully'
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error marking payment as paid: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error marking payment as paid'
        }), 500

def send_payment_receipt_email(payment, receipt_buffer):
    try:
        subject = f"Payment Receipt - {payment.rental.property.title}"
        body = f"""
            Dear {payment.rental.tenant.name},
            
            Thank you for your payment of {format_kes(payment.amount)} for {payment.rental.property.title}.
            
            Payment Details:
            - Amount: {format_kes(payment.amount)}
            - Date: {payment.paid_date.strftime('%Y-%m-%d')}
            - Method: {payment.payment_method}
            - Property: {payment.rental.property.title}
            
            Your receipt is attached to this email.
            
            Best regards,
            {current_user.name}
        """
        
        msg = Message(
            subject=subject,
            recipients=[payment.rental.tenant.email],
            body=body
        )
        
        msg.attach(
            f"receipt_{payment.id}.pdf",
            "application/pdf",
            receipt_buffer.getvalue()
        )
        
        mail.send(msg)
    except Exception as e:
        print(f"Error sending payment receipt email: {str(e)}")
        # Don't raise the exception - we don't want to roll back the payment update
        # just because the email failed

@agent.route('/download-receipt/<int:payment_id>')
@login_required
@agent_required
def download_receipt(payment_id):
    # Get the payment
    payment = Payment.query.join(Rental, Payment.rental_id == Rental.id).join(Property, Rental.property_id == Property.id).filter(
        Payment.id == payment_id,
        Property.agent_id == current_user.id
    ).first_or_404()
    
    try:
        # Generate receipt
        receipt_buffer = generate_payment_receipt(payment)
        receipt_buffer.seek(0)
        
        return send_file(
            receipt_buffer,
            as_attachment=True,
            download_name=f"receipt_{payment.id}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error generating receipt: {str(e)}")
        flash('Error generating receipt', 'danger')
        return redirect(url_for('agent.view_payment', payment_id=payment_id))

@agent.route('/export-payments')
@login_required
@agent_required
def export_payments():
    # Get filter parameters
    status = request.args.get('status', 'all')
    date_range = request.args.get('date_range', '30')
    property_id = request.args.get('property_id')
    tenant_id = request.args.get('tenant_id')
    
    # Calculate date range
    end_date = datetime.utcnow()
    if date_range.isdigit():
        start_date = end_date - timedelta(days=int(date_range))
    else:
        start_date = end_date - timedelta(days=30)  # Default to 30 days
    
    # Base query
    query = Payment.query.join(
        Rental, Payment.rental_id == Rental.id
    ).join(
        Property, Rental.property_id == Property.id
    ).join(
        User, Rental.tenant_id == User.id
    ).filter(
        Property.agent_id == current_user.id
    )
    
    # Apply filters
    if status != 'all':
        query = query.filter(Payment.status == status)
        
    query = query.filter(Payment.created_at.between(start_date, end_date))
    
    if property_id:
        query = query.filter(Property.id == property_id)
    
    # Get payments ordered by date
    payments = query.order_by(Payment.created_at.desc()).all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow([
        'Payment ID',
        'Property',
        'Tenant',
        'Amount',
        'Status',
        'Due Date',
        'Paid Date',
        'Payment Method',
        'Notes'
    ])
    
    # Write payment data
    for payment in payments:
        writer.writerow([
            payment.id,
            payment.rental.property.title,
            payment.rental.tenant.name,
            format_kes(payment.amount),
            payment.status,
            payment.due_date.strftime('%Y-%m-%d'),
            payment.paid_date.strftime('%Y-%m-%d') if payment.paid_date else 'N/A',
            payment.payment_method or 'N/A',
            payment.notes or 'N/A'
        ])
    
    # Prepare the response
    output.seek(0)
    return send_file(
        BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'payment_export_{datetime.now().strftime("%Y%m%d")}.csv'
    )

@agent.route('/generate-report')
@login_required
@agent_required
def generate_report():
    # Get report parameters
    report_type = request.args.get('type', 'summary')
    date_range = request.args.get('date_range', '30')
    property_id = request.args.get('property_id')
    format = request.args.get('format', 'pdf')  # pdf, csv, or excel
    
    # Calculate date range
    end_date = datetime.utcnow()
    if date_range.isdigit():
        start_date = end_date - timedelta(days=int(date_range))
    else:
        start_date = end_date - timedelta(days=30)  # Default to 30 days
    
    try:
        # Generate report based on type
        if report_type == 'summary':
            report_data = generate_summary_report(current_user.id, start_date, end_date, property_id)
        elif report_type == 'maintenance':
            report_data = generate_maintenance_report(current_user.id, start_date, end_date, property_id)
        elif report_type == 'financial':
            report_data = generate_financial_report(current_user.id, start_date, end_date, property_id)
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid report type'
            }), 400
        
        # Generate report in requested format
        if format == 'pdf':
            report_buffer = generate_pdf_report(report_type, report_data)
            mimetype = 'application/pdf'
            ext = 'pdf'
        elif format == 'csv':
            report_buffer = generate_csv_report(report_type, report_data)
            mimetype = 'text/csv'
            ext = 'csv'
        elif format == 'excel':
            report_buffer = generate_excel_report(report_type, report_data)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ext = 'xlsx'
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid format type'
            }), 400
        
        # Send the report
        report_buffer.seek(0)
        return send_file(
            report_buffer,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f'{report_type}_report_{datetime.now().strftime("%Y%m%d")}.{ext}'
        )
        
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error generating report'
        }), 500

@agent.route('/verify-payment/<int:payment_id>', methods=['POST'])
@login_required
@agent_required
def verify_payment(payment_id):
    # Get the payment
    payment = Payment.query.join(Rental, Payment.rental_id == Rental.id).join(Property, Rental.property_id == Property.id).filter(
        Payment.id == payment_id,
        Property.agent_id == current_user.id
    ).first_or_404()
    
    # Only verify pending_verification payments
    if payment.status != 'pending_verification':
        return jsonify({
            'success': False,
            'message': 'Only pending verification payments can be verified'
        }), 400
    
    try:
        # Update payment status
        payment.status = 'completed'
        payment.verification_date = datetime.utcnow()
        payment.verified_by = current_user.id
        payment.verification_notes = request.form.get('notes', '')
        
        db.session.commit()
        
        # Generate and send receipt
        try:
            receipt_buffer = generate_payment_receipt(payment)
            send_payment_receipt_email(payment, receipt_buffer)
        except Exception as e:
            # Log error but don't fail the verification
            print(f"Error sending payment receipt: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': 'Payment verified successfully'
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error verifying payment: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error verifying payment'
        }), 500

def generate_summary_report(agent_id, start_date, end_date, property_id=None):
    # Base property query
    property_query = Property.query.filter(Property.agent_id == agent_id)
    if property_id:
        property_query = property_query.filter(Property.id == property_id)
    
    # Get properties
    properties = property_query.all()
    
    # Collect data for each property
    report_data = {
        'period': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        },
        'properties': []
    }
    
    total_revenue = 0
    total_expenses = 0
    
    for property in properties:
        # Calculate property statistics
        occupancy_rate = calculate_occupancy_rate(property, start_date, end_date)
        revenue = calculate_property_revenue(property, start_date, end_date)
        expenses = calculate_property_expenses(property, start_date, end_date)
        maintenance_count = count_maintenance(property, start_date, end_date)
        
        property_data = {
            'title': property.title,
            'address': property.address,
            'occupancy_rate': occupancy_rate,
            'revenue': revenue,
            'expenses': expenses,
            'net_income': revenue - expenses,
            'maintenance': maintenance_count
        }
        
        report_data['properties'].append(property_data)
        total_revenue += revenue
        total_expenses += expenses
    
    # Add summary statistics
    report_data['summary'] = {
        'total_properties': len(properties),
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'net_income': total_revenue - total_expenses,
        'average_occupancy': sum(p['occupancy_rate'] for p in report_data['properties']) / len(properties) if properties else 0
    }
    
    return report_data

def generate_maintenance_report(agent_id, start_date, end_date, property_id=None):
    # Base maintenance query
    query = Maintenance.query.join(Property).filter(
        Property.agent_id == agent_id,
        Maintenance.created_at.between(start_date, end_date)
    )
    
    if property_id:
        query = query.filter(Property.id == property_id)
    
    # Get maintenance
    maintenance = query.order_by(Maintenance.created_at.desc()).all()
    
    # Collect data
    report_data = {
        'period': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        },
        'maintenance': [],
        'summary': {
            'total_maintenance': len(maintenance),
            'by_status': {},
            'by_priority': {},
            'average_resolution_time': 0
        }
    }
    
    total_resolution_time = timedelta()
    resolved_count = 0
    
    for maintenance_request in maintenance:
        request_data = {
            'id': maintenance_request.id,
            'property': maintenance_request.property.title,
            'issue': maintenance_request.issue,
            'status': maintenance_request.status,
            'priority': maintenance_request.priority,
            'created_at': maintenance_request.created_at.strftime('%Y-%m-%d %H:%M'),
            'resolved_at': maintenance_request.resolved_at.strftime('%Y-%m-%d %H:%M') if maintenance_request.resolved_at else None,
            'resolution_time': (maintenance_request.resolved_at - maintenance_request.created_at).days if maintenance_request.resolved_at else None,
            'contractor': maintenance_request.contractor.name if maintenance_request.contractor else None,
            'cost': maintenance_request.cost
        }
        
        report_data['maintenance'].append(request_data)
        
        # Update summary statistics
        report_data['summary']['by_status'][maintenance_request.status] = report_data['summary']['by_status'].get(maintenance_request.status, 0) + 1
        report_data['summary']['by_priority'][maintenance_request.priority] = report_data['summary']['by_priority'].get(maintenance_request.priority, 0) + 1
        
        if maintenance_request.resolved_at:
            total_resolution_time += maintenance_request.resolved_at - maintenance_request.created_at
            resolved_count += 1
    
    # Calculate average resolution time
    if resolved_count > 0:
        report_data['summary']['average_resolution_time'] = (total_resolution_time / resolved_count).days
    
    return report_data

def generate_financial_report(agent_id, start_date, end_date, property_id=None):
    # Base payment query
    query = Payment.query.join(Rental, Payment.rental_id == Rental.id).join(Property, Rental.property_id == Property.id).filter(
        Property.agent_id == agent_id,
        Payment.created_at.between(start_date, end_date)
    )
    
    if property_id:
        query = query.filter(Property.id == property_id)
    
    # Get payments
    payments = query.order_by(Payment.created_at.desc()).all()
    
    # Collect data
    report_data = {
        'period': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        },
        'payments': [],
        'summary': {
            'total_payments': len(payments),
            'total_amount': 0,
            'by_status': {},
            'by_method': {}
        }
    }
    
    for payment in payments:
        payment_data = {
            'id': payment.id,
            'property': payment.rental.property.title,
            'tenant': payment.rental.tenant.name,
            'amount': payment.amount,
            'status': payment.status,
            'due_date': payment.due_date.strftime('%Y-%m-%d'),
            'paid_date': payment.paid_date.strftime('%Y-%m-%d') if payment.paid_date else None,
            'payment_method': payment.payment_method
        }
        
        report_data['payments'].append(payment_data)
        
        # Update summary statistics
        report_data['summary']['total_amount'] += payment.amount
        report_data['summary']['by_status'][payment.status] = report_data['summary']['by_status'].get(payment.status, 0) + 1
        if payment.payment_method:
            report_data['summary']['by_method'][payment.payment_method] = report_data['summary']['by_method'].get(payment.payment_method, 0) + 1
    
    return report_data

def format_kes(amount):
    if amount is None:
        return "KES 0.00"
    return f"KES {amount:,.2f}"

@agent.route('/rentals/pending')
@login_required
@agent_required
def pending_rentals():
    # Get pending rentals for properties managed by this agent
    pending_rentals = Rental.query.join(Property).filter(
        Property.agent_id == current_user.id,
        Rental.status == 'pending'
    ).order_by(Rental.created_at.desc()).all()
    
    return render_template('agent/pending_rentals.html',
                         pending_rentals=pending_rentals)

@agent.route('/rental/<int:rental_id>/approve', methods=['POST'])
@login_required
@agent_required
def approve_rental(rental_id):
    rental = Rental.query.get_or_404(rental_id)
    
    # Verify this rental is for a property managed by this agent
    if rental.property.agent_id != current_user.id:
        abort(403)
    
    # Check if payment is made
    payment = Payment.query.filter_by(
        rental_id=rental.id,
        status='paid'
    ).first()
    
    if not payment:
        flash('Cannot approve rental without payment confirmation', 'error')
        return redirect(url_for('agent.pending_rentals'))
    
    try:
        # Update rental status
        rental.status = 'active'
        
        # Update property status
        rental.property.status = 'rented'
        
        # Send confirmation email to tenant
        msg = Message(
            'Rental Approved',
            recipients=[rental.tenant.email],
            html=render_template(
                'emails/rental_approved.html',
                rental=rental,
                tenant=rental.tenant
            )
        )
        mail.send(msg)
        
        db.session.commit()
        flash('Rental has been approved', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error approving rental. Please try again.', 'error')
    
    return redirect(url_for('agent.pending_rentals'))

@agent.route('/rental/<int:rental_id>/reject', methods=['POST'])
@login_required
@agent_required
def reject_rental(rental_id):
    rental = Rental.query.get_or_404(rental_id)
    
    # Verify this rental is for a property managed by this agent
    if rental.property.agent_id != current_user.id:
        abort(403)
    
    try:
        # Update rental status
        rental.status = 'rejected'
        
        # Update property status back to available
        rental.property.status = 'available'
        
        # Send notification email to tenant
        msg = Message(
            'Rental Application Update',
            recipients=[rental.tenant.email],
            html=render_template(
                'emails/rental_rejected.html',
                rental=rental,
                tenant=rental.tenant
            )
        )
        mail.send(msg)
        
        db.session.commit()
        flash('Rental has been rejected', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error rejecting rental. Please try again.', 'error')
    
    return redirect(url_for('agent.pending_rentals'))

@agent.route('/payment/<int:payment_id>/verify', methods=['POST'])
@login_required
@agent_required
def verify_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    
    # Verify this payment is for a property managed by this agent
    if payment.rental.property.agent_id != current_user.id:
        abort(403)
    
    try:
        # Update payment status
        payment.status = 'completed'
        payment.verification_date = datetime.utcnow()
        payment.verified_by = current_user.id
        
        # If this is the initial payment for a pending rental, update rental status
        rental = payment.rental
        if rental.status == 'pending':
            rental.status = 'active'
            rental.property.status = 'rented'
            
            # Send confirmation email to tenant
            msg = Message(
                'Rental Approved',
                recipients=[rental.tenant.email],
                html=render_template(
                    'emails/rental_approved.html',
                    rental=rental,
                    tenant=rental.tenant
                )
            )
            mail.send(msg)
        
        db.session.commit()
        
        # Generate and send receipt
        receipt_buffer = generate_payment_receipt(payment)
        send_payment_receipt_email(payment, receipt_buffer)
        
        flash('Payment has been verified and receipt sent to tenant', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error verifying payment. Please try again.', 'error')
    
    return redirect(url_for('agent.pending_rentals'))
