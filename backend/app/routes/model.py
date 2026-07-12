"""
Model evaluation endpoints for Behavioral Risk Scoring.
"""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from app.services.pipeline_service import ModelEvaluationService
from app.utils.auth import admin_required

model_bp = Blueprint("model", __name__)


@model_bp.route("/model/evaluation", methods=["GET"])
@jwt_required()
@admin_required
def get_model_evaluation():
    return jsonify(ModelEvaluationService().get_evaluation())


@model_bp.route("/model/feature-importance", methods=["GET"])
@jwt_required()
@admin_required
def get_feature_importance():
    return jsonify(ModelEvaluationService().get_feature_importance())


@model_bp.route("/model/threshold-sensitivity", methods=["GET"])
@jwt_required()
@admin_required
def get_threshold_sensitivity():
    return jsonify(ModelEvaluationService().get_threshold_sensitivity())


@model_bp.route("/model/risk-distribution", methods=["GET"])
@jwt_required()
@admin_required
def get_risk_distribution():
    return jsonify({
        "distribution": ModelEvaluationService().get_risk_distribution()
    })


@model_bp.route("/model/topic-evaluation", methods=["GET"])
@jwt_required()
@admin_required
def get_topic_evaluation():
    """
    Return the latest BERTopic clustering evaluation metrics.

    Reads from the model_versions table where notes = 'BERTopic clustering model',
    ordered by trained_at descending, and returns the metrics JSON field along
    with model metadata.
    """
    from app.models.topic import ModelVersion

    latest = (
        ModelVersion.query
        .filter(ModelVersion.notes == "BERTopic clustering model")
        .order_by(ModelVersion.trained_at.desc())
        .first()
    )

    if not latest:
        return jsonify({
            "available": False,
            "message": "Belum ada evaluasi clustering BERTopic. Jalankan Train Topic Model terlebih dahulu.",
        }), 200

    metrics = latest.metrics or {}
    return jsonify({
        "available": True,
        "model_version": latest.model_version,
        "model_path": latest.model_path,
        "trained_at": latest.trained_at.isoformat() if latest.trained_at else None,
        # --- Core metrics ---
        "outlier_rate": metrics.get("outlier_rate"),
        "n_outliers": metrics.get("n_outliers"),
        "n_docs": metrics.get("n_docs"),
        "n_topics_found": metrics.get("n_topics_found"),
        "topic_diversity": metrics.get("topic_diversity"),
        "silhouette_score": metrics.get("silhouette_score"),
        "silhouette_cluster_space": metrics.get("silhouette_cluster_space"),
        "silhouette_embedding_space": metrics.get("silhouette_embedding_space"),
        "silhouette_sampled": metrics.get("silhouette_sampled", False),
        "silhouette_n": metrics.get("silhouette_n"),
        # --- Warnings ---
        "evaluation_warnings": metrics.get("evaluation_warnings", []),
        # --- Error passthrough ---
        "evaluation_error": metrics.get("evaluation_error"),
    }), 200
