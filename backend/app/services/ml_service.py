"""
ML Service - Model Loading and Inference

PENTING: Service ini HANYA untuk inference, BUKAN untuk training.
Model sudah ditraining terpisah dan disimpan sebagai artifact.

Arsitektur:
- Model di-load sekali saat startup (singleton)
- Inference harus cepat (<500ms per customer)
- SHAP explainability untuk interpretasi
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from flask import current_app

logger = logging.getLogger(__name__)


class MLService:
    """
    Machine Learning Service for churn prediction
    
    Responsibilities:
    - Load pretrained models from disk
    - Perform inference on customer features
    - Provide model metadata
    
    Model artifacts:
    - churn_model.pkl: Main XGBoost/sklearn model
    - vectorizer.pkl: Text vectorizer (if applicable)
    - features.json: Feature metadata
    - shap_explainer.pkl: SHAP explainer (optional)
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern - ensure only one instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.model = None
        self.vectorizer = None
        self.feature_metadata = None
        self.shap_explainer = None
        self.model_version = None
        self._initialized = True
    
    def load_all_models(self) -> None:
        """
        Load all ML artifacts from disk
        
        Called once at application startup.
        """
        try:
            self._load_model()
            self._load_vectorizer()
            self._load_feature_metadata()
            self._load_shap_explainer()
            
            logger.info("All ML models loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load ML models: {e}")
            raise
    
    def _load_model(self) -> None:
        """Load main prediction model"""
        import joblib
        
        model_path = current_app.config.get("MODEL_PATH", "models/churn_model.pkl")
        
        if not os.path.exists(model_path):
            logger.warning(f"Model file not found: {model_path}")
            return
        
        self.model = joblib.load(model_path)
        self.model_version = current_app.config.get("MODEL_VERSION", "v1.0.0")
        
        logger.info(f"Loaded model from {model_path}, version: {self.model_version}")
    
    def _load_vectorizer(self) -> None:
        """Load text vectorizer (for NLP features)"""
        import joblib
        
        vectorizer_path = current_app.config.get("VECTORIZER_PATH", "models/vectorizer.pkl")
        
        if not os.path.exists(vectorizer_path):
            logger.warning(f"Vectorizer file not found: {vectorizer_path}")
            return
        
        self.vectorizer = joblib.load(vectorizer_path)
        logger.info(f"Loaded vectorizer from {vectorizer_path}")
    
    def _load_feature_metadata(self) -> None:
        """Load feature metadata (names, types, order)"""
        meta_path = current_app.config.get("FEATURE_META_PATH", "models/features.json")
        
        if not os.path.exists(meta_path):
            logger.warning(f"Feature metadata not found: {meta_path}")
            # Use default feature metadata
            self.feature_metadata = self._get_default_feature_metadata()
            return
        
        with open(meta_path, 'r') as f:
            self.feature_metadata = json.load(f)
        
        logger.info(f"Loaded feature metadata from {meta_path}")
    
    def _load_shap_explainer(self) -> None:
        """Load SHAP explainer for interpretability"""
        import joblib
        
        if not current_app.config.get("ENABLE_SHAP", True):
            logger.info("SHAP disabled in config")
            return
        
        shap_path = current_app.config.get("SHAP_EXPLAINER_PATH", "models/shap_explainer.pkl")
        
        if not os.path.exists(shap_path):
            logger.warning(f"SHAP explainer not found: {shap_path}")
            return
        
        self.shap_explainer = joblib.load(shap_path)
        logger.info(f"Loaded SHAP explainer from {shap_path}")
    
    def _get_default_feature_metadata(self) -> Dict[str, Any]:
        """Get default feature metadata if file not found"""
        return {
            "feature_names": [
                "r_score",
                "f_score", 
                "m_score",
                "tenure_days",
                "avg_sentiment_30",
                "neg_msg_count_30",
                "avg_response_secs",
                "intensity_7d"
            ],
            "feature_types": {
                "r_score": "numeric",
                "f_score": "numeric",
                "m_score": "numeric",
                "tenure_days": "numeric",
                "avg_sentiment_30": "numeric",
                "neg_msg_count_30": "numeric",
                "avg_response_secs": "numeric",
                "intensity_7d": "numeric"
            },
            "feature_descriptions": {
                "r_score": "Recency - seberapa baru customer bertransaksi",
                "f_score": "Frequency - seberapa sering customer bertransaksi",
                "m_score": "Monetary - total nilai transaksi customer",
                "tenure_days": "Lama menjadi customer (hari)",
                "avg_sentiment_30": "Rata-rata sentimen 30 hari terakhir",
                "neg_msg_count_30": "Jumlah pesan negatif 30 hari terakhir",
                "avg_response_secs": "Rata-rata waktu respons (detik)",
                "intensity_7d": "Jumlah pesan 7 hari terakhir"
            },
            "expected_shape": 8
        }
    
    def is_model_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None
    
    def get_model_version(self) -> str:
        """Get current model version"""
        return self.model_version or "unknown"
    
    def get_feature_names(self) -> List[str]:
        """Get ordered list of feature names"""
        if self.feature_metadata:
            return self.feature_metadata.get("feature_names", [])
        return []
    
    def predict(self, features: List[float]) -> Tuple[float, str]:
        """
        Predict churn probability for single customer
        
        Args:
            features: List of feature values (in correct order!)
            
        Returns:
            Tuple of (churn_score, churn_label)
            
        Raises:
            ModelNotLoadedError: If model is not loaded
        """
        from app.utils.errors import ModelNotLoadedError
        
        if self.model is None:
            raise ModelNotLoadedError("Model is not loaded. Cannot make predictions.")
        
        # Ensure features is numpy array with correct shape
        features_array = np.array(features).reshape(1, -1)
        
        # Validate feature count
        expected_shape = self.feature_metadata.get("expected_shape", 8)
        if features_array.shape[1] != expected_shape:
            logger.warning(
                f"Feature shape mismatch: expected {expected_shape}, got {features_array.shape[1]}"
            )
        
        # Get probability
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(features_array)[0]
            # Assume binary classification: [prob_no_churn, prob_churn]
            churn_score = float(proba[1]) if len(proba) > 1 else float(proba[0])
        else:
            # Fallback for models without predict_proba
            churn_score = float(self.model.predict(features_array)[0])
        
        # Convert to label
        churn_label = self._score_to_label(churn_score)
        
        return churn_score, churn_label
    
    def predict_batch(self, features_list: List[List[float]]) -> List[Tuple[float, str]]:
        """
        Predict churn for multiple customers
        
        Args:
            features_list: List of feature lists
            
        Returns:
            List of (churn_score, churn_label) tuples
        """
        from app.utils.errors import ModelNotLoadedError
        
        if self.model is None:
            raise ModelNotLoadedError("Model is not loaded. Cannot make predictions.")
        
        features_array = np.array(features_list)
        
        if hasattr(self.model, "predict_proba"):
            probas = self.model.predict_proba(features_array)
            scores = [float(p[1]) if len(p) > 1 else float(p[0]) for p in probas]
        else:
            scores = [float(p) for p in self.model.predict(features_array)]
        
        return [(score, self._score_to_label(score)) for score in scores]
    
    def _score_to_label(self, score: float) -> str:
        """Convert churn score to label"""
        if score < 0.3:
            return "low"
        elif score < 0.7:
            return "medium"
        else:
            return "high"
    
    def reload_model(self, model_path: Optional[str] = None) -> bool:
        """
        Reload model from disk (for hot reloading)
        
        Args:
            model_path: Optional new model path
            
        Returns:
            True if successful
        """
        import joblib
        
        if model_path:
            # Update config temporarily
            current_app.config["MODEL_PATH"] = model_path
        
        try:
            self._load_model()
            self._load_shap_explainer()
            logger.info("Model reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload model: {e}")
            return False
