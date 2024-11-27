from app import create_app
from models import Maintenance

app = create_app()
with app.app_context():
    maintenance_requests = Maintenance.query.filter_by(status='pending').all()
    print(f"Number of pending maintenance requests: {len(maintenance_requests)}")
    for request in maintenance_requests:
        print(f"Property ID: {request.property_id}, Issue: {request.issue}, Priority: {request.priority}")
