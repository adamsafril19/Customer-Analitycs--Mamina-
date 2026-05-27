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
from app.models.action import Action
from app.models.prediction import ChurnPrediction
from app.models.transaction import Transaction
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
        "risk_score": round(churn_score, 4),
        "risk_label": churn_label,
        "model_version": ml_service.get_model_version(),
        "as_of_date": today.isoformat(),
        "shap_values": shap_values
    })


@predictions_bp.route("/predictions", methods=["GET"])
@jwt_required()
def list_predictions():
    """List churn predictions with filtering and pagination"""
    label = request.args.get("label")
    sort = request.args.get("sort", "priority")
    order = request.args.get("order", "desc")
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    page = request.args.get("page", type=int)
    if page and page > 0:
        offset = (page - 1) * limit
    
    latest_pred = db.session.query(
        ChurnPrediction.customer_id,
        db.func.max(ChurnPrediction.created_at).label("max_created")
    ).group_by(ChurnPrediction.customer_id).subquery()

    query = ChurnPrediction.query.join(
        latest_pred,
        db.and_(
            ChurnPrediction.customer_id == latest_pred.c.customer_id,
            ChurnPrediction.created_at == latest_pred.c.max_created,
        )
    )
    
    if label:
        validate_enum(label, ["low", "medium", "high"], "label")
        query = query.filter(ChurnPrediction.churn_label == label)
    
    total = query.count()

    if sort == "name":
        query = query.join(Customer, Customer.customer_id == ChurnPrediction.customer_id)
        order_col = Customer.name.asc() if order == "asc" else Customer.name.desc()
        query = query.order_by(order_col)
    else:
        order_col = ChurnPrediction.churn_score.asc() if order == "asc" else ChurnPrediction.churn_score.desc()
        query = query.order_by(order_col)

    predictions = query.offset(offset).limit(limit).all()

    customer_ids = [p.customer_id for p in predictions]
    customers = {}
    latest_features = {}
    feature_maps = {}
    latest_actions = {}
    last_visits = {}
    if customer_ids:
        feature_service = FeatureService()
        display_as_of_date = feature_service.get_default_as_of_date()
        customers = {
            c.customer_id: c
            for c in Customer.query.filter(Customer.customer_id.in_(customer_ids)).all()
        }
        numeric_rows = CustomerNumericFeatures.query.filter(
            CustomerNumericFeatures.customer_id.in_(customer_ids)
        ).order_by(CustomerNumericFeatures.as_of_date.desc()).all()
        for row in numeric_rows:
            if row.customer_id not in latest_features:
                latest_features[row.customer_id] = row
        for customer_id in customer_ids:
            feature_maps[customer_id] = (
                feature_service.get_ml_feature_dict(str(customer_id), display_as_of_date) or {}
            )

        action_rows = Action.query.filter(
            Action.customer_id.in_(customer_ids)
        ).order_by(Action.created_at.desc()).all()
        for action in action_rows:
            if action.customer_id not in latest_actions:
                latest_actions[action.customer_id] = action

        tx_rows = db.session.query(
            Transaction.customer_id,
            db.func.max(Transaction.tx_date).label("last_visit")
        ).filter(
            Transaction.customer_id.in_(customer_ids),
            Transaction.status == "completed"
        ).group_by(Transaction.customer_id).all()
        last_visits = {
            customer_id: last_visit
            for customer_id, last_visit in tx_rows
        }

    def _explanation_payload(prediction: ChurnPrediction):
        cache = prediction.shap_cache
        shap_available = bool(cache and cache.explanation_type == "shap" and cache.shap_top)
        reasons = cache.shap_top if shap_available else []
        if reasons:
            first = reasons[0]
            if isinstance(first, dict):
                top_reason = first.get("description") or first.get("reason") or first.get("feature")
                top_feature = first.get("feature")
            else:
                top_reason = str(first)
                top_feature = None
            return {
                "explanation_available": True,
                "explanation_type": "shap",
                "explanation_status": "available",
                "top_reason": top_reason or "Faktor risiko utama tersedia",
                "top_feature": top_feature,
            }

        if cache and cache.shap_values:
            top_item = max(
                cache.shap_values,
                key=lambda item: abs(item.get("contribution", 0))
            )
            feature = top_item.get("feature")
            value = top_item.get("value")
            feature_labels = {
                "recency_days": "Sudah lama tidak berkunjung",
                "recency_ratio": "Kunjungan melewati pola biasanya",
                "frequency_trend_smoothed": "Tren frekuensi kunjungan menurun",
                "tx_count_90d": "Frekuensi transaksi 90 hari rendah",
                "spend_90d": "Nilai transaksi 90 hari rendah",
                "avg_tx_value": "Rata-rata nilai transaksi berubah",
                "complaint_ratio": "Rasio komplain meningkat",
                "avg_sentiment_score": "Sentimen pelanggan perlu diperhatikan",
                "msg_volatility": "Pola komunikasi tidak stabil",
                "response_delay_mean": "Waktu respon perlu dipercepat",
            }
            label = feature_labels.get(feature, feature or "Faktor risiko utama")
            suffix = f" ({value:.1f})" if isinstance(value, (int, float)) else ""
            return {
                "explanation_available": True,
                "explanation_type": cache.explanation_type or "shap_values",
                "explanation_status": "available",
                "top_reason": f"{label}{suffix}",
                "top_feature": feature,
            }

        return {
            "explanation_available": False,
            "explanation_type": cache.explanation_type if cache else None,
            "explanation_status": "SHAP explanation belum tersedia",
            "top_reason": None,
            "top_feature": None,
        }

    def _recommendation(top_feature, risk_label):
        if top_feature in ["recency_days", "recency_ratio"]:
            return {
                "action_type": "call",
                "label": "Hubungi personal untuk ajak booking ulang",
                "notes": "Customer sudah melewati pola kunjungan normal. Mulai dengan sapaan personal dan tawarkan jadwal yang tersedia.",
            }
        if top_feature in ["frequency_trend_smoothed", "tx_count_90d", "activity_mean", "recent_activity_avg"]:
            return {
                "action_type": "call",
                "label": "Kirim reminder jadwal perawatan rutin",
                "notes": "Aktivitas kunjungan menurun. Ingatkan jadwal treatment lanjutan atau paket rutin.",
            }
        if top_feature in ["spend_90d", "avg_tx_value", "spend_trend_smoothed"]:
            return {
                "action_type": "promo",
                "label": "Tawarkan promo atau bundling ringan",
                "notes": "Ada sinyal penurunan nilai transaksi. Tawarkan paket yang relevan dengan histori layanan.",
            }
        if top_feature in ["complaint_ratio", "avg_sentiment_score", "sentiment_trend"]:
            return {
                "action_type": "call",
                "label": "Follow-up keluhan sebelum promosi",
                "notes": "Ada sinyal sentimen/komplain. Prioritaskan klarifikasi pengalaman customer.",
            }
        if top_feature == "response_delay_mean":
            return {
                "action_type": "call",
                "label": "Respon cepat dan follow-up manual",
                "notes": "Customer terdampak keterlambatan respon. Hubungi dengan respons personal.",
            }

        if risk_label == "high":
            return {
                "action_type": "call",
                "label": "Hubungi customer high-risk hari ini",
                "notes": "Customer masuk prioritas risiko tinggi. Lakukan check-in dan tawarkan jadwal ulang.",
            }
        return {
            "action_type": "email",
            "label": "Pantau dan kirim check-in ringan",
            "notes": "Customer belum masuk prioritas tinggi. Lakukan check-in ringan bila diperlukan.",
        }

    def _urgency(prediction, recency_days, action):
        has_open_action = action and action.status in ["pending", "in_progress"]
        if has_open_action:
            return "in_progress", "Sudah ada follow-up aktif"
        if prediction.churn_label == "high" and (recency_days is None or recency_days >= 60):
            return "critical", "Prioritas hari ini"
        if prediction.churn_label == "high":
            return "high", "Perlu follow-up segera"
        if prediction.churn_label == "medium":
            return "medium", "Pantau minggu ini"
        return "low", "Monitoring"

    result = []
    for pred in predictions:
        item = pred.to_dict()
        customer = customers.get(pred.customer_id)
        features = latest_features.get(pred.customer_id)
        feature_map = feature_maps.get(pred.customer_id) or {}
        action = latest_actions.get(pred.customer_id)
        last_visit = last_visits.get(pred.customer_id)
        explanation = _explanation_payload(pred)
        recency_days = feature_map.get("recency_days")
        if recency_days is None and features:
            recency_days = features.recency_days
        urgency, urgency_label = _urgency(pred, recency_days, action)
        recommendation = _recommendation(explanation.get("top_feature"), pred.churn_label)

        item["customer_name"] = customer.name if customer else str(pred.customer_id)
        item["customer_city"] = customer.city if customer else None
        item["last_visit"] = last_visit.isoformat() if last_visit else None
        item["recency_days"] = round(float(recency_days), 1) if recency_days is not None else None
        item["tx_count_90d"] = feature_map.get("tx_count_90d", features.tx_count_90d if features else None)
        item["spend_90d"] = feature_map.get("spend_90d", features.spend_90d if features else None)
        item["urgency"] = urgency
        item["urgency_label"] = urgency_label
        item["recommended_action"] = recommendation
        item["latest_action"] = action.to_dict() if action else None
        item["work_status"] = action.status if action else "not_started"
        item.update(explanation)
        result.append(item)
    
    return jsonify({
        "total": total,
        "predictions": result
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
