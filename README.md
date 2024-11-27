# Rent Management System

A comprehensive property rental management system built with Flask.

## Features

- Property listing and management
- Rental request processing
- Payment tracking and verification
- Maintenance request handling
- Email notifications
- User roles (Admin, Agent, Client)

## Quick Start with Docker

1. Clone the repository:
```bash
git clone <repository-url>
cd rent-management
```

2. Configure environment variables:
   - Open `docker-compose.yml`
   - Update the following variables:
     * SECRET_KEY: Your secure secret key
     * MAIL_USERNAME: Your email address
     * MAIL_PASSWORD: Your email app password
     * Other environment variables as needed

3. Build and start the containers:
```bash
docker-compose up --build
```

4. Access the application:
   - Open your browser and go to `http://localhost:5000`
   - Create an admin account at `http://localhost:5000/register`

## Development Setup

If you prefer to run the application without Docker:

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Update the variables in `.env`

4. Initialize the database:
```bash
flask db upgrade
```

5. Run the development server:
```bash
python app.py
```

## Database Migrations

To update the database schema:

```bash
# In Docker:
docker-compose exec web flask db upgrade

# Without Docker:
flask db upgrade
```

## Maintenance

### Backup Database

With Docker:
```bash
docker-compose exec db pg_dump -U postgres rentmanagement > backup.sql
```

### Restore Database

With Docker:
```bash
docker-compose exec -T db psql -U postgres rentmanagement < backup.sql
```

## Troubleshooting

1. If the application fails to start:
   - Check if all environment variables are set correctly
   - Ensure PostgreSQL container is running: `docker-compose ps`
   - View logs: `docker-compose logs`

2. If emails are not sending:
   - Verify email credentials in environment variables
   - Check if SMTP settings are correct
   - Ensure less secure app access is enabled for Gmail

## License

This project is licensed under the MIT License - see the LICENSE file for details.
