"""
ML Pipeline and Model Evaluation services.

These services expose orchestration/status data for Behavioral Risk Scoring
without adding new persistence tables. Long-running execution is handled by
Celery tasks when available; evaluation metrics are read from existing model
metadata and prediction artifacts.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from flask import current_app
from sqlalchemy import func

from app import db
from app.models.customer import Customer
from app.models.feedback import FeedbackFeatures, FeedbackLinked, FeedbackRaw
from app.models.ml_registry import MLModelRegistry
from app.models.prediction import ChurnPrediction
from app.models.text_semantics import CustomerTextSemantics
from app.models.topic import ModelVersion, ShapCache, Topic
from app.services.explainer_service import ExplainerService
from app.models.transaction import Transaction
from app.services.feature_service import FeatureService


FEATURE_LABELS_ID = {
    "recency_ratio": "Rasio Keterlambatan Kunjungan",
    "frequency_trend_smoothed": "Tren Frekuensi Kunjungan",
    "spend_trend_smoothed": "Tren Nilai Transaksi",
    "msg_trend_smoothed": "Tren Komunikasi WhatsApp",
    "sentiment_trend": "Tren Sentimen",
    "recency_days": "Hari Sejak Transaksi Terakhir",
    "tx_count_90d": "Jumlah Transaksi 90 Hari",
    "spend_90d": "Total Belanja 90 Hari",
    "avg_tx_value": "Rata-rata Nilai Transaksi",
    "tenure_days": "Lama Menjadi Customer",
    "activity_mean": "Rata-rata Aktivitas",
    "recent_activity_avg": "Aktivitas Terkini",
    "activity_std": "Variasi Aktivitas",
    "activity_cv": "Stabilitas Aktivitas",
    "spend_volatility_cv": "Stabilitas Nilai Belanja",
    "trend_magnitude_interaction": "Interaksi Tren dan Aktivitas",
    "avg_sentiment_score": "Rata-rata Sentimen",
    "complaint_ratio": "Rasio Komplain",
    "msg_volatility": "Volatilitas Pesan",
    "response_delay_mean": "Rata-rata Waktu Respons",
}


class PipelineService:
    """Read pipeline status and run synchronous units used by Celery tasks."""

    def get_status(self) -> Dict[str, Any]:
        linked_count = FeedbackLinked.query.count()
        raw_count = FeedbackRaw.query.count()
        processed_messages = FeedbackFeatures.query.count()

        try:
            latest_prediction = ChurnPrediction.query.order_by(
                ChurnPrediction.created_at.desc()
            ).first()
        except Exception:
            latest_prediction = None

        # Scoring section — depends on ML model which may not be loaded
        try:
            risk_distribution = ModelEvaluationService().get_risk_distribution()
            scored_customers = sum(int(value or 0) for value in risk_distribution.values())
            scoring_data = {
                "status": "completed" if latest_prediction else "pending",
                "last_processed_at": latest_prediction.created_at.isoformat()
                if latest_prediction and latest_prediction.created_at else None,
                "processed": scored_customers,
                "failed": 0,
                "risk_distribution": risk_distribution,
            }
        except Exception:
            scoring_data = {
                "status": "unavailable",
                "last_processed_at": None,
                "processed": 0,
                "failed": 0,
                "risk_distribution": {"low": 0, "medium": 0, "high": 0},
                "error": "Model scoring belum tersedia",
            }

        # Model overview — depends on ML registry which may be empty
        try:
            model_data = ModelEvaluationService().get_model_overview()
        except Exception:
            model_data = {
                "model_version": None,
                "feature_schema_version": FeatureService.FEATURE_SCHEMA_VERSION,
                "feature_schema_hash": FeatureService.get_feature_schema_hash(),
                "training_date": None,
                "training_samples": None,
                "test_samples": None,
                "is_active": False,
                "error": "Model belum dimuat atau belum di-training",
            }

        feature_status = self._feature_snapshot_status()

        return {
            "import_linking": {
                "customers": Customer.query.count(),
                "active_customers": Customer.query.filter_by(is_active=True).count(),
                "transactions": Transaction.query.count(),
                "whatsapp_messages": raw_count,
                "linked_messages": linked_count,
                "unlinked_messages": max(raw_count - linked_count, 0),
            },
            "nlp": {
                "status": "completed" if processed_messages else "pending",
                "processed_messages": processed_messages,
                "failed_messages": 0,
                "unprocessed_linked_messages": max(linked_count - processed_messages, 0),
                "sentiment_distribution": self._sentiment_distribution(),
                "dominant_keywords": self._top_keywords(),
            },
            "topic_model": self._topic_model_status(),
            "features": {
                "status": "completed" if feature_status["latest_count"] else "pending",
                "feature_vectors": feature_status["latest_count"],
                "feature_snapshots_total": feature_status["total_count"],
                "latest_as_of_date": feature_status["latest_as_of_date"],
                "latest_snapshot_as_of_date": feature_status["latest_snapshot_as_of_date"],
                "schema_version": FeatureService.FEATURE_SCHEMA_VERSION,
                "feature_schema_hash": FeatureService.get_feature_schema_hash(),
                "expected_features": FeatureService.expected_feature_count(),
                "feature_names": FeatureService.get_feature_names(),
            },
            "scoring": scoring_data,
            "model": model_data,
        }

    def process_nlp(self) -> Dict[str, Any]:
        from app.services.message_feature_service import MessageFeatureService
        from app.services.semantic_service import SemanticService

        stats = {"total": 0, "processed": 0, "failed": 0, "errors": []}

        msg_service = MessageFeatureService()
        try:
            feature_stats = msg_service.process_unprocessed_messages(
                generate_embeddings=True,
                refresh_existing=True,
            )
            stats["total"] += int(feature_stats.get("total", 0))
            stats["processed"] += int(feature_stats.get("processed", 0))
            stats["failed"] += int(feature_stats.get("skipped", 0))
        except Exception as exc:
            db.session.rollback()
            stats["failed"] += 1
            stats["errors"].append(str(exc))

        semantic_service = SemanticService()
        try:
            semantic_service.ensure_models_loaded()
        except Exception as exc:
            db.session.rollback()
            stats["failed"] += 1
            stats["errors"].append(str(exc))
            return {
                **stats,
                "success": False,
                "sentiment_distribution": self._sentiment_distribution(),
                "dominant_keywords": self._top_keywords(),
                "dominant_topics": self._top_topics(),
                "error_summary": stats["errors"][:5],
            }

        as_of_date = FeatureService.get_default_as_of_date()
        customer_ids = [
            str(row[0])
            for row in db.session.query(FeedbackLinked.customer_id)
            .distinct()
            .all()
        ]
        for cid in customer_ids:
            try:
                semantic_service.populate_text_semantics(cid, as_of_date)
            except Exception as exc:
                db.session.rollback()
                stats["failed"] += 1
                if len(stats["errors"]) < 5:
                    stats["errors"].append(str(exc))

        return {
            **stats,
            "success": stats["failed"] == 0,
            "sentiment_distribution": self._sentiment_distribution(),
            "dominant_keywords": self._top_keywords(),
            "dominant_topics": self._top_topics(),
            "error_summary": stats["errors"][:5],
            "as_of_date": as_of_date.isoformat(),
        }

    def generate_features(self) -> Dict[str, Any]:
        service = FeatureService()
        customers = Customer.query.filter_by(is_active=True).all()
        processed = 0
        missing = 0
        failed = 0
        errors: List[str] = []
        samples: List[Dict[str, Any]] = []
        as_of_date = service.get_default_as_of_date()

        for customer in customers:
            cid = str(customer.customer_id)
            try:
                service.populate_all_features(cid, as_of_date)
                feature_dict = service.get_ml_feature_dict(cid, as_of_date)
                if not feature_dict or len(feature_dict) != FeatureService.expected_feature_count():
                    missing += 1
                    continue
                processed += 1
                if len(samples) < 5:
                    samples.append({
                        "customer_id": cid,
                        "customer_name": customer.name,
                        "recency_days": feature_dict.get("recency_days"),
                        "tx_count_90d": feature_dict.get("tx_count_90d"),
                        "spend_90d": feature_dict.get("spend_90d"),
                        "avg_sentiment_score": feature_dict.get("avg_sentiment_score"),
                    })
            except Exception as exc:
                db.session.rollback()
                failed += 1
                if len(errors) < 5:
                    errors.append(f"{cid}: {exc}")

        return {
            "success": failed == 0,
            "total_customers": len(customers),
            "processed": processed,
            "failed": failed,
            "missing_features": missing,
            "schema_version": FeatureService.FEATURE_SCHEMA_VERSION,
            "feature_schema_hash": FeatureService.get_feature_schema_hash(),
            "feature_names": FeatureService.get_feature_names(),
            "as_of_date": as_of_date.isoformat(),
            "sample_rows": samples,
            "error_summary": errors,
        }

    def run_scoring(self) -> Dict[str, Any]:
        from flask import current_app

        ml_service = current_app.config.get("ML_SERVICE")
        if not ml_service or not ml_service.is_model_loaded():
            raise RuntimeError("Model risk scoring belum dimuat")

        feature_service = FeatureService()
        explainer_service = ExplainerService(ml_service) if getattr(ml_service, "shap_explainer", None) else None
        customers = Customer.query.filter_by(is_active=True).all()
        processed = 0
        failed = 0
        explained = 0
        errors: List[str] = []
        labels = Counter()
        now = datetime.utcnow()
        as_of_date = feature_service.get_default_as_of_date()

        for customer in customers:
            cid = str(customer.customer_id)
            try:
                feature_service.populate_all_features(cid, as_of_date)
                features = feature_service.get_ml_feature_vector(cid, as_of_date)
                if not features:
                    raise RuntimeError("Feature vector belum tersedia")
                score, label = ml_service.predict(features)
                prediction = ChurnPrediction(
                    customer_id=customer.customer_id,
                    churn_score=score,
                    churn_label=label,
                    model_version=ml_service.get_model_version(),
                    as_of_date=as_of_date,
                    created_at=now,
                    features_used=features,
                    feature_as_of=now,
                    feature_schema_hash=FeatureService.get_feature_schema_hash(),
                    model_hash=ml_service.get_model_hash(),
                )
                db.session.add(prediction)
                db.session.flush()
                if explainer_service:
                    cache = explainer_service.compute_and_cache_shap(
                        pred_id=str(prediction.pred_id),
                        features=features,
                        customer_id=cid,
                        as_of=now,
                        explainer_version=ml_service.get_model_version(),
                    )
                    if cache:
                        explained += 1
                labels[label] += 1
                processed += 1
            except Exception as exc:
                db.session.rollback()
                failed += 1
                if len(errors) < 5:
                    errors.append(f"{cid}: {exc}")

        db.session.commit()
        return {
            "success": failed == 0,
            "total_customers": len(customers),
            "processed": processed,
            "failed": failed,
            "explained": explained,
            "risk_distribution": {
                "low": labels.get("low", 0),
                "medium": labels.get("medium", 0),
                "high": labels.get("high", 0),
            },
            "as_of_date": as_of_date.isoformat(),
            "last_processed_at": now.isoformat(),
            "error_summary": errors,
        }

    def _feature_snapshot_status(self) -> Dict[str, Any]:
        from app.models.numeric_features import CustomerNumericFeatures

        active_as_of = FeatureService.get_default_as_of_date()
        latest_snapshot_as_of = db.session.query(
            func.max(CustomerNumericFeatures.as_of_date)
        ).scalar()
        active_count = CustomerNumericFeatures.query.filter_by(
            as_of_date=active_as_of
        ).count()

        return {
            "latest_count": int(active_count),
            "total_count": int(CustomerNumericFeatures.query.count()),
            "latest_as_of_date": active_as_of.isoformat(),
            "latest_snapshot_as_of_date": latest_snapshot_as_of.isoformat() if latest_snapshot_as_of else None,
        }

    def _topic_model_status(self) -> Dict[str, Any]:
        configured_path = current_app.config.get("TOPIC_MODEL_PATH")
        path_exists = bool(configured_path and Path(configured_path).exists())
        training_lock_exists = Path("/app/models/.topic_model_training.lock").exists()
        latest_topic = Topic.query.order_by(Topic.created_at.desc()).first()
        latest_version = latest_topic.model_version if latest_topic else None
        topic_query = Topic.query
        if latest_version:
            topic_query = topic_query.filter(Topic.model_version == latest_version)
        topic_count = topic_query.count() if latest_version else 0

        if training_lock_exists:
            status = "processing"
        elif path_exists and topic_count:
            status = "completed"
        elif configured_path or topic_count:
            status = "partial"
        else:
            status = "pending"

        return {
            "status": status,
            "configured_path": configured_path,
            "model_exists": path_exists,
            "topic_count": int(topic_count),
            "model_version": latest_version,
            "latest_trained_at": latest_topic.created_at.isoformat() if latest_topic and latest_topic.created_at else None,
            "strict_required": bool(current_app.config.get("NLP_STRICT", True)),
            "training_active": training_lock_exists,
        }

    def _sentiment_distribution(self) -> Dict[str, int]:
        totals = Counter()
        rows = CustomerTextSemantics.query.filter(
            CustomerTextSemantics.sentiment_dist.isnot(None)
        ).all()
        for row in rows:
            for label, count in (row.sentiment_dist or {}).items():
                totals[label] += int(count or 0)
        return dict(totals)

    def _top_keywords(self, limit: int = 10) -> List[Dict[str, Any]]:
        totals = Counter()
        rows = CustomerTextSemantics.query.filter(
            CustomerTextSemantics.top_keywords.isnot(None)
        ).all()
        for row in rows:
            for keyword, count in (row.top_keywords or {}).items():
                totals[keyword] += int(count or 0)
        return [{"keyword": k, "count": v} for k, v in totals.most_common(limit)]

    def _top_topics(self, limit: int = 10) -> List[Dict[str, Any]]:
        totals = Counter()
        rows = CustomerTextSemantics.query.filter(
            CustomerTextSemantics.top_topic_counts.isnot(None)
        ).all()
        for row in rows:
            for topic, count in (row.top_topic_counts or {}).items():
                totals[str(topic)] += int(count or 0)
        return [{"topic": k, "count": v} for k, v in totals.most_common(limit)]


class ModelEvaluationService:
    """Expose model evaluation using existing persisted artifacts."""

    def get_model_overview(self) -> Dict[str, Any]:
        try:
            active = MLModelRegistry.get_active()
        except Exception:
            active = None
        try:
            latest = self._latest_model_version(active.model_version if active else None)
        except Exception:
            latest = None
        metrics = (latest.metrics if latest else None) or {}

        return {
            "model_version": active.model_version if active else (latest.model_version if latest else None),
            "feature_schema_version": FeatureService.FEATURE_SCHEMA_VERSION,
            "feature_schema_hash": active.feature_schema_hash if active else FeatureService.get_feature_schema_hash(),
            "training_date": (
                active.training_date.isoformat() if active and active.training_date
                else latest.trained_at.isoformat() if latest and latest.trained_at
                else None
            ),
            "training_samples": (
                active.training_data_count if active and active.training_data_count is not None
                else metrics.get("train_size")
            ),
            "test_samples": metrics.get("test_size"),
            "is_active": bool(active.is_active) if active else bool(latest and latest.deployed),
        }

    def get_evaluation(self) -> Dict[str, Any]:
        latest = self._latest_model_version()
        metrics = (latest.metrics if latest else None) or {}
        comparison = self._baseline_comparison(metrics)
        technical = {
            "roc_auc": metrics.get("roc_auc"),
            "pr_auc": metrics.get("pr_auc"),
            "precision": metrics.get("precision"),
            "recall": metrics.get("recall"),
            "f1_score": metrics.get("f1") or metrics.get("f1_score"),
        }
        available = any(value is not None for value in technical.values())

        return {
            "overview": self.get_model_overview(),
            "business_summary": self._business_summary(technical) if available else None,
            "technical_metrics": technical if available else None,
            "baseline_comparison": comparison,
            "comparison_interpretation": metrics.get("comparison_interpretation") or (
                self._comparison_interpretation(comparison) if comparison else None
            ),
            "model_metadata": metrics.get("model_metadata"),
            "metrics_available": available,
            "empty_message": None if available else "Belum tersedia. Jalankan Retrain Model terlebih dahulu.",
        }

    def get_threshold_sensitivity(self) -> Dict[str, Any]:
        latest = self._latest_model_version()
        metrics = (latest.metrics if latest else None) or {}
        rows = metrics.get("threshold_sensitivity") or metrics.get("thresholds") or []
        return {
            "rows": rows,
            "empty_message": None if rows else "Belum tersedia. Jalankan Retrain Model terlebih dahulu.",
        }

    def get_feature_importance(self) -> Dict[str, Any]:
        rows = self._importance_from_model()
        source = "model_feature_importances" if rows else None
        if not rows:
            rows = self._importance_from_shap()
            source = "shap_cache" if rows else None

        return {
            "source": source,
            "features": rows,
            "empty_message": None if rows else "Belum tersedia. Jalankan Retrain Model terlebih dahulu.",
        }

    def get_risk_distribution(self) -> Dict[str, int]:
        try:
            latest_per_customer = db.session.query(
                ChurnPrediction.customer_id,
                func.max(ChurnPrediction.created_at).label("created_at"),
            ).group_by(ChurnPrediction.customer_id).subquery()

            rows = db.session.query(ChurnPrediction.churn_label, func.count(ChurnPrediction.pred_id)).join(
                latest_per_customer,
                (ChurnPrediction.customer_id == latest_per_customer.c.customer_id)
                & (ChurnPrediction.created_at == latest_per_customer.c.created_at),
            ).group_by(ChurnPrediction.churn_label).all()

            counts = {"low": 0, "medium": 0, "high": 0}
            for label, count in rows:
                if label in counts:
                    counts[label] = int(count)
            return counts
        except Exception:
            return {"low": 0, "medium": 0, "high": 0}

    def _latest_model_version(self, version: Optional[str] = None) -> Optional[ModelVersion]:
        query = ModelVersion.query
        if version:
            found = query.filter_by(model_version=version).first()
            if found:
                return found
        return query.order_by(ModelVersion.trained_at.desc(), ModelVersion.created_at.desc()).first()

    def _business_summary(self, metrics: Dict[str, Optional[float]]) -> Dict[str, str]:
        recall = metrics.get("recall")
        f1 = metrics.get("f1_score")
        roc_auc = metrics.get("roc_auc")
        score = np.mean([v for v in [recall, f1, roc_auc] if v is not None]) if any(
            v is not None for v in [recall, f1, roc_auc]
        ) else None

        if score is None:
            status = "Perlu Perhatian"
        elif score >= 0.75:
            status = "Baik"
        elif score >= 0.6:
            status = "Cukup"
        else:
            status = "Perlu Perhatian"

        return {
            "performance_status": status,
            "risk_detection": "Model memiliki metrik evaluasi untuk mendukung deteksi pelanggan berisiko.",
            "usage_note": "Gunakan risk score untuk prioritisasi pelanggan, bukan keputusan otomatis.",
        }

    def _baseline_comparison(self, metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        baseline = metrics.get("baseline")
        multimodal = metrics.get("multimodal")
        improvement = metrics.get("improvement")
        if not baseline or not multimodal:
            return None

        metric_map = [
            ("roc_auc", "ROC-AUC"),
            ("pr_auc", "PR-AUC"),
            ("precision", "Precision"),
            ("recall", "Recall"),
            ("f1", "F1"),
        ]
        rows = []
        for key, label in metric_map:
            baseline_value = baseline.get(key)
            multimodal_value = multimodal.get(key)
            gain = (
                improvement.get(key)
                if isinstance(improvement, dict) and key in improvement
                else (
                    round(float(multimodal_value or 0) - float(baseline_value or 0), 4)
                    if baseline_value is not None and multimodal_value is not None
                    else None
                )
            )
            rows.append({
                "metric": key,
                "label": label,
                "baseline": baseline_value,
                "multimodal": multimodal_value,
                "improvement": gain,
            })

        return {
            "baseline": baseline,
            "multimodal": multimodal,
            "improvement": improvement,
            "rows": rows,
        }

    def _comparison_interpretation(self, comparison: Dict[str, Any]) -> str:
        gains = comparison.get("improvement") or {}
        roc_gain = float(gains.get("roc_auc", 0) or 0)
        f1_gain = float(gains.get("f1", 0) or 0)
        if roc_gain > 0 or f1_gain > 0:
            conclusion = "customer interaction signals contribute additional predictive value beyond transactional behavior."
        elif roc_gain == 0 and f1_gain == 0:
            conclusion = "customer interaction signals show no measurable incremental value in the current validation split."
        else:
            conclusion = "customer interaction signals reduce validation performance in the current split and should be reviewed for leakage, noise, or sample-size effects."
        return (
            f"Multimodal model changes ROC-AUC by {roc_gain:.3f} and "
            f"F1-Score by {f1_gain:.3f} compared to the transaction-only baseline. "
            f"This indicates that {conclusion}"
        )

    def _importance_from_model(self) -> List[Dict[str, Any]]:
        try:
            from flask import current_app

            ml_service = current_app.config.get("ML_SERVICE")
            model = getattr(ml_service, "model", None)
            importances = getattr(model, "feature_importances_", None)
            names = FeatureService.get_feature_names()
            if importances is None or len(importances) != len(names):
                return []
            rows = [
                {
                    "feature": name,
                    "label": FEATURE_LABELS_ID.get(name, name),
                    "importance": float(value),
                }
                for name, value in zip(names, importances)
            ]
            return sorted(rows, key=lambda row: row["importance"], reverse=True)
        except Exception:
            return []

    def _importance_from_shap(self) -> List[Dict[str, Any]]:
        totals: Dict[str, List[float]] = defaultdict(list)
        caches = ShapCache.query.filter(ShapCache.shap_values.isnot(None)).limit(500).all()
        for cache in caches:
            for item in cache.shap_values or []:
                feature = item.get("feature")
                contribution = item.get("contribution")
                if feature is not None and contribution is not None:
                    totals[feature].append(abs(float(contribution)))
        rows = [
            {
                "feature": feature,
                "label": FEATURE_LABELS_ID.get(feature, feature),
                "importance": float(np.mean(values)),
            }
            for feature, values in totals.items()
            if values
        ]
        return sorted(rows, key=lambda row: row["importance"], reverse=True)
