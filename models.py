from extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, agent, client
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Relationships
    properties = db.relationship('Property', backref='agent', foreign_keys='Property.agent_id')
    owned_properties = db.relationship('Property', backref='owner', foreign_keys='Property.owner_id')
    rentals = db.relationship('Rental', backref='tenant', foreign_keys='Rental.tenant_id')

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    address = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    bedrooms = db.Column(db.Integer)
    bathrooms = db.Column(db.Integer)
    area = db.Column(db.Float)
    status = db.Column(db.String(20), default='available')  # available, rented, maintenance
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    agent_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_property_agent'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_property_owner'))
    
    # Relationships
    rentals = db.relationship('Rental', backref='property', lazy=True)
    maintenance_requests = db.relationship('Maintenance', backref='property', lazy=True)

class Rental(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', name='fk_rental_property'))
    tenant_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_rental_tenant'))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    rent_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, active, rejected, expired, terminated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add relationship to payments
    payments = db.relationship('Payment', backref='rental', lazy=True)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rental_id = db.Column(db.Integer, db.ForeignKey('rental.id', name='fk_payment_rental'))
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, nullable=False)
    payment_method = db.Column(db.String(50))
    status = db.Column(db.String(20))  # pending, pending_verification, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    late_fee = db.Column(db.Float, default=0)
    days_overdue = db.Column(db.Integer, default=0)
    total_amount = db.Column(db.Float)
    reference = db.Column(db.String(100))  # For bank transfers
    phone_number = db.Column(db.String(20))  # For M-PESA
    verification_date = db.Column(db.DateTime)
    verified_by = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_payment_verifier'))
    verification_notes = db.Column(db.Text)
    
    # Add relationship to verifier
    verifier = db.relationship('User', backref='verified_payments', foreign_keys=[verified_by])

class Maintenance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', name='fk_maintenance_property'))
    reported_by = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_maintenance_reporter'))
    issue = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20))  # low, medium, high
    status = db.Column(db.String(20))  # pending, in_progress, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
