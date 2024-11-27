from app import create_app
from models import Property, User
from sqlalchemy import func

app = create_app()
with app.app_context():
    # Get all properties
    properties = Property.query.all()
    print(f"\nTotal properties in database: {len(properties)}")
    
    # Get property counts by status
    status_counts = Property.query.with_entities(
        Property.status, func.count(Property.id)
    ).group_by(Property.status).all()
    
    print("\nProperties by status:")
    for status, count in status_counts:
        print(f"{status}: {count}")
    
    print("\nDetailed property list:")
    for prop in properties:
        agent = User.query.get(prop.agent_id)
        print(f"\nID: {prop.id}")
        print(f"Title: {prop.title}")
        print(f"Status: {prop.status}")
        print(f"Price: {prop.price}")
        print(f"Agent: {agent.name if agent else 'No agent'}")
        print(f"Created at: {prop.created_at}")
        print("-" * 50)
