from app import create_app
from models import Property, User
from sqlalchemy import func

app = create_app()
with app.app_context():
    # Get an agent user
    agent = User.query.filter_by(role='agent').first()
    print(f"\nChecking properties for agent: {agent.name if agent else 'No agent found'}")
    
    if agent:
        # Get all properties
        properties = Property.query.filter_by(agent_id=agent.id).all()
        print(f"\nTotal properties: {len(properties)}")
        
        # Get property counts by status
        status_counts = Property.query.filter_by(agent_id=agent.id).with_entities(
            Property.status, func.count(Property.id)
        ).group_by(Property.status).all()
        
        print("\nProperties by status:")
        for status, count in status_counts:
            print(f"{status}: {count}")
            
        print("\nDetailed property list:")
        for prop in properties:
            print(f"\nID: {prop.id}")
            print(f"Title: {prop.title}")
            print(f"Status: {prop.status}")
            print(f"Price: {prop.price}")
            print(f"Created at: {prop.created_at}")
            print("-" * 50)
