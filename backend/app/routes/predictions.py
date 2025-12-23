"""
Prediction Endpoints

Handles:
- Single customer prediction
- List predictions
- Batch predictions (via Celery)
"""
from datetime import datetime, date
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from flasgger import swag_from

from app import db
from app.models.customer import Customer
from app.models.prediction import ChurnPrediction
from app.models.feature import CustomerFeature
from app.services.ml_service import MLService
from app.services.explainer_service import ExplainerService
from app.services.feature_service import FeatureService
from app.utils.errors import NotFoundError, ValidationError, ModelNotLoadedError
from app.utils.validators import validate_uuid, validate_pagination, validate_enum

predictions_bp = Blueprint("predictions", __name__)


@predictions_bp.route("/predict/customer/<customer_id>", methods=["POST"])
@jwt_required()
@swag_from({
    "tags": ["Predictions"],
    "summary": "Predict churn for single customer",
    "description": "Generate churn prediction with SHAP explanations for a customer",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "customer_id",
            "in": "path",
            "type": "string",
            "required": True,
            "description": "Customer UUID"
        }
    ],
    "responses": {
        200: {
            "description": "Prediction generated",
            "schema": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "churn_score": {"type": "number", "example": 0.78},
                    "churn_label": {"type": "string", "example": "high"},
                    "top_reasons": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "feature": {"type": "string"},
                                "impact": {"type": "number"},
                                "description": {"type": "string"}
                            }
                        }
                    },
                    "model_version": {"type": "string"},
                    "as_of_date": {"type": "string"},
                    "created_at": {"type": "string"}
                }
            }
        },
        404: {"description": "Customer not found"},
        503: {"description": "Model not loaded"}
    }
})
def predict_customer(customer_id: str):
    """
    Generate churn prediction for a single customer
    
    Steps:
    1. Validate customer exists
    2. Get or calculate features
    3. Run ML prediction
    4. Calculate SHAP explanations
    5. Store and return prediction
    """
    # Validate customer_id
    customer_uuid = validate_uuid(customer_id, "customer_id")
    
    # Check customer exists
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    
    # Get ML service
    ml_service = current_app.config.get("ML_SERVICE")
    if not ml_service or not ml_service.is_model_loaded():
        raise ModelNotLoadedError("ML model is not loaded. Cannot make predictions.")
    
    # Get or calculate features
    feature_service = FeatureService()
    today = date.today()
    
    features = feature_service.get_latest_features(customer_id)
    if not features or features.as_of_date < today:
        # Recalculate features
        features = feature_service.calculate_customer_features(customer_id, today)
    
    # Convert to feature vector
    feature_vector = features.to_feature_vector()
    
    # Run prediction
    churn_score, churn_label = ml_service.predict(feature_vector)
    
    # Get SHAP explanations
    explainer_service = ExplainerService(ml_service)
    top_reasons = explainer_service.get_top_reasons(feature_vector, top_n=5)
    
    # Store prediction
    prediction = ChurnPrediction(
        customer_id=customer_uuid,
        churn_score=churn_score,
        churn_label=churn_label,
        top_reasons=top_reasons,
        model_version=ml_service.get_model_version(),
        as_of_date=today
    )
    
    db.session.add(prediction)
    db.session.commit()
    
    current_app.logger.info(
        f"Prediction generated for customer {customer_id}: "
        f"score={churn_score:.2f}, label={churn_label}"
    )
    
    return jsonify({
        "customer_id": str(customer_id),
        "churn_score": round(churn_score, 4),
        "churn_label": churn_label,
        "top_reasons": top_reasons,
        "model_version": ml_service.get_model_version(),
        "as_of_date": today.isoformat(),
        "created_at": prediction.created_at.isoformat()
    })


@predictions_bp.route("/predictions", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Predictions"],
    "summary": "List predictions",
    "description": "Get paginated list of churn predictions with optional filters",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "label",
            "in": "query",
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "Filter by churn label"
        },
        {
            "name": "limit",
            "in": "query",
            "type": "integer",
            "default": 20,
            "description": "Number of results per page"
        },
        {
            "name": "offset",
            "in": "query",
            "type": "integer",
            "default": 0,
            "description": "Offset for pagination"
        }
    ],
    "responses": {
        200: {
            "description": "List of predictions",
            "schema": {
                "type": "object",
                "properties": {
                    "total": {"type": "integer"},
                    "predictions": {
                        "type": "array",
                        "items": {"type": "object"}
                    }
                }
            }
        }
    }
})
def list_predictions():
    """
    List churn predictions with filtering and pagination
    """
    # Get query parameters
    label = request.args.get("label")
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    
    # Validate pagination
    offset, limit = validate_pagination(offset // limit + 1 if offset else 1, limit)
    
    # Build query
    query = ChurnPrediction.query
    
    if label:
        validate_enum(label, ["low", "medium", "high"], "label")
        query = query.filter_by(churn_label=label)
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    predictions = query.order_by(
        ChurnPrediction.churn_score.desc()
    ).offset(offset).limit(limit).all()
    
    return jsonify({
        "total": total,
        "predictions": [p.to_dict_with_customer() for p in predictions]
    })


@predictions_bp.route("/predictions/<pred_id>", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Predictions"],
    "summary": "Get prediction details",
    "description": "Get detailed information about a specific prediction",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "pred_id",
            "in": "path",
            "type": "string",
            "required": True,
            "description": "Prediction UUID"
        }
    ],
    "responses": {
        200: {"description": "Prediction details"},
        404: {"description": "Prediction not found"}
    }
})
def get_prediction(pred_id: str):
    """Get prediction details"""
    pred_uuid = validate_uuid(pred_id, "pred_id")
    
    prediction = ChurnPrediction.query.get(pred_uuid)
    if not prediction:
        raise NotFoundError(f"Prediction {pred_id} not found")
    
    return jsonify(prediction.to_dict_with_customer())


@predictions_bp.route("/predictions/customer/<customer_id>", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Predictions"],
    "summary": "Get predictions for customer",
    "description": "Get all predictions for a specific customer",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "customer_id",
            "in": "path",
            "type": "string",
            "required": True,
            "description": "Customer UUID"
        }
    ],
    "responses": {
        200: {"description": "List of predictions for customer"},
        404: {"description": "Customer not found"}
    }
})
def get_customer_predictions(customer_id: str):
    """Get all predictions for a customer"""
    customer_uuid = validate_uuid(customer_id, "customer_id")
    
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    
    predictions = ChurnPrediction.query.filter_by(
        customer_id=customer_uuid
    ).order_by(ChurnPrediction.created_at.desc()).all()
    
    return jsonify({
        "customer_id": customer_id,
        "predictions": [p.to_dict() for p in predictions]
    })
