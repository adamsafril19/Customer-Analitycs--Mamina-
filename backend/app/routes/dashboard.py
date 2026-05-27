"""
Dashboard Routes
REVISED: Uses new ontology, no storytelling
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import numpy as np
from app import db
from app.models.customer import Customer
from app.models.prediction import ChurnPrediction
from app.models.feedback import FeedbackFeatures
from app.models.numeric_features import CustomerNumericFeatures
from app.models.text_semantics import CustomerTextSemantics
from app.models.text_signals import CustomerTextSignals
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

        latest_pred = db.session.query(
            ChurnPrediction.customer_id,
            func.max(ChurnPrediction.created_at).label("max_created")
        ).group_by(ChurnPrediction.customer_id).subquery()

        latest_predictions = ChurnPrediction.query.join(
            latest_pred,
            db.and_(
                ChurnPrediction.customer_id == latest_pred.c.customer_id,
                ChurnPrediction.created_at == latest_pred.c.max_created,
            )
        )

        high_risk = latest_predictions.filter(ChurnPrediction.churn_label == "high").count()
        medium_risk = latest_predictions.filter(ChurnPrediction.churn_label == "medium").count()
        low_risk = latest_predictions.filter(ChurnPrediction.churn_label == "low").count()

        total_predictions = high_risk + medium_risk + low_risk
        high_risk_rate = (high_risk / total_predictions * 100) if total_predictions > 0 else 0

        avg_risk_score = db.session.query(
            func.avg(ChurnPrediction.churn_score)
        ).select_from(ChurnPrediction).join(
            latest_pred,
            db.and_(
                ChurnPrediction.customer_id == latest_pred.c.customer_id,
                ChurnPrediction.created_at == latest_pred.c.max_created,
            )
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
                "high_risk_rate": round(high_risk_rate, 2),
                "high_risk_count": high_risk,
                "at_risk_count": high_risk,
                "medium_risk_count": medium_risk,
                "low_risk_count": low_risk,
                "avg_risk_score": round(float(avg_risk_score), 3),
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
        
        latest_pred = db.session.query(
            ChurnPrediction.customer_id,
            func.max(ChurnPrediction.created_at).label("max_created")
        ).filter(
            ChurnPrediction.created_at >= start_date
        ).group_by(ChurnPrediction.customer_id).subquery()

        predictions = db.session.query(
            func.date(ChurnPrediction.created_at).label('date'),
            func.count(ChurnPrediction.pred_id).label('total'),
            func.sum(
                db.case(
                    (ChurnPrediction.churn_label == 'high', 1),
                    else_=0
                )
            ).label('high_risk')
        ).join(
            latest_pred,
            db.and_(
                ChurnPrediction.customer_id == latest_pred.c.customer_id,
                ChurnPrediction.created_at == latest_pred.c.max_created,
            )
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
                "risk_rate": round((pred.high_risk or 0) / pred.total * 100, 2) if pred.total > 0 else 0
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
        # Get SHAP values from latest high-risk predictions only
        latest_pred = db.session.query(
            ChurnPrediction.customer_id,
            func.max(ChurnPrediction.created_at).label("max_created")
        ).group_by(ChurnPrediction.customer_id).subquery()

        high_risk_preds = ChurnPrediction.query.join(
            latest_pred,
            db.and_(
                ChurnPrediction.customer_id == latest_pred.c.customer_id,
                ChurnPrediction.created_at == latest_pred.c.max_created,
            )
        ).filter(ChurnPrediction.churn_label == "high").limit(100).all()
        
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
        
        latest_pred = db.session.query(
            ChurnPrediction.customer_id,
            func.max(ChurnPrediction.created_at).label("max_created")
        ).group_by(ChurnPrediction.customer_id).subquery()

        at_risk = db.session.query(
            Customer, ChurnPrediction
        ).join(
            ChurnPrediction, Customer.customer_id == ChurnPrediction.customer_id
        ).join(
            latest_pred,
            db.and_(
                ChurnPrediction.customer_id == latest_pred.c.customer_id,
                ChurnPrediction.created_at == latest_pred.c.max_created,
            )
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
                "risk_score": round(prediction.churn_score, 3),
                "risk_label": prediction.churn_label,
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


@dashboard_bp.route("/dashboard/behavioral-insights", methods=["GET", "OPTIONS"])
def get_behavioral_insights():
    """
    Generate behavioral insights from actual ML data.

    Analyses:
    1. Top SHAP driver for high-risk customers
    2. Feature comparison between high-risk vs low-risk groups
    3. Sentiment signal from text semantics
    4. WhatsApp activity signal from text signals
    """
    if request.method == "OPTIONS":
        return jsonify({}), 200

    try:
        # --- Build latest-prediction subquery ---
        latest_pred = db.session.query(
            ChurnPrediction.customer_id,
            func.max(ChurnPrediction.created_at).label("max_created")
        ).group_by(ChurnPrediction.customer_id).subquery()

        latest_predictions = ChurnPrediction.query.join(
            latest_pred,
            db.and_(
                ChurnPrediction.customer_id == latest_pred.c.customer_id,
                ChurnPrediction.created_at == latest_pred.c.max_created,
            )
        )

        high_risk_preds = latest_predictions.filter(
            ChurnPrediction.churn_label == "high"
        ).all()
        low_risk_preds = latest_predictions.filter(
            ChurnPrediction.churn_label == "low"
        ).all()

        total_predicted = latest_predictions.count()
        high_count = len(high_risk_preds)
        low_count = len(low_risk_preds)

        insights = []

        # ================================================================
        # INSIGHT 1 — Top SHAP Driver
        # ================================================================
        feature_impacts = {}
        for pred in high_risk_preds:
            if pred.shap_cache and pred.shap_cache.shap_values:
                for item in pred.shap_cache.shap_values:
                    feat = item.get("feature", "unknown")
                    contrib = item.get("contribution", 0)
                    if feat not in feature_impacts:
                        feature_impacts[feat] = {"total": 0.0, "count": 0}
                    feature_impacts[feat]["total"] += abs(contrib)
                    feature_impacts[feat]["count"] += 1

        if feature_impacts:
            top_feature = max(
                feature_impacts.items(),
                key=lambda x: x[1]["total"] / max(x[1]["count"], 1)
            )
            top_name = top_feature[0]
            avg_impact = top_feature[1]["total"] / max(top_feature[1]["count"], 1)
            affected = top_feature[1]["count"]

            FEATURE_LABELS = {
                "recency_ratio": ("Rasio Waktu Kembali", "TrendingUp", "pink"),
                "recency_days": ("Hari Sejak Kunjungan Terakhir", "TrendingUp", "pink"),
                "frequency_trend_smoothed": ("Tren Frekuensi Kunjungan", "Users", "purple"),
                "spend_trend_smoothed": ("Tren Nilai Transaksi", "TrendingUp", "pink"),
                "tx_count_90d": ("Frekuensi Transaksi", "Users", "purple"),
                "spend_90d": ("Total Belanja", "TrendingUp", "pink"),
                "avg_tx_value": ("Rata-rata Nilai Transaksi", "TrendingUp", "pink"),
                "activity_mean": ("Rata-rata Aktivitas", "Users", "purple"),
                "activity_cv": ("Stabilitas Aktivitas", "AlertTriangle", "rose"),
                "complaint_ratio": ("Rasio Komplain", "AlertTriangle", "rose"),
                "avg_sentiment_score": ("Skor Sentimen", "Heart", "blue"),
                "sentiment_trend": ("Tren Sentimen", "Heart", "blue"),
                "msg_volatility": ("Volatilitas Pesan", "MessageSquare", "blue"),
                "trend_magnitude_interaction": ("Interaksi Tren & Aktivitas", "TrendingUp", "pink"),
            }

            label_info = FEATURE_LABELS.get(
                top_name, (top_name, "TrendingUp", "pink")
            )
            insights.append({
                "key": "top_shap_driver",
                "title": label_info[0],
                "icon": label_info[1],
                "color": label_info[2],
                "description": (
                    f"Fitur \"{label_info[0]}\" adalah faktor risiko utama. "
                    f"Rata-rata kontribusi SHAP sebesar {avg_impact:.3f} pada "
                    f"{affected} dari {high_count} pelanggan berisiko tinggi."
                ),
                "metric": round(avg_impact, 3),
                "affected": affected,
            })
        else:
            insights.append({
                "key": "top_shap_driver",
                "title": "Faktor Risiko Utama",
                "icon": "TrendingUp",
                "color": "pink",
                "description": "Belum ada data SHAP. Jalankan risk scoring terlebih dahulu.",
                "metric": None,
                "affected": 0,
            })

        # ================================================================
        # INSIGHT 2 — Recency/Frequency comparison high vs low risk
        # ================================================================
        def _avg_feature(preds, field):
            cids = [str(p.customer_id) for p in preds]
            if not cids:
                return None
            vals = db.session.query(
                getattr(CustomerNumericFeatures, field)
            ).filter(
                CustomerNumericFeatures.customer_id.in_(cids)
            ).all()
            numbers = [float(v[0]) for v in vals if v[0] is not None]
            return float(np.mean(numbers)) if numbers else None

        high_recency = _avg_feature(high_risk_preds, "recency_days")
        low_recency = _avg_feature(low_risk_preds, "recency_days")
        high_tx = _avg_feature(high_risk_preds, "tx_count_90d")
        low_tx = _avg_feature(low_risk_preds, "tx_count_90d")

        if high_recency is not None and low_recency is not None and low_recency > 0:
            recency_ratio = high_recency / low_recency
            insights.append({
                "key": "recency_comparison",
                "title": "Frekuensi Transaksi",
                "icon": "Users",
                "color": "purple",
                "description": (
                    f"Pelanggan berisiko tinggi rata-rata {high_recency:.0f} hari sejak kunjungan terakhir, "
                    f"{recency_ratio:.1f}x lebih lama dari pelanggan risiko rendah ({low_recency:.0f} hari). "
                    f"Rata-rata transaksi 90 hari: high-risk {high_tx:.1f} vs low-risk {low_tx:.1f}."
                ),
                "metric": round(recency_ratio, 1),
                "high_avg": round(high_recency, 1),
                "low_avg": round(low_recency, 1),
            })
        else:
            insights.append({
                "key": "recency_comparison",
                "title": "Frekuensi Transaksi",
                "icon": "Users",
                "color": "purple",
                "description": (
                    "Belum cukup data prediksi untuk membandingkan pola transaksi "
                    "antara pelanggan berisiko tinggi dan rendah."
                ),
                "metric": None,
                "high_avg": None,
                "low_avg": None,
            })

        # ================================================================
        # INSIGHT 3 — Sentiment signal
        # ================================================================
        high_cids = [str(p.customer_id) for p in high_risk_preds]
        low_cids = [str(p.customer_id) for p in low_risk_preds]

        def _avg_sentiment(cids):
            if not cids:
                return None
            rows = db.session.query(
                CustomerTextSemantics.avg_sentiment_score
            ).filter(
                CustomerTextSemantics.customer_id.in_(cids)
            ).all()
            vals = [float(r[0]) for r in rows if r[0] is not None]
            return float(np.mean(vals)) if vals else None

        high_sentiment = _avg_sentiment(high_cids)
        low_sentiment = _avg_sentiment(low_cids)

        if high_sentiment is not None and low_sentiment is not None:
            diff = low_sentiment - high_sentiment
            pct_lower = (diff / abs(low_sentiment) * 100) if low_sentiment != 0 else 0
            insights.append({
                "key": "sentiment_signal",
                "title": "Sinyal Sentimen",
                "icon": "AlertTriangle",
                "color": "rose",
                "description": (
                    f"Rata-rata skor sentimen pelanggan berisiko tinggi ({high_sentiment:.3f}) "
                    f"{'lebih rendah' if high_sentiment < low_sentiment else 'lebih tinggi'} "
                    f"dibanding risiko rendah ({low_sentiment:.3f}). "
                    f"Selisih {abs(pct_lower):.1f}%."
                ),
                "metric": round(high_sentiment, 3),
                "high_avg": round(high_sentiment, 3),
                "low_avg": round(low_sentiment, 3),
            })
        else:
            insights.append({
                "key": "sentiment_signal",
                "title": "Sinyal Sentimen",
                "icon": "AlertTriangle",
                "color": "rose",
                "description": "Belum ada data sentimen. Jalankan NLP Processing terlebih dahulu.",
                "metric": None,
                "high_avg": None,
                "low_avg": None,
            })

        # ================================================================
        # INSIGHT 4 — WhatsApp activity signal
        # ================================================================
        def _avg_msg_count(cids):
            if not cids:
                return None
            rows = db.session.query(
                CustomerTextSignals.msg_count_30d
            ).filter(
                CustomerTextSignals.customer_id.in_(cids)
            ).all()
            vals = [float(r[0]) for r in rows if r[0] is not None]
            return float(np.mean(vals)) if vals else None

        def _avg_complaint_rate(cids):
            if not cids:
                return None
            rows = db.session.query(
                CustomerTextSignals.complaint_rate_30d
            ).filter(
                CustomerTextSignals.customer_id.in_(cids)
            ).all()
            vals = [float(r[0]) for r in rows if r[0] is not None]
            return float(np.mean(vals)) if vals else None

        high_msg = _avg_msg_count(high_cids)
        low_msg = _avg_msg_count(low_cids)
        high_complaint = _avg_complaint_rate(high_cids)

        if high_msg is not None and low_msg is not None:
            msg_diff = low_msg - high_msg
            msg_pct = (msg_diff / low_msg * 100) if low_msg > 0 else 0
            complaint_str = ""
            if high_complaint is not None:
                complaint_str = f" Rasio komplain pelanggan berisiko tinggi: {high_complaint:.1%}."

            insights.append({
                "key": "whatsapp_activity",
                "title": "Aktivitas WhatsApp",
                "icon": "Baby",
                "color": "blue",
                "description": (
                    f"Pelanggan berisiko tinggi rata-rata mengirim {high_msg:.1f} pesan/30 hari, "
                    f"{'lebih sedikit' if high_msg < low_msg else 'lebih banyak'} "
                    f"dibanding risiko rendah ({low_msg:.1f} pesan). "
                    f"Selisih {abs(msg_pct):.0f}%.{complaint_str}"
                ),
                "metric": round(high_msg, 1),
                "high_avg": round(high_msg, 1),
                "low_avg": round(low_msg, 1),
            })
        else:
            insights.append({
                "key": "whatsapp_activity",
                "title": "Aktivitas WhatsApp",
                "icon": "Baby",
                "color": "blue",
                "description": "Belum ada data aktivitas pesan. Jalankan NLP Processing terlebih dahulu.",
                "metric": None,
                "high_avg": None,
                "low_avg": None,
            })

        return jsonify({
            "success": True,
            "data": {
                "insights": insights,
                "summary": {
                    "total_predicted": total_predicted,
                    "high_risk_count": high_count,
                    "low_risk_count": low_count,
                },
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
