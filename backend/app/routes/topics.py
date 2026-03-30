"""
Topics API Endpoints (Milestone 3)

Provides:
- GET /api/topics - List all topics with keywords
- GET /api/topics/{id} - Get single topic details
- GET /api/topics/lift - Get topic-churn lift analysis
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from flasgger import swag_from
from sqlalchemy import func

from app import db
from app.models.topic import Topic
from app.models.feedback import FeedbackFeatures
from app.models.prediction import ChurnPrediction
from app.utils.errors import NotFoundError
from app.utils.validators import validate_uuid

topics_bp = Blueprint("topics", __name__)


@topics_bp.route("/topics", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Topics"],
    "summary": "List all topics",
    "description": "Get all topic clusters with keywords and message counts",
    "security": [{"Bearer": []}],
    "responses": {
        200: {
            "description": "List of topics",
            "schema": {
                "type": "object",
                "properties": {
                    "topics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic_id": {"type": "string"},
                                "name": {"type": "string"},
                                "top_keywords": {"type": "array"},
                                "message_count": {"type": "integer"}
                            }
                        }
                    }
                }
            }
        }
    }
})
def list_topics():
    """List all topics with message counts"""
    topics = Topic.query.all()
    
    # Get message counts per topic
    topic_counts = dict(
        db.session.query(
            FeedbackFeatures.topic_id,
            func.count(FeedbackFeatures.feature_id)
        ).filter(
            FeedbackFeatures.topic_id.isnot(None)
        ).group_by(FeedbackFeatures.topic_id).all()
    )
    
    result = []
    for topic in topics:
        topic_data = topic.to_dict()
        topic_data["message_count"] = topic_counts.get(topic.topic_id, 0)
        result.append(topic_data)
    
    # Sort by message count descending
    result.sort(key=lambda x: x["message_count"], reverse=True)
    
    return jsonify({
        "topics": result,
        "total": len(result)
    })


@topics_bp.route("/topics/<topic_id>", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Topics"],
    "summary": "Get topic details",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "topic_id",
            "in": "path",
            "type": "string",
            "required": True
        }
    ],
    "responses": {
        200: {"description": "Topic details"},
        404: {"description": "Topic not found"}
    }
})
def get_topic(topic_id: str):
    """Get single topic details with sample messages"""
    topic_uuid = validate_uuid(topic_id, "topic_id")
    
    topic = Topic.query.get(topic_uuid)
    if not topic:
        raise NotFoundError(f"Topic {topic_id} not found")
    
    # Get sample messages
    sample_messages = db.session.query(
        FeedbackFeatures.feature_id,
        FeedbackFeatures.sentiment_label
    ).filter(
        FeedbackFeatures.topic_id == topic_uuid
    ).limit(10).all()
    
    result = topic.to_dict()
    result["sample_message_count"] = len(sample_messages)
    
    # Get sentiment distribution for this topic
    sentiment_dist = dict(
        db.session.query(
            FeedbackFeatures.sentiment_label,
            func.count(FeedbackFeatures.feature_id)
        ).filter(
            FeedbackFeatures.topic_id == topic_uuid,
            FeedbackFeatures.sentiment_label.isnot(None)
        ).group_by(FeedbackFeatures.sentiment_label).all()
    )
    result["sentiment_distribution"] = sentiment_dist
    
    return jsonify(result)


@topics_bp.route("/topics/lift", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Topics"],
    "summary": "Get topic-churn lift analysis",
    "description": "Analyze correlation between topics and churn risk",
    "security": [{"Bearer": []}],
    "responses": {
        200: {
            "description": "Topic lift analysis",
            "schema": {
                "type": "object",
                "properties": {
                    "topic_lifts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic_id": {"type": "string"},
                                "topic_name": {"type": "string"},
                                "lift": {"type": "number"},
                                "churn_rate": {"type": "number"},
                                "message_count": {"type": "integer"}
                            }
                        }
                    },
                    "baseline_churn_rate": {"type": "number"}
                }
            }
        }
    }
})
def get_topic_lift():
    """
    Calculate topic-churn lift
    
    Lift = P(churn | topic) / P(churn)
    > 1 means topic is associated with higher churn
    """
    # Get baseline churn rate
    total_predictions = ChurnPrediction.query.count()
    high_risk = ChurnPrediction.query.filter(
        ChurnPrediction.churn_label == 'high'
    ).count()
    
    baseline_churn_rate = high_risk / total_predictions if total_predictions > 0 else 0
    
    # Get all topics
    topics = Topic.query.all()
    
    topic_lifts = []
    
    for topic in topics:
        # Get customers who have messages with this topic
        customer_ids_with_topic = db.session.query(
            FeedbackFeatures.customer_id.distinct()
        ).filter(
            FeedbackFeatures.topic_id == topic.topic_id
        ).all()
        
        customer_ids = [c[0] for c in customer_ids_with_topic]
        
        if not customer_ids:
            continue
        
        # Get churn rate for these customers
        predictions = ChurnPrediction.query.filter(
            ChurnPrediction.customer_id.in_(customer_ids)
        ).all()
        
        if not predictions:
            continue
        
        high_risk_count = len([p for p in predictions if p.churn_label == 'high'])
        topic_churn_rate = high_risk_count / len(predictions)
        
        # Calculate lift
        lift = topic_churn_rate / baseline_churn_rate if baseline_churn_rate > 0 else 0
        
        # Get message count
        msg_count = FeedbackFeatures.query.filter(
            FeedbackFeatures.topic_id == topic.topic_id
        ).count()
        
        topic_lifts.append({
            "topic_id": str(topic.topic_id),
            "topic_name": topic.name,
            "top_keywords": topic.top_keywords[:5] if topic.top_keywords else [],
            "lift": round(lift, 3),
            "churn_rate": round(topic_churn_rate, 3),
            "message_count": msg_count,
            "customer_count": len(customer_ids)
        })
    
    # Sort by lift descending (highest risk topics first)
    topic_lifts.sort(key=lambda x: x["lift"], reverse=True)
    
    return jsonify({
        "topic_lifts": topic_lifts,
        "baseline_churn_rate": round(baseline_churn_rate, 3),
        "total_topics": len(topic_lifts)
    })
