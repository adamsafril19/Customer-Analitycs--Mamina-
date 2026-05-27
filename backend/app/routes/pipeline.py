"""
ML Pipeline endpoints for Behavioral Risk Scoring orchestration.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.services.pipeline_service import PipelineService
from app.utils.auth import admin_required

pipeline_bp = Blueprint("pipeline", __name__)


def _queue_task(task_func, *args, **kwargs):
    try:
        result = task_func.delay(*args, **kwargs)
        return jsonify({
            "task_id": result.id,
            "status": "queued",
            "timestamp": datetime.utcnow().isoformat(),
        }), 202
    except Exception as exc:
        return jsonify({
            "task_id": None,
            "status": "failed",
            "error": f"Background job tidak dapat diantrikan: {exc}",
            "timestamp": datetime.utcnow().isoformat(),
        }), 503


@pipeline_bp.route("/pipeline/status", methods=["GET"])
@jwt_required()
@admin_required
def get_pipeline_status():
    return jsonify(PipelineService().get_status())


@pipeline_bp.route("/pipeline/process-nlp", methods=["POST"])
@jwt_required()
@admin_required
def process_nlp():
    from app.tasks.pipeline_tasks import process_nlp_task

    return _queue_task(process_nlp_task)


@pipeline_bp.route("/pipeline/train-topic-model", methods=["POST"])
@jwt_required()
@admin_required
def train_topic_model():
    from app.tasks.pipeline_tasks import train_topic_model_task

    data = request.get_json(silent=True) or {}
    return _queue_task(
        train_topic_model_task,
        bool(data.get("overwrite", True)),
        bool(data.get("replace_topics", True)),
        data.get("source", "db"),
        data.get("csv_path"),
        int(data.get("min_chars", 15)),
        int(data.get("min_docs", 50)),
        int(data.get("target_topics", 30)),
    )


@pipeline_bp.route("/pipeline/generate-features", methods=["POST"])
@jwt_required()
@admin_required
def generate_features():
    from app.tasks.pipeline_tasks import generate_features_task

    return _queue_task(generate_features_task)


@pipeline_bp.route("/pipeline/run-scoring", methods=["POST"])
@jwt_required()
@admin_required
def run_scoring():
    from app.tasks.pipeline_tasks import run_scoring_task

    return _queue_task(run_scoring_task)


@pipeline_bp.route("/pipeline/retrain-model", methods=["POST"])
@jwt_required()
@admin_required
def retrain_model():
    from app.tasks.pipeline_tasks import retrain_model_task

    data = request.get_json(silent=True) or {}
    return _queue_task(
        retrain_model_task,
        data.get("cutoff_date"),
        int(data.get("churn_window", 90)),
        int(data.get("observation_window", 90)),
    )
