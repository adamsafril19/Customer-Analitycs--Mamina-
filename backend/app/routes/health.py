"""
Health Check Endpoint

Provides system health status including:
- Application status
- Database connectivity
- ML model status
- Redis connectivity
"""
from datetime import datetime
from flask import Blueprint, jsonify, current_app
from flasgger import swag_from

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
@swag_from({
    "tags": ["Health"],
    "summary": "Health check endpoint",
    "description": "Returns the health status of the API and its dependencies",
    "responses": {
        200: {
            "description": "System is healthy",
            "schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "example": "ok"},
                    "model_loaded": {"type": "boolean", "example": True},
                    "model_version": {"type": "string", "example": "v1.0.0"},
                    "timestamp": {"type": "string", "example": "2025-01-15T10:30:00Z"}
                }
            }
        }
    }
})
def health_check():
    """
    Health check endpoint
    
    Returns system status including:
    - Overall status
    - ML model loading status
    - Model version
    - Current timestamp
    """
    # Check model status
    model_loaded = current_app.config.get("MODEL_LOADED", False)
    model_version = current_app.config.get("MODEL_VERSION", "unknown")
    
    # Check database connectivity
    db_status = "ok"
    try:
        from app import db
        db.session.execute(db.text("SELECT 1"))
    except Exception as e:
        db_status = "error"
        current_app.logger.error(f"Database health check failed: {e}")
    
    # Check Redis connectivity
    redis_status = "ok"
    try:
        import redis
        redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        r.ping()
    except Exception as e:
        redis_status = "error"
        current_app.logger.warning(f"Redis health check failed: {e}")
    
    # Determine overall status
    if db_status == "ok":
        status = "ok"
    else:
        status = "degraded"
    
    return jsonify({
        "status": status,
        "model_loaded": model_loaded,
        "model_version": model_version,
        "database": db_status,
        "redis": redis_status,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


@health_bp.route("/ready", methods=["GET"])
def readiness_check():
    """
    Readiness check for Kubernetes/container orchestration
    
    Returns 200 if service is ready to accept requests
    """
    model_loaded = current_app.config.get("MODEL_LOADED", False)
    
    # Check database
    try:
        from app import db
        db.session.execute(db.text("SELECT 1"))
        db_ready = True
    except Exception:
        db_ready = False
    
    if model_loaded and db_ready:
        return jsonify({"ready": True}), 200
    else:
        return jsonify({
            "ready": False,
            "model_loaded": model_loaded,
            "database_ready": db_ready
        }), 503


@health_bp.route("/live", methods=["GET"])
def liveness_check():
    """
    Liveness check for Kubernetes/container orchestration
    
    Returns 200 if service is alive
    """
    return jsonify({"alive": True}), 200
