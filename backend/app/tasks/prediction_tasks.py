"""
Prediction Celery Tasks

UPDATED (Milestone 3): Added compute_shap_task with shap_cache and nearest_messages

Background tasks for:
- Batch predictions
- SHAP calculations with caching
"""
import logging
from datetime import date
from typing import List, Optional

from app.tasks import celery_app
from app import db

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="prediction.batch_predict_churn")
def batch_predict_churn(self, customer_ids: Optional[List[str]] = None):
    """
    Run batch churn predictions
    
    Args:
        customer_ids: Optional list of customer IDs (None = all active customers)
        
    Returns:
        Processing statistics
    """
    from app.services.ml_service import MLService
    from app.services.explainer_service import ExplainerService
    from app.services.feature_service import FeatureService
    from app.models.customer import Customer
    from app.models.prediction import ChurnPrediction
    
    logger.info(f"Starting batch prediction for {len(customer_ids) if customer_ids else 'all'} customers")
    
    try:
        self.update_state(state="PROGRESS", meta={"progress": 5})
        
        # Get services
        ml_service = MLService()
        if not ml_service.is_model_loaded():
            logger.error("Model not loaded, cannot run batch predictions")
            return {"error": "Model not loaded"}
        
        explainer_service = ExplainerService(ml_service)
        feature_service = FeatureService()
        
        # Get customer IDs if not provided
        if customer_ids is None:
            customers = Customer.query.filter_by(is_active=True).all()
            customer_ids = [str(c.customer_id) for c in customers]
        
        total = len(customer_ids)
        processed = 0
        failed = 0
        today = date.today()
        
        for i, cid in enumerate(customer_ids):
            try:
                # Get or calculate features
                features = feature_service.get_latest_features(cid)
                if not features or features.as_of_date < today:
                    features = feature_service.calculate_customer_features(cid, today)
                
                # Get feature vector
                feature_vector = features.to_feature_vector()
                
                # Predict
                churn_score, churn_label = ml_service.predict(feature_vector)
                
                # Get SHAP explanations
                top_reasons = explainer_service.get_top_reasons(feature_vector, top_n=5)
                
                # Store prediction
                prediction = ChurnPrediction(
                    customer_id=cid,
                    churn_score=churn_score,
                    churn_label=churn_label,
                    top_reasons=top_reasons,
                    model_version=ml_service.get_model_version(),
                    as_of_date=today
                )
                
                db.session.add(prediction)
                processed += 1
                
            except Exception as e:
                logger.warning(f"Failed to predict for {cid}: {e}")
                failed += 1
            
            # Update progress and commit periodically
            if (i + 1) % 10 == 0:
                db.session.commit()
                progress = int((i + 1) / total * 100)
                self.update_state(state="PROGRESS", meta={
                    "progress": progress,
                    "processed": processed,
                    "failed": failed
                })
        
        # Final commit
        db.session.commit()
        
        result = {
            "total": total,
            "processed": processed,
            "failed": failed
        }
        
        logger.info(f"Batch prediction complete: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Batch prediction failed: {e}")
        db.session.rollback()
        raise


@celery_app.task(bind=True, name="prediction.compute_shap_task")
def compute_shap_task(self, pred_id: str):
    """
    Compute SHAP values with nearest messages and cache results (Milestone 3)
    
    This computes:
    - SHAP values using TreeExplainer
    - Top reasons with formatted descriptions
    - Nearest messages using pgvector similarity
    
    Results are stored in shap_cache table for quick retrieval.
    
    Args:
        pred_id: Prediction UUID
        
    Returns:
        Dict with shap_top and nearest_messages
    """
    from app.services.ml_service import MLService
    from app.services.explainer_service import ExplainerService
    from app.services.feature_service import FeatureService
    from app.models.prediction import ChurnPrediction
    
    logger.info(f"Computing SHAP values for prediction {pred_id}")
    
    try:
        self.update_state(state="PROGRESS", meta={"step": "loading"})
        
        # Get prediction
        prediction = ChurnPrediction.query.get(pred_id)
        if not prediction:
            return {"error": "Prediction not found"}
        
        # Get features
        feature_service = FeatureService()
        features = feature_service.get_latest_features(str(prediction.customer_id))
        
        if not features:
            return {"error": "Features not found"}
        
        self.update_state(state="PROGRESS", meta={"step": "computing_shap"})
        
        # Get services
        ml_service = MLService()
        explainer_service = ExplainerService(ml_service)
        
        # Get feature vector
        feature_vector = features.to_feature_vector()
        
        # Compute and cache SHAP with nearest messages
        cache = explainer_service.compute_and_cache_shap(
            pred_id=pred_id,
            features=feature_vector,
            customer_id=str(prediction.customer_id),
            explainer_version=ml_service.get_model_version()
        )
        
        if not cache:
            return {"error": "Failed to compute and cache SHAP"}
        
        logger.info(f"SHAP computation complete for {pred_id}")
        
        return {
            "pred_id": pred_id,
            "shap_top": cache.shap_top,
            "nearest_messages": cache.nearest_messages,
            "computed_at": cache.computed_at.isoformat() if cache.computed_at else None
        }
        
    except Exception as e:
        logger.error(f"SHAP computation failed: {e}")
        raise


@celery_app.task(bind=True, name="prediction.calculate_shap_values")
def calculate_shap_values(self, pred_id: str):
    """
    Legacy SHAP calculation (kept for backward compatibility)
    
    Args:
        pred_id: Prediction UUID
        
    Returns:
        SHAP values and top reasons
    """
    # Delegate to new compute_shap_task
    return compute_shap_task(pred_id)
