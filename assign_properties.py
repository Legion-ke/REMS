from app import create_app
from models import Property, User
from sqlalchemy import func

app = create_app()
with app.app_context():
    # Get the current agent
    agent = User.query.filter_by(name='Given Omondi', role='agent').first()
    if not agent:
        print("Agent 'Given Omondi' not found")
        exit()
        
    # Get some available properties
    properties = Property.query.filter_by(status='available').limit(3).all()
    
    # Assign them to the current agent
    for prop in properties:
        prop.agent_id = agent.id
        print(f"Assigning property '{prop.title}' to agent {agent.name}")
    
    # Commit the changes
    from extensions import db
    db.session.commit()
    
    print("\nAssignment complete. Checking updated properties:")
    agent_properties = Property.query.filter_by(agent_id=agent.id).all()
    print(f"\nTotal properties for {agent.name}: {len(agent_properties)}")
    for prop in agent_properties:
        print(f"\nID: {prop.id}")
        print(f"Title: {prop.title}")
        print(f"Status: {prop.status}")
        print(f"Price: {prop.price}")
        print("-" * 50)
