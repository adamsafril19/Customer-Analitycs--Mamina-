import hashlib
import logging
import os
import sys
from datetime import datetime

import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SKIP_ML_LOAD', 'true')

from app import create_app, db
from app.models.ml_registry import MLModelRegistry
from app.models.topic import ModelVersion
from app.services.feature_service import FeatureService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def restore():
    app = create_app()
    with app.app_context():
        metadata_path = "models/model_metadata.pkl"
        if not os.path.exists(metadata_path):
            alt_path = "/app/models/model_metadata.pkl"
            if os.path.exists(alt_path):
                metadata_path = alt_path
            else:
                raise FileNotFoundError(f"Model metadata not found at {metadata_path} or {alt_path}")

        meta = joblib.load(metadata_path)
        version = meta.get("model_version", "v20260902_130504")
        metrics = meta.get("metrics", {})
        model_path = "models/multimodal_model.pkl"
        if not os.path.exists(model_path) and os.path.exists(f"/app/{model_path}"):
            model_path = f"/app/{model_path}"

        with open(model_path, "rb") as f:
            model_hash = hashlib.sha256(f.read()).hexdigest()[:16]

        shap_path = "models/shap_explainer.pkl"
        if not os.path.exists(shap_path) and os.path.exists(f"/app/{shap_path}"):
            shap_path = f"/app/{shap_path}"
        shap_hash = None
        if os.path.exists(shap_path):
            with open(shap_path, "rb") as f:
                shap_hash = hashlib.sha256(f.read()).hexdigest()[:16]

        # 1. Update/insert ModelVersion
        mv = ModelVersion.query.filter_by(model_version=version).first()
        if not mv:
            mv = ModelVersion(model_version=version)
            db.session.add(mv)
        mv.model_path = "models/multimodal_model.pkl"
        mv.metrics = metrics
        trained_at_str = meta.get("trained_at")
        if trained_at_str:
            try:
                mv.trained_at = datetime.fromisoformat(trained_at_str)
            except Exception:
                mv.trained_at = datetime.utcnow()
        else:
            mv.trained_at = datetime.utcnow()
        mv.deployed = True

        # 2. Deactivate other models and set research model active in MLModelRegistry
        MLModelRegistry.query.filter_by(is_active=True).update({"is_active": False})
        reg = MLModelRegistry.query.filter_by(model_hash=model_hash).first()
        if not reg:
            reg = MLModelRegistry(model_hash=model_hash)
            db.session.add(reg)
        reg.is_active = True
        reg.model_version = version
        reg.model_name = "gated_transaction_xgb_logistic"
        reg.feature_schema_hash = FeatureService.get_feature_schema_hash()
        reg.feature_names = FeatureService.get_feature_names()
        reg.expected_feature_count = len(reg.feature_names)
        reg.training_data_count = metrics.get("production_refit_size") or metrics.get("train_size", 16040)
        reg.training_date = mv.trained_at
        reg.shap_explainer_hash = shap_hash
        reg.notes = "Official Thesis Research Model: Gated transaction XGBoost with regularized logistic communication adjustment."

        db.session.commit()

        logger.info("Successfully restored and activated thesis research model %s!", version)
        logger.info("Metrics: ROC-AUC=%.4f, PR-AUC=%.4f, F1=%.4f", 
                    metrics.get("roc_auc", 0), metrics.get("pr_auc", 0), metrics.get("f1_score", 0))


if __name__ == '__main__':
    restore()
