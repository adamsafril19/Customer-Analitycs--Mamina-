"""
Application Configuration
Sistem Prediksi Customer Churn - Mamina Baby Spa

Konfigurasi dipisahkan berdasarkan environment:
- Development: Untuk pengembangan lokal
- Testing: Untuk unit testing
- Production: Untuk deployment
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration class"""
    
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = False
    TESTING = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", 
        "postgresql://user:password@localhost:5432/churn_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True
    }
    
    # JWT
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 3600))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        seconds=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", 2592000))
    )
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"
    
    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Celery
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    CELERY_TASK_SERIALIZER = "json"
    CELERY_RESULT_SERIALIZER = "json"
    CELERY_ACCEPT_CONTENT = ["json"]
    CELERY_TIMEZONE = "Asia/Jakarta"
    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_TIME_LIMIT = 300  # 5 minutes
    
    # ML Models
    MODEL_PATH = os.getenv("MODEL_PATH", "models/churn_model.pkl")
    VECTORIZER_PATH = os.getenv("VECTORIZER_PATH", "models/vectorizer.pkl")
    FEATURE_META_PATH = os.getenv("FEATURE_META_PATH", "models/features.json")
    SHAP_EXPLAINER_PATH = os.getenv("SHAP_EXPLAINER_PATH", "models/shap_explainer.pkl")
    
    # Model Config
    MODEL_VERSION = os.getenv("MODEL_VERSION", "v1.0.0")
    ENABLE_SHAP = os.getenv("ENABLE_SHAP", "true").lower() == "true"
    SHAP_BACKGROUND_MODE = os.getenv("SHAP_BACKGROUND_MODE", "true").lower() == "true"
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
    
    # Security
    PHONE_HASH_SALT = os.getenv("PHONE_HASH_SALT", "default-salt-change-in-production")
    
    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # Cache
    PREDICTION_CACHE_TTL = 3600  # 1 hour in seconds


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    
    # Use SQLite for local development if PostgreSQL not available
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", 
        "postgresql://user:password@localhost:5432/churn_db_dev"
    )


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    
    # Use separate test database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL", 
        "postgresql://user:password@localhost:5432/churn_db_test"
    )
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Use eager task execution for testing
    CELERY_TASK_ALWAYS_EAGER = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Stricter security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # Production logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING")


# Configuration dictionary
config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": ProductionConfig
}
