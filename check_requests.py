from app import create_app
from models import Maintenance, Property, Rental
from flask_login import current_user

app = create_app()
with app.app_context():
    # Get all maintenance requests
    maintenance_requests = Maintenance.query.all()
    print(f"\nAll maintenance requests:")
    for request in maintenance_requests:
        print(f"ID: {request.id}")
        print(f"Property ID: {request.property_id}")
        print(f"Issue: {request.issue}")
        print(f"Status: {request.status}")
        print(f"Priority: {request.priority}")
        print("-" * 50)
