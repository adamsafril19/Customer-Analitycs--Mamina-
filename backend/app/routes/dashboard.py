"""
Dashboard Routes
REVISED: Uses new ontology, no storytelling
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from app import db
from app.models.customer import Customer
from app.models.prediction import ChurnPrediction
from app.models.feedback import FeedbackFeatures
from app.models.numeric_features import CustomerNumericFeatures
from app.models.text_semantics import CustomerTextSemantics
from app.models.topic import ShapCache
from app.models.action import Action

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard/stats", methods=["GET", "OPTIONS"])
def get_dashboard_stats():
    """Get dashboard statistics"""
    if request.method == "OPTIONS":
        return jsonify({}), 200
    
    try:
        total_customers = Customer.query.filter_by(is_active=True).count()
        
        high_risk = ChurnPrediction.query.filter_by(churn_label="high").count()
        medium_risk = ChurnPrediction.query.filter_by(churn_label="medium").count()
        low_risk = ChurnPrediction.query.filter_by(churn_label="low").count()
        
        total_predictions = high_risk + medium_risk + low_risk
        churn_rate = (high_risk / total_predictions * 100) if total_predictions > 0 else 0
        
        avg_churn_score = db.session.query(
            func.avg(ChurnPrediction.churn_score)
        ).scalar() or 0
        
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        new_predictions_7d = ChurnPrediction.query.filter(
            ChurnPrediction.created_at >= seven_days_ago
        ).count()
        
        pending_actions = Action.query.filter_by(status="pending").count()
        
        return jsonify({
            "success": True,
            "data": {
                "total_customers": total_customers,
                "churn_rate": round(churn_rate, 2),
                "high_risk_count": high_risk,
                "at_risk_count": high_risk,
                "medium_risk_count": medium_risk,
                "low_risk_count": low_risk,
                "avg_churn_score": round(float(avg_churn_score), 3),
                "new_predictions_7d": new_predictions_7d,
                "pending_actions": pending_actions,
                "last_updated": datetime.utcnow().isoformat()
            }
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/dashboard/trend", methods=["GET", "OPTIONS"])
def get_churn_trend():
    """Get churn trend over time"""
    if request.method == "OPTIONS":
        return jsonify({}), 200
    
    try:
        days = request.args.get("days", 30, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        predictions = db.session.query(
            func.date(ChurnPrediction.created_at).label('date'),
            func.count(ChurnPrediction.pred_id).label('total'),
            func.sum(
                db.case(
                    (ChurnPrediction.churn_label == 'high', 1),
                    else_=0
                )
            ).label('high_risk')
        ).filter(
            ChurnPrediction.created_at >= start_date
        ).group_by(
            func.date(ChurnPrediction.created_at)
        ).order_by(
            func.date(ChurnPrediction.created_at)
        ).all()
        
        trend_data = []
        for pred in predictions:
            trend_data.append({
                "date": str(pred.date),
                "total": pred.total,
                "high_risk": pred.high_risk or 0,
                "churn_rate": round((pred.high_risk or 0) / pred.total * 100, 2) if pred.total > 0 else 0
            })
        
        return jsonify({"success": True, "data": trend_data}), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/dashboard/top-drivers", methods=["GET", "OPTIONS"])
def get_top_churn_drivers():
    """Get top churn drivers from SHAP values"""
    if request.method == "OPTIONS":
        return jsonify({}), 200
    
    try:
        # Get SHAP values from high-risk predictions
        high_risk_preds = ChurnPrediction.query.filter_by(churn_label="high").limit(100).all()
        
        feature_impacts = {}
        for pred in high_risk_preds:
            if pred.shap_cache and pred.shap_cache.shap_values:
                for item in pred.shap_cache.shap_values:
                    feature = item.get("feature", "unknown")
                    contribution = abs(item.get("contribution", 0))
                    if feature in feature_impacts:
                        feature_impacts[feature]["count"] += 1
                        feature_impacts[feature]["total"] += contribution
                    else:
                        feature_impacts[feature] = {"count": 1, "total": contribution}
        
        sorted_drivers = sorted(
            feature_impacts.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:10]
        
        drivers = [
            {
                "feature": feature,
                "count": data["count"],
                "avg_contribution": round(data["total"] / data["count"], 3) if data["count"] > 0 else 0
            }
            for feature, data in sorted_drivers
        ]
        
        if not drivers:
            drivers = [
                {"feature": "recency_days", "count": 0, "avg_contribution": 0.3},
                {"feature": "complaint_rate_30d", "count": 0, "avg_contribution": 0.25},
                {"feature": "tx_count_30d", "count": 0, "avg_contribution": 0.2}
            ]
        
        return jsonify({"success": True, "data": drivers}), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/dashboard/at-risk-customers", methods=["GET", "OPTIONS"])
def get_at_risk_customers():
    """Get list of at-risk customers"""
    if request.method == "OPTIONS":
        return jsonify({}), 200
    
    try:
        limit = request.args.get("limit", 10, type=int)
        
        at_risk = db.session.query(
            Customer, ChurnPrediction
        ).join(
            ChurnPrediction, Customer.customer_id == ChurnPrediction.customer_id
        ).filter(
            ChurnPrediction.churn_label == "high",
            Customer.is_active == True
        ).order_by(
            desc(ChurnPrediction.churn_score)
        ).limit(limit).all()
        
        customers = []
        for customer, prediction in at_risk:
            customers.append({
                "customer_id": str(customer.customer_id),
                "name": customer.name,
                "churn_score": round(prediction.churn_score, 3),
                "churn_label": prediction.churn_label,
                "created_at": customer.created_at.isoformat() if customer.created_at else None
            })
        
        return jsonify({"success": True, "data": customers}), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/dashboard/sentiment-summary", methods=["GET", "OPTIONS"])
def get_sentiment_summary():
    """Get sentiment summary from customer_text_semantics"""
    if request.method == "OPTIONS":
        return jsonify({}), 200
    
    try:
        # Get sentiment from customer_text_semantics
        semantics = CustomerTextSemantics.query.limit(100).all()
        
        summary = {"positive": 0, "neutral": 0, "negative": 0}
        
        for s in semantics:
            if s.sentiment_dist:
                for label, count in s.sentiment_dist.items():
                    if label in summary:
                        summary[label] += count
        
        total = sum(summary.values())
        
        return jsonify({
            "success": True,
            "data": {
                "counts": summary,
                "total": total,
                "percentages": {
                    k: round(v / total * 100, 2) if total > 0 else 0
                    for k, v in summary.items()
                }
            }
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
