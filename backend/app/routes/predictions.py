"""
Prediction Endpoints

REVISED: Uses new ontology, no storytelling
"""
from datetime import datetime, date
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from flasgger import swag_from

from app import db
from app.models.customer import Customer
from app.models.prediction import ChurnPrediction
from app.models.numeric_features import CustomerNumericFeatures
from app.models.text_signals import CustomerTextSignals
from app.models.topic import ShapCache
from app.services.ml_service import MLService
from app.services.explainer_service import ExplainerService
from app.services.feature_service import FeatureService
from app.utils.errors import NotFoundError, ValidationError, ModelNotLoadedError
from app.utils.validators import validate_uuid, validate_pagination, validate_enum

predictions_bp = Blueprint("predictions", __name__)


@predictions_bp.route("/predict/customer/<customer_id>", methods=["POST"])
@jwt_required()
def predict_customer(customer_id: str):
    """Generate churn prediction for a single customer"""
    customer_uuid = validate_uuid(customer_id, "customer_id")
    
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    
    ml_service = current_app.config.get("ML_SERVICE")
    if not ml_service or not ml_service.is_model_loaded():
        raise ModelNotLoadedError("ML model is not loaded")
    
    feature_service = FeatureService()
    today = date.today()
    
    # Ensure features are populated
    feature_service.populate_numeric_features(customer_id, today)
    feature_service.populate_text_signals(customer_id, today)
    
    # Get feature vector
    feature_vector = feature_service.get_ml_feature_vector(customer_id, today)
    if not feature_vector:
        raise ValidationError("Could not calculate features for customer")
    
    # Run prediction
    churn_score, churn_label = ml_service.predict(feature_vector)
    
    # Store prediction (no top_reasons - that's storytelling)
    prediction = ChurnPrediction(
        customer_id=customer_uuid,
        churn_score=churn_score,
        churn_label=churn_label,
        model_version=ml_service.get_model_version(),
        as_of_date=today
    )
    db.session.add(prediction)
    db.session.commit()
    
    # Calculate and cache SHAP values
    explainer_service = ExplainerService(ml_service)
    shap_values = explainer_service.calculate_shap_values(feature_vector)
    
    if shap_values:
        shap_cache = ShapCache(
            pred_id=prediction.pred_id,
            shap_values=shap_values,
            explainer_version=ml_service.get_model_version()
        )
        db.session.add(shap_cache)
        db.session.commit()
    
    current_app.logger.info(f"Prediction for {customer_id}: score={churn_score:.2f}")
    
    return jsonify({
        "customer_id": str(customer_id),
        "churn_score": round(churn_score, 4),
        "churn_label": churn_label,
        "model_version": ml_service.get_model_version(),
        "as_of_date": today.isoformat(),
        "shap_values": shap_values
    })


@predictions_bp.route("/predictions", methods=["GET"])
@jwt_required()
def list_predictions():
    """List churn predictions with filtering and pagination"""
    label = request.args.get("label")
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    
    query = ChurnPrediction.query
    
    if label:
        validate_enum(label, ["low", "medium", "high"], "label")
        query = query.filter_by(churn_label=label)
    
    total = query.count()
    predictions = query.order_by(
        ChurnPrediction.churn_score.desc()
    ).offset(offset).limit(limit).all()
    
    return jsonify({
        "total": total,
        "predictions": [p.to_dict() for p in predictions]
    })


@predictions_bp.route("/predictions/<pred_id>", methods=["GET"])
@jwt_required()
def get_prediction(pred_id: str):
    """Get prediction details with SHAP values"""
    pred_uuid = validate_uuid(pred_id, "pred_id")
    
    prediction = ChurnPrediction.query.get(pred_uuid)
    if not prediction:
        raise NotFoundError(f"Prediction {pred_id} not found")
    
    result = prediction.to_dict()
    
    # Add SHAP values from cache
    if prediction.shap_cache:
        result["shap_values"] = prediction.shap_cache.shap_values
    
    return jsonify(result)


@predictions_bp.route("/predictions/customer/<customer_id>", methods=["GET"])
@jwt_required()
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
