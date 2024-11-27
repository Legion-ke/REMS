from app import create_app
from models import Maintenance, Property, Rental, User
from sqlalchemy import and_

app = create_app()
with app.app_context():
    # Get a client user (you can replace this with your user ID)
    client = User.query.filter_by(role='client').first()
    print(f"\nChecking maintenance requests for client: {client.name} (ID: {client.id})")
    
    # Get maintenance requests using the same query from the route
    maintenance_requests = Maintenance.query.join(
        Property, Property.id == Maintenance.property_id
    ).join(
        Rental, 
        and_(Rental.property_id == Property.id, Rental.tenant_id == client.id)
    ).filter(
        Maintenance.status != 'completed'
    ).order_by(Maintenance.created_at.desc()).all()
    
    print(f"\nFound {len(maintenance_requests)} pending maintenance requests:")
    for request in maintenance_requests:
        print(f"\nID: {request.id}")
        print(f"Property ID: {request.property_id}")
        print(f"Issue: {request.issue}")
        print(f"Status: {request.status}")
        print(f"Priority: {request.priority}")
        
        # Get the rental info
        rental = Rental.query.filter_by(
            property_id=request.property_id,
            tenant_id=client.id
        ).first()
        if rental:
            print(f"Rental Status: {rental.status}")
        print("-" * 50)
