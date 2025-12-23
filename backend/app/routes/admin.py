"""
Admin Endpoints

Handles:
- Model reloading
- ETL triggering
- Task status monitoring
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from flasgger import swag_from

from app import db
from app.utils.errors import ValidationError, NotFoundError
from app.utils.auth import admin_required
from app.utils.validators import validate_required_fields

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/reload-model", methods=["POST"])
@jwt_required()
@admin_required
@swag_from({
    "tags": ["Admin"],
    "summary": "Reload ML model",
    "description": "Hot reload the ML model without restarting the server",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "schema": {
                "type": "object",
                "properties": {
                    "model_path": {
                        "type": "string",
                        "description": "Optional new model path"
                    }
                }
            }
        }
    ],
    "responses": {
        200: {
            "description": "Model reloaded",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "model_version": {"type": "string"}
                }
            }
        },
        500: {"description": "Failed to reload model"}
    }
})
def reload_model():
    """
    Hot reload ML model
    
    Allows updating the model without restarting the server.
    """
    data = request.get_json() or {}
    model_path = data.get("model_path")
    
    ml_service = current_app.config.get("ML_SERVICE")
    
    if not ml_service:
        from app.services.ml_service import MLService
        ml_service = MLService()
    
    success = ml_service.reload_model(model_path)
    
    if success:
        current_app.config["MODEL_LOADED"] = True
        current_app.config["MODEL_VERSION"] = ml_service.get_model_version()
        
        current_app.logger.info(f"Model reloaded: {ml_service.get_model_version()}")
        
        return jsonify({
            "success": True,
            "model_version": ml_service.get_model_version(),
            "timestamp": datetime.utcnow().isoformat()
        })
    else:
        return jsonify({
            "success": False,
            "error": "Failed to reload model"
        }), 500


@admin_bp.route("/trigger-etl", methods=["POST"])
@jwt_required()
@admin_required
@swag_from({
    "tags": ["Admin"],
    "summary": "Trigger ETL task",
    "description": "Trigger a background ETL task",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "enum": ["recalculate_features", "process_whatsapp", "batch_predict"]
                    },
                    "customer_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of customer IDs"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "File path for WhatsApp processing"
                    }
                },
                "required": ["task"]
            }
        }
    ],
    "responses": {
        200: {
            "description": "Task queued",
            "schema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "status": {"type": "string"}
                }
            }
        },
        400: {"description": "Invalid task"}
    }
})
def trigger_etl():
    """
    Trigger ETL background task
    
    Available tasks:
    - recalculate_features: Recalculate customer features
    - process_whatsapp: Process WhatsApp export file
    - batch_predict: Run batch predictions
    """
    data = request.get_json()
    
    if not data:
        raise ValidationError("Request body is required")
    
    validate_required_fields(data, ["task"])
    
    task_name = data["task"]
    valid_tasks = ["recalculate_features", "process_whatsapp", "batch_predict"]
    
    if task_name not in valid_tasks:
        raise ValidationError(
            f"Invalid task: {task_name}",
            {"task": f"Must be one of: {', '.join(valid_tasks)}"}
        )
    
    customer_ids = data.get("customer_ids")
    file_path = data.get("file_path")
    
    # Import and queue Celery task
    try:
        if task_name == "recalculate_features":
            from app.tasks.etl_tasks import recalculate_customer_features
            result = recalculate_customer_features.delay(customer_ids)
        
        elif task_name == "process_whatsapp":
            if not file_path:
                raise ValidationError("file_path is required for process_whatsapp task")
            from app.tasks.etl_tasks import process_whatsapp_logs
            result = process_whatsapp_logs.delay(file_path)
        
        elif task_name == "batch_predict":
            from app.tasks.prediction_tasks import batch_predict_churn
            result = batch_predict_churn.delay(customer_ids)
        
        current_app.logger.info(f"Queued task {task_name}: {result.id}")
        
        return jsonify({
            "task_id": result.id,
            "task_name": task_name,
            "status": "queued",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except ImportError as e:
        current_app.logger.warning(f"Celery not available, running task synchronously: {e}")
        
        # Fallback: run synchronously
        if task_name == "recalculate_features":
            from app.services.feature_service import FeatureService
            service = FeatureService()
            result = service.recalculate_all_features(customer_ids)
            
            return jsonify({
                "task_id": "sync",
                "task_name": task_name,
                "status": "completed",
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        raise ValidationError("Task cannot be executed synchronously")


@admin_bp.route("/tasks/<task_id>", methods=["GET"])
@jwt_required()
@admin_required
@swag_from({
    "tags": ["Admin"],
    "summary": "Get task status",
    "description": "Check the status of a background task",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "task_id",
            "in": "path",
            "type": "string",
            "required": True
        }
    ],
    "responses": {
        200: {
            "description": "Task status",
            "schema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "status": {"type": "string"},
                    "progress": {"type": "integer"},
                    "result": {"type": "object"}
                }
            }
        },
        404: {"description": "Task not found"}
    }
})
def get_task_status(task_id: str):
    """Get status of background task"""
    try:
        from celery.result import AsyncResult
        from app.tasks import celery_app
        
        result = AsyncResult(task_id, app=celery_app)
        
        response = {
            "task_id": task_id,
            "status": result.status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if result.ready():
            if result.successful():
                response["result"] = result.result
                response["progress"] = 100
            else:
                response["error"] = str(result.result)
        else:
            response["progress"] = result.info.get("progress", 0) if result.info else 0
        
        return jsonify(response)
        
    except ImportError:
        raise NotFoundError("Celery not available, cannot check task status")


@admin_bp.route("/stats", methods=["GET"])
@jwt_required()
@admin_required
@swag_from({
    "tags": ["Admin"],
    "summary": "Get system statistics",
    "description": "Get overview statistics of the system",
    "security": [{"Bearer": []}],
    "responses": {
        200: {"description": "System statistics"}
    }
})
def get_stats():
    """Get system statistics"""
    from app.models.customer import Customer
    from app.models.transaction import Transaction
    from app.models.prediction import ChurnPrediction
    from app.models.action import Action
    
    stats = {
        "customers": {
            "total": Customer.query.count(),
            "active": Customer.query.filter_by(is_active=True).count()
        },
        "transactions": {
            "total": Transaction.query.count(),
            "completed": Transaction.query.filter_by(status="completed").count()
        },
        "predictions": {
            "total": ChurnPrediction.query.count(),
            "high_risk": ChurnPrediction.query.filter_by(churn_label="high").count(),
            "medium_risk": ChurnPrediction.query.filter_by(churn_label="medium").count(),
            "low_risk": ChurnPrediction.query.filter_by(churn_label="low").count()
        },
        "actions": {
            "total": Action.query.count(),
            "pending": Action.query.filter_by(status="pending").count(),
            "in_progress": Action.query.filter_by(status="in_progress").count(),
            "completed": Action.query.filter_by(status="completed").count()
        },
        "model": {
            "loaded": current_app.config.get("MODEL_LOADED", False),
            "version": current_app.config.get("MODEL_VERSION", "unknown")
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return jsonify(stats)
