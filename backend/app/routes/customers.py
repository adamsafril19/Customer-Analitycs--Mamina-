"""
Customer Endpoints

Handles:
- Customer 360 view
- Customer listing
- Customer CRUD operations
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
from app.models.feature import CustomerFeature
from app.models.feedback import FeedbackClean
from app.utils.errors import NotFoundError, ValidationError
from app.utils.validators import validate_uuid, validate_pagination, validate_required_fields
from app.utils.auth import hash_phone_number

customers_bp = Blueprint("customers", __name__)


@customers_bp.route("/customers/<customer_id>/360", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Customers"],
    "summary": "Get Customer 360 View",
    "description": "Get comprehensive view of customer including RFM, sentiment, transactions, and predictions",
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
            "description": "Customer 360 view",
            "schema": {
                "type": "object",
                "properties": {
                    "customer": {"type": "object"},
                    "rfm_features": {"type": "object"},
                    "sentiment_summary": {"type": "object"},
                    "transaction_summary": {"type": "object"},
                    "latest_prediction": {"type": "object"}
                }
            }
        },
        404: {"description": "Customer not found"}
    }
})
def get_customer_360(customer_id: str):
    """
    Get comprehensive 360-degree view of customer
    
    Includes:
    - Basic customer info
    - RFM features
    - Sentiment summary
    - Transaction summary
    - Latest prediction with reasons
    """
    customer_uuid = validate_uuid(customer_id, "customer_id")
    
    # Get customer
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    
    # Get latest features
    latest_features = CustomerFeature.query.filter_by(
        customer_id=customer_uuid
    ).order_by(CustomerFeature.as_of_date.desc()).first()
    
    # Get RFM features
    rfm_features = {}
    if latest_features:
        rfm_features = {
            "r_score": latest_features.r_score,
            "f_score": latest_features.f_score,
            "m_score": latest_features.m_score,
            "tenure_days": latest_features.tenure_days,
            "as_of_date": latest_features.as_of_date.isoformat() if latest_features.as_of_date else None
        }
    
    # Get sentiment summary
    sentiment_summary = {}
    if latest_features:
        # Get recent topics from feedback
        recent_feedback = FeedbackClean.query.filter_by(
            customer_id=customer_uuid
        ).order_by(FeedbackClean.processed_at.desc()).limit(10).all()
        
        recent_topics = []
        for fb in recent_feedback:
            if fb.topic_labels:
                recent_topics.extend(fb.topic_labels)
        
        # Get unique topics
        recent_topics = list(set(recent_topics))[:5]
        
        sentiment_summary = {
            "avg_sentiment_30": latest_features.avg_sentiment_30,
            "neg_msg_count_30": latest_features.neg_msg_count_30,
            "recent_topics": recent_topics
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
            "churn_score": latest_prediction.churn_score,
            "churn_label": latest_prediction.churn_label,
            "top_reasons": latest_prediction.top_reasons,
            "model_version": latest_prediction.model_version,
            "as_of_date": latest_prediction.as_of_date.isoformat() if latest_prediction.as_of_date else None
        }
    
    return jsonify({
        "customer": customer.to_dict(),
        "rfm_features": rfm_features,
        "sentiment_summary": sentiment_summary,
        "transaction_summary": transaction_summary,
        "latest_prediction": prediction_data
    })


@customers_bp.route("/customers", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Customers"],
    "summary": "List customers",
    "description": "Get paginated list of customers",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "search",
            "in": "query",
            "type": "string",
            "description": "Search by name or city"
        },
        {
            "name": "is_active",
            "in": "query",
            "type": "boolean",
            "description": "Filter by active status"
        },
        {
            "name": "limit",
            "in": "query",
            "type": "integer",
            "default": 20
        },
        {
            "name": "offset",
            "in": "query",
            "type": "integer",
            "default": 0
        }
    ],
    "responses": {
        200: {"description": "List of customers"}
    }
})
def list_customers():
    """List customers with search and pagination"""
    search = request.args.get("search")
    is_active = request.args.get("is_active")
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    
    offset, limit = validate_pagination(offset // limit + 1 if offset else 1, limit)
    
    query = Customer.query
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                Customer.name.ilike(search_filter),
                Customer.city.ilike(search_filter)
            )
        )
    
    if is_active is not None:
        is_active_bool = is_active.lower() in ["true", "1", "yes"]
        query = query.filter_by(is_active=is_active_bool)
    
    total = query.count()
    customers = query.order_by(Customer.name).offset(offset).limit(limit).all()
    
    return jsonify({
        "total": total,
        "customers": [c.to_dict() for c in customers]
    })


@customers_bp.route("/customers/<customer_id>", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Customers"],
    "summary": "Get customer details",
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
        200: {"description": "Customer details"},
        404: {"description": "Customer not found"}
    }
})
def get_customer(customer_id: str):
    """Get customer details"""
    customer_uuid = validate_uuid(customer_id, "customer_id")
    
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    
    return jsonify(customer.to_dict())


@customers_bp.route("/customers", methods=["POST"])
@jwt_required()
@swag_from({
    "tags": ["Customers"],
    "summary": "Create customer",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "city": {"type": "string"},
                    "consent_given": {"type": "boolean"}
                },
                "required": ["name"]
            }
        }
    ],
    "responses": {
        201: {"description": "Customer created"},
        400: {"description": "Validation error"}
    }
})
def create_customer():
    """Create a new customer"""
    data = request.get_json()
    
    if not data:
        raise ValidationError("Request body is required")
    
    validate_required_fields(data, ["name"])
    
    # Hash phone if provided
    phone_hash = None
    if data.get("phone"):
        phone_hash = hash_phone_number(data["phone"])
        
        # Check for duplicate
        existing = Customer.query.filter_by(phone_hash=phone_hash).first()
        if existing:
            raise ValidationError("Customer with this phone already exists")
    
    customer = Customer(
        name=data["name"],
        phone_hash=phone_hash,
        city=data.get("city"),
        consent_given=data.get("consent_given", False)
    )
    
    db.session.add(customer)
    db.session.commit()
    
    current_app.logger.info(f"Created customer: {customer.customer_id}")
    
    return jsonify(customer.to_dict()), 201


@customers_bp.route("/customers/<customer_id>", methods=["PATCH"])
@jwt_required()
@swag_from({
    "tags": ["Customers"],
    "summary": "Update customer",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "customer_id",
            "in": "path",
            "type": "string",
            "required": True
        },
        {
            "name": "body",
            "in": "body",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "city": {"type": "string"},
                    "is_active": {"type": "boolean"},
                    "consent_given": {"type": "boolean"}
                }
            }
        }
    ],
    "responses": {
        200: {"description": "Customer updated"},
        404: {"description": "Customer not found"}
    }
})
def update_customer(customer_id: str):
    """Update customer details"""
    customer_uuid = validate_uuid(customer_id, "customer_id")
    
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    
    data = request.get_json()
    if not data:
        raise ValidationError("Request body is required")
    
    # Update allowed fields
    if "name" in data:
        customer.name = data["name"]
    if "city" in data:
        customer.city = data["city"]
    if "is_active" in data:
        customer.is_active = data["is_active"]
    if "consent_given" in data:
        customer.consent_given = data["consent_given"]
    
    db.session.commit()
    
    return jsonify(customer.to_dict())


@customers_bp.route("/customers/<customer_id>", methods=["DELETE"])
@jwt_required()
@swag_from({
    "tags": ["Customers"],
    "summary": "Delete customer (Right to be Forgotten)",
    "description": "Permanently delete customer and all associated data",
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
        200: {"description": "Customer deleted"},
        404: {"description": "Customer not found"}
    }
})
def delete_customer(customer_id: str):
    """
    Delete customer (Right to be Forgotten)
    
    Cascades to:
    - Transactions
    - Feedback (raw and clean)
    - Features
    - Predictions
    - Actions
    """
    customer_uuid = validate_uuid(customer_id, "customer_id")
    
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")
    
    # Log deletion for audit
    current_app.logger.warning(
        f"Deleting customer {customer_id} and all associated data (Right to be Forgotten)"
    )
    
    # Delete customer (cascade deletes related records)
    db.session.delete(customer)
    db.session.commit()
    
    return jsonify({
        "message": "Customer and all associated data deleted",
        "customer_id": customer_id
    })
