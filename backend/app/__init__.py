"""
Flask Application Factory
Sistem Prediksi Customer Churn - Mamina Baby Spa

Arsitektur:
- Flask untuk inference dan API serving (BUKAN training)
- Model ML di-load sekali saat startup
- SHAP explainability untuk interpretasi prediksi
- Celery untuk background jobs (ETL, batch prediction)
"""
import os
import logging
from datetime import datetime
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flasgger import Swagger

from app.config import config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

def create_app(config_name: str = None) -> Flask:
    """
    Application Factory Pattern
    
    Args:
        config_name: Configuration name (development, testing, production)
        
    Returns:
        Flask application instance
    """
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "production")
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Swagger configuration
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/api/docs/"
    }
    
    swagger_template = {
        "info": {
            "title": "Mamina Churn Prediction API",
            "description": "API Backend untuk Sistem Prediksi Customer Churn",
            "version": "1.0.0",
            "contact": {
                "name": "Skripsi Project",
                "email": "admin@mamina.com"
            }
        },
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT Authorization header using the Bearer scheme. Example: 'Bearer {token}'"
            }
        },
        "security": [{"Bearer": []}]
    }
    
    Swagger(app, config=swagger_config, template=swagger_template)
    
    # Setup logging
    setup_logging(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # JWT error handlers
    register_jwt_callbacks(app)
    
    # Load ML models on startup (singleton pattern)
    with app.app_context():
        load_ml_models(app)
    
    app.logger.info(f"Application started in {config_name} mode")
    
    return app


def setup_logging(app: Flask) -> None:
    """Configure application logging"""
    log_level = getattr(logging, app.config.get("LOG_LEVEL", "INFO"))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # File handler (if configured)
    log_file = app.config.get("LOG_FILE")
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(console_formatter)
        app.logger.addHandler(file_handler)
    
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)


def register_blueprints(app: Flask) -> None:
    """Register Flask blueprints"""
    from app.routes.health import health_bp
    from app.routes.auth import auth_bp
    from app.routes.predictions import predictions_bp
    from app.routes.customers import customers_bp
    from app.routes.actions import actions_bp
    from app.routes.admin import admin_bp
    
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(predictions_bp, url_prefix="/api")
    app.register_blueprint(customers_bp, url_prefix="/api")
    app.register_blueprint(actions_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")


def register_error_handlers(app: Flask) -> None:
    """Register error handlers"""
    from app.utils.errors import (
        APIError, 
        ValidationError, 
        NotFoundError,
        UnauthorizedError
    )
    
    @app.errorhandler(APIError)
    def handle_api_error(error):
        response = jsonify({
            "error": error.message,
            "code": error.code,
            "timestamp": datetime.utcnow().isoformat()
        })
        response.status_code = error.status_code
        return response
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        response = jsonify({
            "error": error.message,
            "code": "VALIDATION_ERROR",
            "details": error.details,
            "timestamp": datetime.utcnow().isoformat()
        })
        response.status_code = 400
        return response
    
    @app.errorhandler(NotFoundError)
    def handle_not_found_error(error):
        response = jsonify({
            "error": error.message,
            "code": "NOT_FOUND",
            "timestamp": datetime.utcnow().isoformat()
        })
        response.status_code = 404
        return response
    
    @app.errorhandler(UnauthorizedError)
    def handle_unauthorized_error(error):
        response = jsonify({
            "error": error.message,
            "code": "UNAUTHORIZED",
            "timestamp": datetime.utcnow().isoformat()
        })
        response.status_code = 401
        return response
    
    @app.errorhandler(404)
    def handle_404(error):
        return jsonify({
            "error": "Resource not found",
            "code": "NOT_FOUND",
            "timestamp": datetime.utcnow().isoformat()
        }), 404
    
    @app.errorhandler(500)
    def handle_500(error):
        app.logger.error(f"Internal server error: {error}")
        return jsonify({
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
            "timestamp": datetime.utcnow().isoformat()
        }), 500


def register_jwt_callbacks(app: Flask) -> None:
    """Register JWT callbacks for error handling"""
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            "error": "Token has expired",
            "code": "TOKEN_EXPIRED",
            "timestamp": datetime.utcnow().isoformat()
        }), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            "error": "Invalid token",
            "code": "INVALID_TOKEN",
            "timestamp": datetime.utcnow().isoformat()
        }), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            "error": "Authorization token is missing",
            "code": "MISSING_TOKEN",
            "timestamp": datetime.utcnow().isoformat()
        }), 401


def load_ml_models(app: Flask) -> None:
    """
    Load ML models once at startup (singleton pattern)
    
    Models are loaded into app.config for global access:
    - LOADED_MODEL: Main churn prediction model
    - LOADED_VECTORIZER: Text vectorizer (if applicable)
    - LOADED_SHAP_EXPLAINER: SHAP explainer for interpretability
    - FEATURE_METADATA: Feature names and types
    """
    from app.services.ml_service import MLService
    
    try:
        ml_service = MLService()
        ml_service.load_all_models()
        
        # Store in app config for global access
        app.config["ML_SERVICE"] = ml_service
        app.config["MODEL_LOADED"] = ml_service.is_model_loaded()
        
        app.logger.info(f"ML models loaded successfully. Version: {app.config.get('MODEL_VERSION')}")
        
    except Exception as e:
        app.logger.warning(f"Failed to load ML models: {e}")
        app.config["MODEL_LOADED"] = False
        # Don't crash the app, allow it to run without models
        # Models can be loaded later via admin endpoint
