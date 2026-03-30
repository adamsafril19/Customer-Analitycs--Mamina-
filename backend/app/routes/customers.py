"""
Customer Endpoints

UPDATED: Uses correct ontology (numeric + text_signals for ML, text_semantics for dashboard)
"""
from datetime import datetime, date
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from flasgger import swag_from
from sqlalchemy import func

from app import db
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.prediction import ChurnPrediction
from app.models.numeric_features import CustomerNumericFeatures
from app.models.text_signals import CustomerTextSignals
from app.models.text_semantics import CustomerTextSemantics
from app.models.feedback import FeedbackFeatures
from app.models.topic import ShapCache
from app.utils.errors import NotFoundError, ValidationError
from app.utils.validators import validate_uuid, validate_pagination, validate_required_fields
from app.utils.auth import hash_phone_number

customers_bp = Blueprint("customers", __name__)


@customers_bp.route("/customers/<customer_id>/360", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Customers"],
    "summary": "Get Customer 360 View",
    "description": "Comprehensive view with correct ontology separation",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "customer_id",
            "in": "path",
            "type": "string",
            "required": True
        }
    ],
    "responses": {
        200: {"description": "Customer 360 view"},
        404: {"description": "Customer not found"}
    }
})
def get_customer_360(customer_id: str):
    """
    Get comprehensive 360-degree view of customer
    
    Uses correct ontology:
    - numeric_features + text_signals = what ML sees
    - text_semantics = what dashboard shows (for explanation)
    """
    customer_uuid = validate_uuid(customer_id, "customer_id")
    
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    
    # Get numeric features (RFM + tenure)
    numeric = CustomerNumericFeatures.query.filter_by(
        customer_id=customer_uuid
    ).order_by(CustomerNumericFeatures.as_of_date.desc()).first()
    
    numeric_features = {}
    if numeric:
        numeric_features = {
            "r_score": numeric.r_score,
            "f_score": numeric.f_score,
            "m_score": numeric.m_score,
            "tenure_days": numeric.tenure_days,
            "as_of_date": numeric.as_of_date.isoformat() if numeric.as_of_date else None
        }
    
    # Get text signals (behavioral patterns - ML sees this)
    signals = CustomerTextSignals.query.filter_by(
        customer_id=customer_uuid
    ).order_by(CustomerTextSignals.as_of_date.desc()).first()
    
    text_signals = {}
    if signals:
        text_signals = {
            "msg_count_7d": signals.msg_count_7d,
            "msg_count_30d": signals.msg_count_30d,
            "msg_volatility": signals.msg_volatility,
            "avg_msg_length_30d": signals.avg_msg_length_30d,
            "complaint_rate_30d": signals.complaint_rate_30d,
            "response_delay_mean": signals.response_delay_mean,
            "embedding_count_30d": signals.embedding_count_30d,
            "has_embedding": signals.avg_embedding is not None
        }
    
    # Get text semantics (dashboard only - for explanation)
    semantics = CustomerTextSemantics.query.filter_by(
        customer_id=customer_uuid
    ).order_by(CustomerTextSemantics.as_of_date.desc()).first()
    
    text_semantics = {}
    if semantics:
        text_semantics = {
            "top_topic_counts": semantics.top_topic_counts,
            "sentiment_dist": semantics.sentiment_dist,
            "top_keywords": semantics.top_keywords,
            "top_complaint_types": semantics.top_complaint_types,
            "dominant_topic": semantics.get_dominant_topic(),
            "dominant_sentiment": semantics.get_dominant_sentiment()
        }
    
    # Get transaction summary
    transactions = Transaction.query.filter_by(
        customer_id=customer_uuid,
        status="completed"
    ).all()
    
    transaction_summary = {
        "total_transactions": len(transactions),
        "total_spent": sum(float(tx.amount) for tx in transactions),
        "last_transaction_date": max((tx.tx_date for tx in transactions), default=None)
    }
    if transaction_summary["last_transaction_date"]:
        transaction_summary["last_transaction_date"] = transaction_summary["last_transaction_date"].isoformat()
    
    # Get latest prediction
    latest_prediction = ChurnPrediction.query.filter_by(
        customer_id=customer_uuid
    ).order_by(ChurnPrediction.created_at.desc()).first()
    
    prediction_data = None
    if latest_prediction:
        prediction_data = {
            "pred_id": str(latest_prediction.pred_id),
            "churn_score": latest_prediction.churn_score,
            "churn_label": latest_prediction.churn_label,
            "top_reasons": latest_prediction.top_reasons,
            "model_version": latest_prediction.model_version,
            "as_of_date": latest_prediction.as_of_date.isoformat() if latest_prediction.as_of_date else None
        }
        
        # Get cached SHAP
        cache = ShapCache.query.filter_by(pred_id=latest_prediction.pred_id).first()
        if cache:
            prediction_data["shap_cached"] = True
            prediction_data["nearest_messages"] = cache.nearest_messages
    
    # Get last messages for drilldown
    last_messages = []
    if semantics and semantics.last_n_msg_ids:
        for msg_id in semantics.last_n_msg_ids[:5]:
            fb = FeedbackFeatures.query.filter_by(msg_id=msg_id).first()
            if fb and fb.feedback_raw:
                text = fb.feedback_raw.text or ""
                last_messages.append({
                    "msg_id": str(fb.msg_id),
                    "text_snippet": text[:100] + "..." if len(text) > 100 else text,
                    "sentiment_label": fb.sentiment_label,
                    "has_complaint": fb.has_complaint
                })
    
    # Quick stats
    quick_stats = {
        "total_transactions": transaction_summary["total_transactions"],
        "total_spent": transaction_summary["total_spent"],
        "last_visit": transaction_summary["last_transaction_date"],
        "message_count": text_signals.get("msg_count_30d", 0),
        "complaint_rate": text_signals.get("complaint_rate_30d", 0)
    }
    
    return jsonify({
        "customer": customer.to_dict(),
        "numeric_features": numeric_features,  # ML sees this
        "text_signals": text_signals,          # ML sees this
        "text_semantics": text_semantics,      # Dashboard only
        "transaction_summary": transaction_summary,
        "latest_prediction": prediction_data,
        "last_messages": last_messages,
        "quick_stats": quick_stats
    })


