import os
import sys

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import Rental, Payment, User, Property
from datetime import datetime, timedelta

app = create_app()

def check_rental_status():
    with app.app_context():
        # Get all active rentals
        active_rentals = Rental.query.filter_by(status='active').all()
        
        print(f"\nTotal active rentals found: {len(active_rentals)}")
        print("\n=== RENTAL STATUS REPORT ===")
        
        for rental in active_rentals:
            tenant = User.query.get(rental.tenant_id)
            property = Property.query.get(rental.property_id)
            
            print(f"\nRental ID: {rental.id}")
            print(f"Property: {property.title}")
            print(f"Tenant: {tenant.name}")
            print(f"Start Date: {rental.start_date}")
            print(f"Monthly Rent: KES {rental.rent_amount:,.2f}")
            
            # Get last payment
            last_payment = Payment.query.filter_by(
                rental_id=rental.id
            ).order_by(Payment.payment_date.desc()).first()
            
            if last_payment:
                next_due_date = last_payment.payment_date + timedelta(days=30)
                print(f"Last Payment: {last_payment.payment_date.strftime('%Y-%m-%d')}")
                print(f"Next Due Date: {next_due_date.strftime('%Y-%m-%d')}")
                
                if next_due_date <= datetime.now():
                    days_overdue = (datetime.now() - next_due_date).days
                    print(f"Status: PAYMENT DUE (Overdue by {days_overdue} days)")
                else:
                    days_until_due = (next_due_date - datetime.now()).days
                    print(f"Status: Up to date (Next payment in {days_until_due} days)")
            else:
                first_due_date = rental.start_date + timedelta(days=30)
                if first_due_date <= datetime.now().date():
                    days_overdue = (datetime.now().date() - first_due_date).days
                    print("Status: NO PAYMENTS MADE")
                    print(f"First payment was due {days_overdue} days ago")
                else:
                    days_until_due = (first_due_date - datetime.now().date()).days
                    print("Status: NO PAYMENTS MADE")
                    print(f"First payment due in {days_until_due} days")
            
            print("-" * 50)

if __name__ == "__main__":
    check_rental_status()
