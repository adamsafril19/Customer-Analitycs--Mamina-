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
