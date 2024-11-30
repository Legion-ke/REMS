from flask import Flask, jsonify
import os
from dotenv import load_dotenv
from extensions import db, login_manager, migrate, mail
from models import User

load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///rems.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # File Upload Configuration
    app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB max file size

    # Create upload directory if it doesn't exist
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Email configuration
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@rentmanagement.com')

    # Initialize Flask extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # Configure LoginManager
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Jinja2 filters
    @app.template_filter('currency')
    def currency_format(value):
        if value is None:
            return "KES 0.00"
        if isinstance(value, str):
            # Remove commas before converting to float
            value = value.replace(',', '')
        return "KES {:,.2f}".format(float(value))

    # Register blueprints
    from routes.main_routes import main
    from routes.auth_routes import auth
    from routes.property_routes import property
    from routes.client_routes import client
    from routes.agent_routes import agent

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(property)
    app.register_blueprint(client)
    app.register_blueprint(agent)

    # Create database tables
    with app.app_context():
        db.create_all()

    # Health check endpoint
    @app.route('/health')
    def health_check():
        try:
            # Test database connection
            db.session.execute('SELECT 1')
            return jsonify({'status': 'healthy', 'database': 'connected'}), 200
        except Exception as e:
            return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

    return app

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5002)
else:
    app = create_app()