@customers_bp.route("/customers/<customer_id>/timeline", methods=["GET", "OPTIONS"])
@jwt_required(optional=True)
def get_customer_timeline(customer_id: str):
    """Get customer activity timeline"""
    if request.method == "OPTIONS":
        return jsonify({}), 200
    
    customer_uuid = validate_uuid(customer_id, "customer_id")
    
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    
    timeline_type = request.args.get("type", "all")
    limit = request.args.get("limit", 10, type=int)
    
    timeline_items = []
    
    # Get transactions
    if timeline_type in ["transactions", "all"]:
        transactions = Transaction.query.filter_by(
            customer_id=customer_uuid
        ).order_by(Transaction.tx_date.desc()).limit(limit).all()
        
        for tx in transactions:
            timeline_items.append({
                "id": str(tx.tx_id),
                "type": "transaction",
                "date": tx.tx_date.isoformat() if tx.tx_date else None,
                "description": f"Transaksi: {tx.service_type or 'Unknown'}",
                "amount": float(tx.amount) if tx.amount else 0,
                "status": tx.status
            })
    
    # Get feedback
    if timeline_type in ["messages", "feedback", "all"]:
        feedbacks = FeedbackFeatures.query.filter_by(
            customer_id=customer_uuid
        ).order_by(FeedbackFeatures.processed_at.desc()).limit(limit).all()
        
        for fb in feedbacks:
            raw_text = fb.feedback_raw.text if fb.feedback_raw else None
            description = raw_text[:100] + "..." if raw_text and len(raw_text) > 100 else raw_text
            
            timeline_items.append({
                "id": str(fb.feature_id),
                "type": "feedback",
                "date": fb.processed_at.isoformat() if fb.processed_at else None,
                "description": description,
                "sentiment": fb.sentiment_label,
                "has_complaint": fb.has_complaint
            })
    
    timeline_items.sort(key=lambda x: x["date"] if x["date"] else "", reverse=True)
    
    return jsonify({
        "customer_id": str(customer_uuid),
        "type": timeline_type,
        "total": len(timeline_items),
        "items": timeline_items[:limit]
    })


