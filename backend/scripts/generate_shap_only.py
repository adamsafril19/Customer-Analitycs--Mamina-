import os
import sys
import joblib
import numpy as np
import logging
from datetime import date

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add backend directory to path if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models.customer import Customer
from app.services.feature_service import FeatureService
from app.services.shap_wrapper import (
    GatedRiskModel,
    RiskProbabilityModel,
    coerce_numeric_array,
)
import shap

def main():
    app = create_app()
    with app.app_context():
        logger.info("Loading existing models...")
        model_path = "models/multimodal_model.pkl"
        scaler_path = "models/scaler.pkl"
        
        if not os.path.exists(model_path) or not os.path.exists(scaler_path):
            logger.error("Model or scaler not found!")
            sys.exit(1)
            
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        
        logger.info("Fetching active customers...")
        customers = Customer.query.filter(
            Customer.is_active.is_(True),
            Customer.is_provisional.is_(False)
        ).limit(100).all()
        
        if not customers:
            logger.error("No active customers found!")
            sys.exit(1)
            
        feature_service = FeatureService()
        features_list = []
        
        logger.info("Generating feature vectors for SHAP background...")
        for customer in customers:
            cid = str(customer.customer_id)
            try:
                # Populate features to make sure they are up-to-date
                # but don't commit to DB to avoid mutating state
                feature_service.populate_all_features(cid, commit=False)
                vec = feature_service.get_ml_feature_vector(cid)
                if vec is not None and len(vec) == len(feature_service.get_feature_names()):
                    features_list.append(vec)
            except Exception as e:
                logger.warning(f"Error getting features for {cid}: {e}")
                
        if len(features_list) < 5:
            logger.error(f"Not enough valid features generated! Got only {len(features_list)}")
            sys.exit(1)
            
        logger.info(f"Generated {len(features_list)} sample vectors.")
        X_sample = np.array(features_list, dtype=np.float32)
        X_sample_scaled = scaler.transform(X_sample)
        
        logger.info("Creating SHAP explainer...")
        try:
            background_size = min(50, len(X_sample_scaled))
            test_size = min(2, len(X_sample_scaled))
            background = X_sample_scaled[:background_size]
            masker = shap.maskers.Independent(background, max_samples=background_size)
            
            # Use RiskProbabilityModel for agnostic explainer
            feature_names = feature_service.get_feature_names()
            
            # Identify neutralized indices (if any)
            neutralized_indices = []
            
            wrapped_model = RiskProbabilityModel(model, neutralized_indices)
            explainer = shap.Explainer(
                wrapped_model,
                masker,
                algorithm="permutation"
            )
            
            # Trigger explainer initialization
            _ = explainer(
                X_sample_scaled[:test_size],
                max_evals=(2 * X_sample_scaled.shape[1]) + 1,
                silent=True
            )
            logger.info("SHAP explainer created successfully.")
            
            shap_path = "models/shap_explainer.pkl"
            joblib.dump(explainer, shap_path)
            logger.info(f"Saved SHAP explainer to {shap_path}")
            
            # Also update model metadata if it exists
            meta_path = "models/model_metadata.pkl"
            if os.path.exists(meta_path):
                meta = joblib.load(meta_path)
                meta["shap_available"] = True
                meta["explanation_status"] = "available"
                if "artifact_paths" in meta:
                    meta["artifact_paths"]["shap"] = shap_path
                joblib.dump(meta, meta_path)
                logger.info("Updated model_metadata.pkl")
                
            # Update ModelVersion in DB
            from app.models.topic import ModelVersion
            latest = ModelVersion.query.filter(
                ModelVersion.model_path.ilike("%multimodal_model.pkl")
            ).order_by(ModelVersion.trained_at.desc()).first()
            if latest:
                metrics = latest.metrics or {}
                metrics["shap_available"] = True
                latest.metrics = metrics
                db.session.commit()
                logger.info("Updated ModelVersion in DB.")
                
        except Exception as e:
            logger.error(f"Failed to create SHAP explainer: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
