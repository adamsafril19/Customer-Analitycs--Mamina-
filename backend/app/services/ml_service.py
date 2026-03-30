"""
ML Service - Model Loading and Inference

PENTING: Service ini HANYA untuk inference, BUKAN untuk training.
Model sudah ditraining terpisah dan disimpan sebagai artifact.

TRUTH-AWARE ARCHITECTURE:
- Model identity tracked via hash
- Feature schema validated before prediction
- All predictions traceable to specific model version
"""
import os
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import numpy as np
from flask import current_app

logger = logging.getLogger(__name__)


class MLService:
    """
    Machine Learning Service for churn prediction
    
    TRUTH-AWARE DESIGN:
    - Model identity is first-class (hash, version, registry)
    - Feature schema must match training schema
    - SHAP explainer bound to specific model
    - All predictions include provenance
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
        # REMOVED: self.vectorizer - model is numeric-only, no text vectorization
        self.feature_metadata = None
        self.shap_explainer = None
        
        # Model identity (CRITICAL for provenance)
        self.model_version = None
        self.model_hash = None
        self.feature_schema_hash = None
        self.shap_hash = None
        
        self._initialized = True
    
    def _compute_file_hash(self, filepath: str) -> str:
        """Compute SHA256 hash of file for identity"""
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    
    def _validate_against_registry(self) -> bool:
        """
        Validate loaded model against active registry entry.
        
        CRITICAL: Ensures loaded model matches what registry expects.
        FAIL-CLOSED: Raises error on mismatch (not just log).
        """
        try:
            from app.models.ml_registry import MLModelRegistry
            
            active = MLModelRegistry.get_active()
            if not active:
                logger.warning("No active ML model in registry - skipping validation")
                return True  # Allow for initial setup
            
            # Skip validation for initial placeholder
            if active.model_hash == "initial_v1":
                logger.info("Initial placeholder in registry - update after first training")
                return True
            
            # FAIL-CLOSED: Model hash mismatch = hard fail
            if self.model_hash != active.model_hash:
                raise RuntimeError(
                    f"CRITICAL: Model hash mismatch! "
                    f"Loaded={self.model_hash}, Registry={active.model_hash}. "
                    f"Update registry or load correct model."
                )
            
            # FAIL-CLOSED: Feature schema mismatch = hard fail
            if active.feature_schema_hash != "initial_schema" and self.feature_schema_hash != active.feature_schema_hash:
                raise RuntimeError(
                    f"CRITICAL: Feature schema hash mismatch! "
                    f"Loaded={self.feature_schema_hash}, Registry={active.feature_schema_hash}. "
                    f"Features may have drifted since training."
                )
            
            # FAIL-CLOSED: SHAP mismatch = hard fail
            if active.shap_explainer_hash and self.shap_hash and self.shap_hash != active.shap_explainer_hash:
                raise RuntimeError(
                    f"CRITICAL: SHAP explainer hash mismatch! "
                    f"Explanations would be for wrong model."
                )
            
            logger.info("Registry validation PASSED")
            
            # REGISTRY = SOURCE OF TRUTH for model version
            self.model_version = active.model_version
            
            return True
            
        except RuntimeError:
            raise  # Re-raise our own errors
        except Exception as e:
            logger.warning(f"Registry validation skipped: {e}")
            return True
    
    def load_all_models(self) -> None:
        """
        Load all ML artifacts from disk and validate against registry.
        
        Called once at application startup.
        Computes hashes and validates against MLModelRegistry.
        """
        try:
            self._load_model()
            # REMOVED: self._load_vectorizer() - model is numeric-only
            self._load_feature_metadata()
            self._load_shap_explainer()
            
            # Validate against registry
            self._validate_against_registry()
            
            logger.info(
                f"All ML models loaded - model_hash: {self.model_hash}, "
                f"feature_schema_hash: {self.feature_schema_hash}"
            )
            
        except Exception as e:
            logger.error(f"Failed to load ML models: {e}")
            raise
    
    def _load_model(self) -> None:
        """Load main prediction model with identity tracking"""
        import joblib
        
        model_path = current_app.config.get("MODEL_PATH", "models/churn_model.pkl")
        
        if not os.path.exists(model_path):
            logger.warning(f"Model file not found: {model_path}")
            return
        
        self.model = joblib.load(model_path)
        self.model_version = current_app.config.get("MODEL_VERSION", "v1.0.0")
        
        # Compute model hash for identity
        self.model_hash = self._compute_file_hash(model_path)
        
        logger.info(f"Loaded model from {model_path}, version: {self.model_version}, hash: {self.model_hash}")
    
    # REMOVED: _load_vectorizer() 
    # Model is numeric-only. Vectorizer was never used.
    # Text features are aggregated to numeric by FeatureService.
    
    def _load_feature_metadata(self) -> None:
        """
        Load feature metadata (names, types, order) with schema hash.
        
        FAIL-CLOSED: Raises error if metadata missing.
        Inference without explicit schema = ILLEGAL.
        """
        meta_path = current_app.config.get("FEATURE_META_PATH")
        
        if not meta_path or not os.path.exists(meta_path):
            raise RuntimeError(
                "CRITICAL: Feature metadata file missing or not configured. "
                "Inference must not run without explicit schema. "
                "Set FEATURE_META_PATH in config and ensure file exists."
            )
        
        with open(meta_path, 'r') as f:
            self.feature_metadata = json.load(f)
        
        # VALIDATE metadata has required fields
        if "expected_shape" not in self.feature_metadata:
            raise RuntimeError(
                "CRITICAL: Feature metadata missing 'expected_shape'. "
                "Cannot validate feature vector length."
            )
        if "feature_names" not in self.feature_metadata:
            raise RuntimeError(
                "CRITICAL: Feature metadata missing 'feature_names'. "
                "Cannot provide feature explanations."
            )
        
        logger.info(f"Loaded feature metadata from {meta_path}")
        
        # Compute feature schema hash from FULL metadata (not just names!)
        # This catches: order changes, type changes, scaling changes
        schema_str = json.dumps(self.feature_metadata, sort_keys=True)
        self.feature_schema_hash = hashlib.sha256(schema_str.encode()).hexdigest()[:16]
        logger.info(f"Feature schema hash: {self.feature_schema_hash}")
    
    def _load_shap_explainer(self) -> None:
        """Load SHAP explainer for interpretability with hash binding"""
        import joblib
        
        if not current_app.config.get("ENABLE_SHAP", True):
            logger.info("SHAP disabled in config")
            return
        
        shap_path = current_app.config.get("SHAP_EXPLAINER_PATH", "models/shap_explainer.pkl")
        
        if not os.path.exists(shap_path):
            logger.warning(f"SHAP explainer not found: {shap_path}")
            return
        
        self.shap_explainer = joblib.load(shap_path)
        self.shap_hash = self._compute_file_hash(shap_path)
        logger.info(f"Loaded SHAP explainer from {shap_path}, hash: {self.shap_hash}")
    
    def _expected_feature_count(self) -> int:
        """
        SINGLE SOURCE OF TRUTH for expected feature count.
        
        Returns:
            Expected number of features from metadata.
            
        Raises:
            RuntimeError: If metadata not loaded.
        """
        if not self.feature_metadata:
            raise RuntimeError("Feature metadata not loaded")
        return self.feature_metadata["expected_shape"]
    
    def is_model_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None
    
    def get_model_version(self) -> str:
        """Get current model version"""
        return self.model_version or "unknown"
    
    def get_model_hash(self) -> str:
        """Get model file hash for identity"""
        return self.model_hash
    
    def get_feature_schema_hash(self) -> str:
        """Get feature schema hash for validation"""
        return self.feature_schema_hash
    
    def get_model_identity(self) -> Dict[str, Any]:
        """Get full model identity for provenance tracking"""
        return {
            "model_version": self.model_version,
            "model_hash": self.model_hash,
            "feature_schema_hash": self.feature_schema_hash,
            "shap_hash": self.shap_hash,
            "expected_features": self.feature_metadata.get("expected_shape", 0) if self.feature_metadata else 0
        }
    
    def get_feature_names(self) -> List[str]:
        """Get ordered list of feature names"""
        if self.feature_metadata:
            return self.feature_metadata.get("feature_names", [])
        return []
    
    def predict_for_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        SINGLE TRUST BOUNDARY prediction.
        
        This method:
        1. Validates identity (verified feedback count > 0)
        2. Builds features internally via FeatureService (PURE)
        3. Validates schema hash cross-service
        4. Runs prediction with full provenance
        
        This is the ONLY method that should be exposed to external callers.
        
        Args:
            customer_id: Customer UUID
            
        Returns:
            Dict with prediction and full provenance
            
        Raises:
            PermissionError: If customer lacks verified identity
            RuntimeError: If model/registry/schema mismatch
        """
        from app.utils.errors import ModelNotLoadedError
        from app.services.feature_service import FeatureService
        
        if self.model is None:
            raise ModelNotLoadedError("Model is not loaded. Cannot make predictions.")
        
        # BUILD FEATURES via trusted service (PURE - no DB writes)
        feature_service = FeatureService()
        feature_data = feature_service.build_verified_features(customer_id)
        
        # CROSS-SERVICE SCHEMA VALIDATION
        # This catches schema drift between training and inference
        if feature_data["feature_schema_hash"] != self.feature_schema_hash:
            raise RuntimeError(
                f"Feature schema hash mismatch! "
                f"FeatureService={feature_data['feature_schema_hash']}, "
                f"MLService={self.feature_schema_hash}. "
                f"Model may have been trained on different features."
            )
        
        # VALIDATE feature count matches model expectation
        features = feature_data["features"]
        expected_shape = self._expected_feature_count()
        if len(features) != expected_shape:
            raise ValueError(
                f"Feature count mismatch: FeatureService returned {len(features)}, "
                f"model expects {expected_shape}"
            )
        
        # GET PREDICTION
        churn_score, churn_label = self._predict_raw(features)
        
        # RETURN with full provenance (all from trusted sources)
        # EPISTEMOLOGICAL FIX: Include features_used for Explainer to reference
        return {
            "customer_id": customer_id,
            "churn_score": churn_score,
            "churn_label": churn_label,
            "provenance": {
                "model_version": self.model_version,
                "model_hash": self.model_hash,
                "feature_schema_hash": self.feature_schema_hash,
                "feature_service_version": feature_data["feature_service_version"],
                "verified_feedback_count": feature_data["verified_feedback_count"],
                "as_of_date": feature_data["as_of_date"],
                "predicted_at": datetime.utcnow().isoformat(),
                # IMMUTABLE ARTIFACTS for Explainer
                "features_used": features,  # Snapshot at prediction time
                "feature_as_of": feature_data.get("as_of"),  # Exact timestamp
                "feature_names": self.get_feature_names()
            }
        }
    
    def predict_with_provenance(
        self, 
        customer_id: str,
        features: List[float]
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Use predict_for_customer() instead.
        
        This method is deprecated because it accepts external features,
        violating the single trust boundary principle.
        
        Raises:
            RuntimeError: Always - method is deprecated.
        """
        raise RuntimeError(
            "predict_with_provenance() is DEPRECATED. "
            "Use predict_for_customer(customer_id) instead. "
            "External feature injection violates trust boundary."
        )
    
    def _predict_with_features_internal(
        self, 
        customer_id: str,
        features: List[float],
        verified_count: int
    ) -> Dict[str, Any]:
        """
        INTERNAL ONLY: Predict with pre-validated features.
        
        NOT FOR EXTERNAL USE. Called only by predict_for_customer.
        
        Args:
            customer_id: Customer identifier
            features: Pre-validated feature vector from FeatureService
            verified_count: Pre-validated count of verified feedback
            
        Returns:
            Dict with prediction and provenance
        """
        # No external validation needed - caller already validated
        expected_shape = self._expected_feature_count()
        if len(features) != expected_shape:
            raise ValueError(
                f"Feature schema mismatch: got {len(features)} features, "
                f"model expects {expected_shape}"
            )
        
        churn_score, churn_label = self._predict_raw(features)
        
        return {
            "customer_id": customer_id,
            "churn_score": churn_score,
            "churn_label": churn_label,
            "provenance": {
                "model_version": self.model_version,
                "model_hash": self.model_hash,
                "feature_schema_hash": self.feature_schema_hash,
                "verified_feedback_count": verified_count,
                "predicted_at": datetime.utcnow().isoformat()
            }
        }
    
    def _predict_raw(self, features: List[float]) -> Tuple[float, str]:
        """
        Internal prediction method - RAW, NO PROVENANCE.
        
        Use predict_with_provenance() for auditable predictions.
        This method is private (_) to discourage direct use.
        
        Args:
            features: List of feature values (in correct order!)
            
        Returns:
            Tuple of (churn_score, churn_label)
        """
        from app.utils.errors import ModelNotLoadedError
        
        if self.model is None:
            raise ModelNotLoadedError("Model is not loaded. Cannot make predictions.")
        
        # Ensure features is numpy array with correct shape
        features_array = np.array(features).reshape(1, -1)
        
        # Validate feature count using SINGLE SOURCE OF TRUTH
        expected_shape = self._expected_feature_count()
        if features_array.shape[1] != expected_shape:
            raise ValueError(
                f"Feature shape mismatch: expected {expected_shape}, got {features_array.shape[1]}"
            )
        
        # Get probability
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(features_array)[0]
            churn_score = float(proba[1]) if len(proba) > 1 else float(proba[0])
        else:
            churn_score = float(self.model.predict(features_array)[0])
        
        churn_label = self._score_to_label(churn_score)
        
        return churn_score, churn_label
    
    # Deprecated alias for backwards compatibility
    predict = _predict_raw
    
    def predict_batch_with_provenance(
        self, 
        customer_features: List[Tuple[str, List[float]]]
    ) -> List[Dict[str, Any]]:
        """
        Batch prediction with provenance (SYSTEM-ENFORCED).
        
        Args:
            customer_features: List of (customer_id, features) tuples
            
        Returns:
            List of prediction results with provenance
        """
        results = []
        for customer_id, features in customer_features:
            try:
                result = self.predict_with_provenance(customer_id, features)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed prediction for {customer_id}: {e}")
                results.append({
                    "customer_id": customer_id,
                    "error": str(e)
                })
        return results
    
    
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
        Reload all models from disk with full revalidation.
        
        Called for hot reloading. Revalidates against registry.
        
        Args:
            model_path: Optional new model path
            
        Returns:
            True if successful
        """
        if model_path:
            current_app.config["MODEL_PATH"] = model_path
        
        try:
            # FULL RELOAD with registry revalidation
            self.load_all_models()
            logger.info("Model reloaded successfully with registry validation")
            return True
        except Exception as e:
            logger.error(f"Failed to reload model: {e}")
            return False