@customers_bp.route("/customers", methods=["GET"])
@jwt_required()
def list_customers():
    """List customers with pagination"""
    search = request.args.get("search")
    is_active = request.args.get("is_active")
    risk_level = request.args.get("risk_level")
    limit = min(100, max(1, request.args.get("limit", 20, type=int)))
    page = max(1, request.args.get("page", 1, type=int))
    offset = (page - 1) * limit
    
    query = Customer.query
    
    if search:
        query = query.filter(
            db.or_(
                Customer.name.ilike(f"%{search}%"),
                Customer.city.ilike(f"%{search}%")
            )
        )
    
    if is_active is not None:
        is_active_bool = str(is_active).lower() in ["true", "1"]
        query = query.filter_by(is_active=is_active_bool)
    
    total = query.count()
    customers = query.order_by(Customer.name).offset(offset).limit(limit).all()
    
    # Get predictions
    customer_ids = [c.customer_id for c in customers]
    predictions = {}
    if customer_ids:
        preds = ChurnPrediction.query.filter(
            ChurnPrediction.customer_id.in_(customer_ids)
        ).order_by(ChurnPrediction.created_at.desc()).all()
        for p in preds:
            if p.customer_id not in predictions:
                predictions[p.customer_id] = p
    
    result = []
    for c in customers:
        data = c.to_dict()
        pred = predictions.get(c.customer_id)
        if pred:
            data["churn_score"] = round(pred.churn_score, 3)
            data["churn_label"] = pred.churn_label
        result.append(data)
    
    return jsonify({"total": total, "customers": result})


@customers_bp.route("/customers/<customer_id>", methods=["GET"])
@jwt_required()
def get_customer(customer_id: str):
    """Get customer details"""
    customer_uuid = validate_uuid(customer_id, "customer_id")
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    return jsonify(customer.to_dict())


@customers_bp.route("/customers", methods=["POST"])
@jwt_required()
def create_customer():
    """Create customer"""
    data = request.get_json()
    if not data:
        raise ValidationError("Request body required")
    validate_required_fields(data, ["name"])
    
    phone_hash = None
    if data.get("phone"):
        phone_hash = hash_phone_number(data["phone"])
        if Customer.query.filter_by(phone_hash=phone_hash).first():
            raise ValidationError("Phone already exists")
    
    customer = Customer(
        name=data["name"],
        phone_hash=phone_hash,
        city=data.get("city"),
        consent_given=data.get("consent_given", False)
    )
    db.session.add(customer)
    db.session.commit()
    
    return jsonify(customer.to_dict()), 201


@customers_bp.route("/customers/<customer_id>", methods=["PATCH"])
@jwt_required()
def update_customer(customer_id: str):
    """Update customer"""
    customer_uuid = validate_uuid(customer_id, "customer_id")
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    
    data = request.get_json()
    if not data:
        raise ValidationError("Request body required")
    
    for field in ["name", "city", "is_active", "consent_given"]:
        if field in data:
            setattr(customer, field, data[field])
    
    db.session.commit()
    return jsonify(customer.to_dict())


@customers_bp.route("/customers/<customer_id>", methods=["DELETE"])
@jwt_required()
def delete_customer(customer_id: str):
    """Delete customer (Right to be Forgotten)"""
    customer_uuid = validate_uuid(customer_id, "customer_id")
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    
    current_app.logger.warning(f"Deleting customer {customer_id}")
    db.session.delete(customer)
    db.session.commit()
    
    return jsonify({"message": "Customer deleted", "customer_id": customer_id})
