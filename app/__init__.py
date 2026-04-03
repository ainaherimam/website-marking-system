from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_session import Session

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
session_ext = Session()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    session_ext.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
    login_manager.login_message_category = 'warning'

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # Blueprints
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.chef import bp as chef_bp
    from app.blueprints.directeur import bp as directeur_bp
    from app.blueprints.admin import bp as admin_bp
    from app.blueprints.referentiel import bp as ref_bp
    from app.blueprints.consultation import bp as consult_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(chef_bp, url_prefix='/chef')
    app.register_blueprint(directeur_bp, url_prefix='/directeur')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(ref_bp)
    app.register_blueprint(consult_bp)

    # CLI commands
    from app.cli import register_commands
    register_commands(app)

    return app
