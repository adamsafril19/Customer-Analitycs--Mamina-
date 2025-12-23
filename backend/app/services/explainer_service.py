"""
SHAP Explainer Service

Provides interpretability for ML predictions using SHAP values.
Heavy calculations should be run as background jobs.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from flask import current_app

logger = logging.getLogger(__name__)


class ExplainerService:
    """
    SHAP Explainability Service
    
    Responsibilities:
    - Calculate SHAP values for predictions
    - Extract top contributing features
    - Provide human-readable explanations
    
    Note: Heavy SHAP calculations should be done in background jobs.
    """
    
    def __init__(self, ml_service=None):
        """
        Initialize explainer service
        
        Args:
            ml_service: MLService instance (optional, will use singleton)
        """
        self.ml_service = ml_service
    
    def _get_ml_service(self):
        """Get ML service instance"""
        if self.ml_service is None:
            from app.services.ml_service import MLService
            self.ml_service = MLService()
        return self.ml_service
    
    def calculate_shap_values(self, features: List[float]) -> Optional[np.ndarray]:
        """
        Calculate SHAP values for a single prediction
        
        Args:
            features: Feature values
            
        Returns:
            SHAP values array or None if SHAP is not available
        """
        ml_service = self._get_ml_service()
        
        if ml_service.shap_explainer is None:
            logger.warning("SHAP explainer not loaded, cannot calculate SHAP values")
            return None
        
        try:
            features_array = np.array(features).reshape(1, -1)
            shap_values = ml_service.shap_explainer.shap_values(features_array)
            
            # Handle different SHAP output formats
            if isinstance(shap_values, list):
                # For tree-based models, use positive class
                shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]
            
            return shap_values[0]  # Return first (only) sample
            
        except Exception as e:
            logger.error(f"Error calculating SHAP values: {e}")
            return None
    
    def get_top_reasons(
        self, 
        features: List[float], 
        shap_values: Optional[np.ndarray] = None,
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get top contributing features with explanations
        
        Args:
            features: Feature values
            shap_values: Precomputed SHAP values (optional)
            top_n: Number of top features to return
            
        Returns:
            List of dicts with feature, impact, value, description
        """
        ml_service = self._get_ml_service()
        
        # Calculate SHAP if not provided
        if shap_values is None:
            shap_values = self.calculate_shap_values(features)
        
        # If SHAP still not available, use fallback
        if shap_values is None:
            return self._get_fallback_reasons(features, top_n)
        
        # Get feature names and descriptions
        feature_names = ml_service.get_feature_names()
        feature_descriptions = ml_service.feature_metadata.get("feature_descriptions", {})
        
        # Create list of (index, shap_value, feature_value)
        feature_impacts = []
        for i, (shap_val, feat_val) in enumerate(zip(shap_values, features)):
            if i < len(feature_names):
                feature_impacts.append({
                    "feature": feature_names[i],
                    "shap_value": float(shap_val),
                    "feature_value": float(feat_val)
                })
        
        # Sort by absolute SHAP value
        feature_impacts.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        
        # Take top N and format
        top_reasons = []
        for item in feature_impacts[:top_n]:
            feature_name = item["feature"]
            shap_value = item["shap_value"]
            feature_value = item["feature_value"]
            
            # Get description
            base_description = feature_descriptions.get(
                feature_name, 
                self._get_default_description(feature_name)
            )
            
            # Add directional context
            description = self._format_description(
                feature_name, 
                shap_value, 
                feature_value,
                base_description
            )
            
            top_reasons.append({
                "feature": feature_name,
                "impact": round(shap_value, 4),
                "value": round(feature_value, 4),
                "description": description
            })
        
        return top_reasons
    
    def _get_fallback_reasons(
        self, 
        features: List[float], 
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fallback when SHAP is not available
        Uses feature values and domain knowledge to estimate importance
        """
        ml_service = self._get_ml_service()
        feature_names = ml_service.get_feature_names()
        feature_descriptions = ml_service.feature_metadata.get("feature_descriptions", {})
        
        # Define which features indicate higher churn risk
        # Positive impact = increases churn probability
        risk_indicators = {
            "r_score": lambda x: -x,  # Lower recency = higher risk
            "f_score": lambda x: -x,  # Lower frequency = higher risk
            "m_score": lambda x: -x,  # Lower monetary = higher risk
            "tenure_days": lambda x: -x,  # Shorter tenure = higher risk
            "avg_sentiment_30": lambda x: -x,  # Negative sentiment = higher risk
            "neg_msg_count_30": lambda x: x,  # More negative messages = higher risk
            "avg_response_secs": lambda x: x,  # Slower response = higher risk
            "intensity_7d": lambda x: -x,  # Less engagement = higher risk
        }
        
        impacts = []
        for i, (name, value) in enumerate(zip(feature_names, features)):
            if name in risk_indicators:
                impact = risk_indicators[name](value) / 10  # Normalize
            else:
                impact = 0
            
            impacts.append({
                "feature": name,
                "impact": round(impact, 4),
                "value": round(value, 4) if isinstance(value, (int, float)) else value,
                "description": feature_descriptions.get(name, self._get_default_description(name))
            })
        
        # Sort by absolute impact
        impacts.sort(key=lambda x: abs(x["impact"]), reverse=True)
        
        return impacts[:top_n]
    
    def _get_default_description(self, feature_name: str) -> str:
        """Get default description for feature"""
        descriptions = {
            "r_score": "Recency - waktu sejak transaksi terakhir",
            "f_score": "Frequency - frekuensi transaksi",
            "m_score": "Monetary - total nilai transaksi",
            "tenure_days": "Lama menjadi customer",
            "avg_sentiment_30": "Rata-rata sentimen 30 hari terakhir",
            "neg_msg_count_30": "Jumlah pesan negatif 30 hari terakhir",
            "avg_response_secs": "Rata-rata waktu respons admin",
            "intensity_7d": "Intensitas komunikasi 7 hari terakhir"
        }
        return descriptions.get(feature_name, feature_name)
    
    def _format_description(
        self, 
        feature_name: str, 
        shap_value: float, 
        feature_value: float,
        base_description: str
    ) -> str:
        """
        Format description with directional context
        
        Args:
            feature_name: Name of feature
            shap_value: SHAP value (positive = increases churn)
            feature_value: Actual feature value
            base_description: Base description
            
        Returns:
            Formatted description
        """
        # Determine direction
        direction = "meningkatkan" if shap_value > 0 else "menurunkan"
        
        # Feature-specific formatting
        if feature_name == "avg_sentiment_30":
            if feature_value < -0.2:
                return f"Sentimen sangat negatif ({direction} risiko churn)"
            elif feature_value < 0:
                return f"Sentimen cenderung negatif ({direction} risiko churn)"
            else:
                return f"Sentimen positif ({direction} risiko churn)"
        
        elif feature_name == "f_score":
            if shap_value > 0:
                return f"Frekuensi kunjungan menurun ({direction} risiko churn)"
            else:
                return f"Frekuensi kunjungan stabil ({direction} risiko churn)"
        
        elif feature_name == "r_score":
            if shap_value > 0:
                return f"Sudah lama tidak berkunjung ({direction} risiko churn)"
            else:
                return f"Baru saja berkunjung ({direction} risiko churn)"
        
        elif feature_name == "avg_response_secs":
            if shap_value > 0:
                return f"Waktu respons admin lambat ({direction} risiko churn)"
            else:
                return f"Waktu respons admin cepat ({direction} risiko churn)"
        
        elif feature_name == "neg_msg_count_30":
            if shap_value > 0:
                return f"Banyak komplain ({direction} risiko churn)"
            else:
                return f"Sedikit komplain ({direction} risiko churn)"
        
        return f"{base_description} ({direction} risiko churn)"
