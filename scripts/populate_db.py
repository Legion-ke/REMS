from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from models import User, Property, Rental
from werkzeug.security import generate_password_hash

def create_sample_data():
    app = create_app()
    with app.app_context():
        # Create agent
        agent = User(
            email='john.agent@realtor.com',
            password=generate_password_hash('agent123'),
            name='John Smith',
            role='agent'
        )
        db.session.add(agent)
        db.session.commit()

        # Create 15 clients
        clients = []
        for i in range(1, 16):
            client = User(
                email=f'client{i}@example.com',
                password=generate_password_hash(f'client{i}123'),
                name=f'Client {i}',
                role='client'
            )
            clients.append(client)
            db.session.add(client)
        db.session.commit()

        # Create 20 properties
        properties = []
        locations = [
            'Karen', 'Lavington', 'Kileleshwa', 'Kilimani', 'Westlands',
            'Runda', 'Muthaiga', 'Spring Valley', 'Loresho', 'Kitisuru',
            'Nyari', 'Gigiri', 'Riverside', 'Upper Hill', 'Parklands',
            'Garden Estate', 'South B', 'South C', 'Langata', 'Hurlingham'
        ]
        
        for i in range(20):
            property = Property(
                title=f'Luxury {i+1} Bedroom Apartment in {locations[i]}',
                description=f'Beautiful {i+1} bedroom apartment with modern finishes, spacious living area, and stunning views.',
                address=f'{locations[i]} Road, Nairobi',
                price=float(50000 + (i * 10000)),  # Prices from 50,000 to 240,000 KES
                bedrooms=i % 4 + 1,  # 1 to 4 bedrooms
                bathrooms=i % 3 + 1,  # 1 to 3 bathrooms
                area=float(80 + (i * 20)),  # 80 to 460 sq meters
                status='available',
                agent_id=agent.id
            )
            properties.append(property)
            db.session.add(property)
        db.session.commit()

        # Create rentals for first 15 properties (one for each client)
        for i in range(15):
            start_date = datetime.now() - timedelta(days=i*30)  # Stagger start dates
            rental = Rental(
                property_id=properties[i].id,
                tenant_id=clients[i].id,
                start_date=start_date.date(),
                end_date=(start_date + timedelta(days=365)).date(),  # One year lease
                rent_amount=properties[i].price,
                status='active'
            )
            db.session.add(rental)
            # Update property status to rented
            properties[i].status = 'rented'
        db.session.commit()

        print("\nSample data created successfully!")
        print("\nLogin Credentials:")
        print("\nAgent Login:")
        print("Email: john.agent@realtor.com")
        print("Password: agent123")
        print("\nClient Logins:")
        for i in range(1, 16):
            print(f"\nClient {i}:")
            print(f"Email: client{i}@example.com")
            print(f"Password: client{i}123")

if __name__ == '__main__':
    create_sample_data()
