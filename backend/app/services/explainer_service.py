"""
SHAP Explainer Service

UPDATED (Milestone 3): Added nearest-message drilldown and shap_cache storage
- Calculate SHAP values for predictions
- Find nearest messages using pgvector similarity
- Cache results in shap_cache table
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.exc import IntegrityError

import numpy as np
from sqlalchemy import text

from app import db
from app.models.topic import ShapCache
from app.models.feedback import FeedbackFeatures

logger = logging.getLogger(__name__)


class ExplainerService:
    """
    SHAP Explainability Service with Nearest-Message Drilldown
    
    Responsibilities:
    - Calculate SHAP values for predictions
    - Extract top contributing features
    - Find nearest messages using embedding similarity
    - Cache results in shap_cache table
    
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
        
        SCHEMA BOUND: Validates feature count matches model expectation.
        
        Args:
            features: Feature values (must match model schema)
            
        Returns:
            SHAP values array or None if SHAP is not available
            
        Raises:
            ValueError: If feature length doesn't match model schema
        """
        ml_service = self._get_ml_service()
        
        if ml_service.shap_explainer is None:
            logger.warning("SHAP explainer not loaded, cannot calculate SHAP values")
            return None
        
        # SCHEMA GUARD: Validate feature count matches model
        expected_count = ml_service.feature_metadata.get("expected_shape", 13)
        if len(features) != expected_count:
            raise ValueError(
                f"Feature count mismatch: got {len(features)}, "
                f"model expects {expected_count}. "
                f"Schema hash: {ml_service.feature_schema_hash}"
            )
        
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
        
        # ORDER VALIDATION: Ensure all arrays match length
        if not (len(feature_names) == len(features) == len(shap_values)):
            logger.error(
                f"Length mismatch: names={len(feature_names)}, "
                f"features={len(features)}, shap={len(shap_values)}"
            )
            return self._get_fallback_reasons(features, top_n)
        
        # Create list of (index, shap_value, feature_value)
        feature_impacts = []
        for i, (shap_val, feat_val) in enumerate(zip(shap_values, features)):
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
    
    def get_nearest_messages(
        self,
        customer_id: str,
        query_embedding: Optional[List[float]] = None,
        top_n: int = 5,
        as_of: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Find nearest messages using pgvector similarity (Milestone 3)
        
        TEMPORAL SAFE: Only considers messages that existed at as_of time.
        TRUST AWARE: Only considers verified/probable feedback.
        
        Args:
            customer_id: Customer UUID
            query_embedding: Query embedding (if None, uses last message embedding)
            top_n: Number of messages to return
            as_of: Temporal anchor (defaults to now)
            
        Returns:
            List of nearest messages with text snippets
        """
        try:
            # Temporal anchor
            if as_of is None:
                as_of = datetime.utcnow()
            
            # If no query embedding, get customer's last message embedding
            if query_embedding is None:
                from app.models.feedback import FeedbackLinked
                
                last_msg = db.session.query(FeedbackFeatures).join(
                    FeedbackLinked, FeedbackFeatures.link_id == FeedbackLinked.link_id
                ).filter(
                    FeedbackLinked.customer_id == customer_id,
                    FeedbackLinked.link_status.in_(['verified', 'probable']),
                    FeedbackFeatures.embedding.isnot(None),
                    FeedbackFeatures.processed_at <= as_of
                ).order_by(FeedbackFeatures.processed_at.desc()).first()
                
                if not last_msg or last_msg.embedding is None:
                    logger.warning(f"No embedding found for customer {customer_id}")
                    return []
                
                query_embedding = list(last_msg.embedding)
            
            # Use pgvector cosine distance operator
            # Note: <-> is L2, <=> is cosine distance (0-2), <#> is inner product
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            # FIXED: Add link_status filter, temporal anchor, and link_id for provenance
            sql = text("""
                SELECT 
                    ff.feature_id,
                    ff.link_id,
                    ff.msg_id,
                    fr.text,
                    fr.timestamp,
                    ff.sentiment_label,
                    ff.topic_id,
                    fl.link_status,
                    ff.embedding <=> :query_embedding::vector AS distance
                FROM feedback_features ff
                JOIN feedback_raw fr ON ff.msg_id = fr.msg_id
                JOIN feedback_linked fl ON ff.link_id = fl.link_id
                WHERE fl.customer_id = :customer_id
                  AND fl.link_status IN ('verified', 'probable')
                  AND ff.embedding IS NOT NULL
                  AND ff.processed_at <= :as_of
                ORDER BY ff.embedding <=> :query_embedding::vector
                LIMIT :limit
            """)
            
            result = db.session.execute(sql, {
                "customer_id": customer_id,
                "query_embedding": embedding_str,
                "as_of": as_of,
                "limit": top_n
            })
            
            messages = []
            for row in result:
                # Truncate text for privacy
                text_snippet = row.text[:200] + "..." if len(row.text) > 200 else row.text
                
                # FIXED: Correct similarity formula
                # Cosine distance ∈ [0, 2], convert to similarity ∈ [0, 1]
                similarity = max(0.0, 1 - (row.distance / 2))
                
                # EPISTEMOLOGICAL FIX: Include IDs for provenance/audit
                messages.append({
                    # PROOF OF PROVENANCE - these IDs allow audit
                    "feedback_id": str(row.feature_id),  # Original feature_id
                    "link_id": str(row.link_id),  # Link for traceability
                    "msg_id": str(row.msg_id),
                    # Content
                    "text_snippet": text_snippet,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "sentiment_label": row.sentiment_label,
                    "topic_id": str(row.topic_id) if row.topic_id else None,
                    "link_status": row.link_status,
                    "similarity_score": round(similarity, 4),
                    # SEMANTIC DRIFT WARNING
                    "interpretation": "semantic_similarity_not_causal"
                })
            
            return messages
            
        except Exception as e:
            logger.error(f"Error finding nearest messages: {e}")
            return []
    
    def compute_and_cache_shap(
        self,
        pred_id: str,
        features: List[float],
        customer_id: str,
        as_of: Optional[datetime] = None,
        explainer_version: Optional[str] = None
    ) -> Optional[ShapCache]:
        """
        Compute SHAP values and cache results (for Celery task)
        
        TEMPORAL SAFE: Uses as_of for nearest message lookup.
        SCHEMA BOUND: Stores feature_schema_hash for validation.
        
        Args:
            pred_id: Prediction UUID
            features: Feature values
            customer_id: Customer UUID
            as_of: Temporal anchor (should match prediction time)
            explainer_version: Version string
            
        Returns:
            ShapCache object or None
        """
        try:
            if as_of is None:
                as_of = datetime.utcnow()
            
            ml_service = self._get_ml_service()
            
            # Calculate SHAP
            shap_values = self.calculate_shap_values(features)
            
            # Determine explanation type
            if shap_values is not None:
                top_reasons = self.get_top_reasons(features, shap_values)
                explanation_type = "shap"
            else:
                top_reasons = self._get_fallback_reasons(features, 5)
                explanation_type = "heuristic"
            
            # Get nearest messages with temporal anchor
            nearest_messages = self.get_nearest_messages(customer_id, as_of=as_of)
            
            # RACE CONDITION SAFE: Use upsert pattern
            try:
                existing = ShapCache.query.filter_by(pred_id=pred_id).first()
                
                if existing:
                    cache = existing
                else:
                    cache = ShapCache(pred_id=pred_id)
                    db.session.add(cache)
                
                cache.shap_top = top_reasons
                # NOTE: nearest_messages = semantic similarity, NOT causal attribution
                cache.nearest_messages = nearest_messages
                cache.computed_at = datetime.utcnow()
                cache.explainer_version = explainer_version or "unknown"
                
                # SCHEMA BINDING for reproducibility validation
                cache.feature_schema_hash = ml_service.feature_schema_hash
                cache.model_version = ml_service.model_version
                cache.explanation_type = explanation_type
                cache.as_of = as_of
                
                db.session.commit()
                
                logger.info(f"Cached {explanation_type} explanation for prediction {pred_id}")
                return cache
                
            except IntegrityError:
                # Race condition: another worker inserted first
                db.session.rollback()
                logger.warning(f"SHAP cache race condition for {pred_id}, fetching existing")
                return ShapCache.query.filter_by(pred_id=pred_id).first()
            
        except Exception as e:
            logger.error(f"Error caching SHAP: {e}")
            db.session.rollback()
            return None
    
    def get_cached_shap(self, pred_id: str) -> Optional[Dict[str, Any]]:
        """Get cached SHAP results if available"""
        cache = ShapCache.query.filter_by(pred_id=pred_id).first()
        if cache:
            return cache.to_dict()
        return None
    
    def _get_fallback_reasons(
        self, 
        features: List[float], 
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fallback when SHAP is not available
        Uses feature values and domain knowledge to estimate importance
        
        NOTE: explanation_type will be 'heuristic' not 'shap'
        """
        ml_service = self._get_ml_service()
        feature_names = ml_service.get_feature_names()
        feature_descriptions = ml_service.feature_metadata.get("feature_descriptions", {})
        
        # Risk indicators aligned with FEATURE_SCHEMA
        # Names MUST match FeatureService.FEATURE_SCHEMA exactly
        # v2 FEATURE_SCHEMA aligned risk indicators
        risk_indicators = {
            "recency_ratio": lambda x: (x - 1) * 2,  # >1 = overdue vs personal baseline
            "frequency_trend": lambda x: -(1 - min(x, 2)),  # <1 = declining frequency
            "spend_trend": lambda x: -(1 - min(x, 2)),  # <1 = declining spend
            "msg_trend": lambda x: -(1 - min(x, 2)),  # <1 = declining communication
            "sentiment_trend": lambda x: -x * 3,  # Negative delta = worsening sentiment
            "recency_days": lambda x: x / 30,  # Higher recency = higher risk
            "tx_count_90d": lambda x: -x / 3,  # Lower tx count = higher risk
            "spend_90d": lambda x: -x / 300000,  # Lower spend = higher risk
            "avg_tx_value": lambda x: -x / 50000,  # Lower avg = higher risk
            "tenure_days": lambda x: -x / 365,  # Shorter tenure = higher risk
            "avg_sentiment_score": lambda x: -x * 2,  # Negative sentiment = higher risk
            "complaint_ratio": lambda x: x * 5,  # More complaints = higher risk
            "msg_volatility": lambda x: x,  # Higher volatility = higher risk
            "response_delay_mean": lambda x: x / 3600,  # Slower response = higher risk
        }
        
        impacts = []
        for i, (name, value) in enumerate(zip(feature_names, features)):
            value = float(value) if isinstance(value, (int, float)) else 0
            if name in risk_indicators:
                impact = risk_indicators[name](value)
            else:
                impact = 0
            
            impacts.append({
                "feature": name,
                "impact": round(impact, 4),
                "value": round(value, 4),
                "description": feature_descriptions.get(name, self._get_default_description(name))
            })
        
        # Sort by absolute impact
        impacts.sort(key=lambda x: abs(x["impact"]), reverse=True)
        
        return impacts[:top_n]
    
    def _get_default_description(self, feature_name: str) -> str:
        """
        Get default description for feature
        Names MUST match FeatureService.FEATURE_SCHEMA v2 exactly
        """
        descriptions = {
            "recency_ratio": "Rasio recency terhadap baseline personal",
            "frequency_trend": "Tren frekuensi transaksi (30d vs prior)",
            "spend_trend": "Tren belanja (30d vs prior)",
            "msg_trend": "Tren komunikasi (30d vs prior)",
            "sentiment_trend": "Perubahan sentimen (30d vs prior)",
            "recency_days": "Hari sejak transaksi terakhir",
            "tx_count_90d": "Jumlah transaksi 90 hari terakhir",
            "spend_90d": "Total belanja 90 hari terakhir",
            "avg_tx_value": "Rata-rata nilai transaksi",
            "tenure_days": "Lama menjadi customer",
            "avg_sentiment_score": "Rata-rata skor sentimen 30 hari",
            "complaint_ratio": "Rasio pesan komplain 30 hari",
            "msg_volatility": "Volatilitas pola pesan",
            "response_delay_mean": "Rata-rata waktu respons admin",
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
        Names MUST match FeatureService.FEATURE_SCHEMA v2 exactly
        """
        direction = "meningkatkan" if shap_value > 0 else "menurunkan"
        risk_word = "risiko"
        
        # === DEVIATION FEATURES ===
        if feature_name == "recency_ratio":
            if feature_value > 2:
                return f"Sudah 2x lebih lama dari biasanya tidak bertransaksi ({direction} {risk_word})"
            elif feature_value > 1:
                return f"Lebih lama dari biasanya tidak bertransaksi ({direction} {risk_word})"
            else:
                return f"Masih dalam pola normal ({direction} {risk_word})"
        
        elif feature_name == "frequency_trend":
            if feature_value < 0.5:
                return f"Frekuensi transaksi turun drastis ({direction} {risk_word})"
            elif feature_value < 1:
                return f"Frekuensi transaksi menurun ({direction} {risk_word})"
            else:
                return f"Frekuensi transaksi stabil/naik ({direction} {risk_word})"
        
        elif feature_name == "spend_trend":
            if feature_value < 0.5:
                return f"Belanja turun drastis ({direction} {risk_word})"
            elif feature_value < 1:
                return f"Belanja menurun ({direction} {risk_word})"
            else:
                return f"Belanja stabil/naik ({direction} {risk_word})"
        
        elif feature_name == "msg_trend":
            if feature_value < 0.5:
                return f"Komunikasi turun drastis ({direction} {risk_word})"
            elif feature_value < 1:
                return f"Komunikasi menurun ({direction} {risk_word})"
            else:
                return f"Komunikasi stabil/naik ({direction} {risk_word})"
        
        elif feature_name == "sentiment_trend":
            if feature_value < -0.2:
                return f"Sentimen memburuk signifikan ({direction} {risk_word})"
            elif feature_value < 0:
                return f"Sentimen sedikit menurun ({direction} {risk_word})"
            else:
                return f"Sentimen stabil/membaik ({direction} {risk_word})"
        
        # === ABSOLUTE FEATURES ===
        elif feature_name == "recency_days":
            if shap_value > 0:
                return f"Sudah lama tidak bertransaksi ({direction} {risk_word})"
            else:
                return f"Baru saja bertransaksi ({direction} {risk_word})"
        
        elif feature_name == "tenure_days":
            if shap_value > 0:
                return f"Customer baru (tenure pendek) ({direction} {risk_word})"
            else:
                return f"Customer loyal (tenure panjang) ({direction} {risk_word})"
        
        # === NLP FEATURES ===
        elif feature_name == "avg_sentiment_score":
            if feature_value < -0.2:
                return f"Sentimen negatif ({direction} {risk_word})"
            elif feature_value > 0.2:
                return f"Sentimen positif ({direction} {risk_word})"
            else:
                return f"Sentimen netral ({direction} {risk_word})"
        
        elif feature_name == "complaint_ratio":
            if feature_value > 0.3:
                return f"Tingkat komplain tinggi ({direction} {risk_word})"
            elif feature_value > 0.1:
                return f"Beberapa komplain ({direction} {risk_word})"
            else:
                return f"Sedikit/tanpa komplain ({direction} {risk_word})"
        
        elif feature_name == "response_delay_mean":
            if shap_value > 0:
                return f"Waktu respons admin lambat ({direction} {risk_word})"
            else:
                return f"Waktu respons admin cepat ({direction} {risk_word})"
        
        return f"{base_description} ({direction} {risk_word})"
