"""
Topic, ModelVersion, ShapCache Models

REVISED: ShapCache now only stores numerical SHAP values, no storytelling
"""
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app import db


class Topic(db.Model):
    """
    Topic cluster dictionary from BERTopic/HDBSCAN
    
    This provides STABLE topic identity across model retraining.
    
    topic_id = UUID (stable, never changes)
    topic_idx = BERTopic internal index (changes on retrain)
    model_version = Which model version this mapping belongs to
    
    On retrain: create new Topic records with same semantic meaning
    but different topic_idx.
    """
    __tablename__ = "topics"
    
    topic_id = db.Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        server_default=db.text('gen_random_uuid()')
    )
    topic_idx = db.Column(db.Integer, nullable=True, index=True)  # BERTopic internal index
    name = db.Column(db.Text, nullable=True)
    top_keywords = db.Column(ARRAY(db.Text), nullable=True)
    model_version = db.Column(db.String(50), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, server_default=db.func.now())
    
    # Unique constraint: one topic_idx per model_version
    __table_args__ = (
        db.UniqueConstraint("topic_idx", "model_version", name="uq_topic_idx_version"),
    )
    
    def to_dict(self) -> dict:
        return {
            "topic_id": str(self.topic_id),
            "topic_idx": self.topic_idx,
            "name": self.name,
            "top_keywords": self.top_keywords,
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self) -> str:
        return f"<Topic {self.name} (idx={self.topic_idx})>"


class ModelVersion(db.Model):
    """Tracks ML model versions for reproducibility"""
    __tablename__ = "model_versions"
    
    model_version = db.Column(db.String(50), primary_key=True)
    model_path = db.Column(db.Text, nullable=True)
    trained_at = db.Column(db.DateTime, nullable=True)
    metrics = db.Column(db.JSON, nullable=True)
    deployed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, server_default=db.func.now())
    
    def to_dict(self) -> dict:
        return {
            "model_version": self.model_version,
            "model_path": self.model_path,
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "metrics": self.metrics,
            "deployed": self.deployed,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self) -> str:
        return f"<ModelVersion {self.model_version}>"


class ShapCache(db.Model):
    """
    Cached SHAP/explanation values for predictions
    
    REVISED: Schema-bound for reproducibility validation.
    
    shap_values format:
    [
        {"feature": "recency_days", "value": 45, "contribution": 0.32},
        {"feature": "complaint_rate_30d", "value": 0.8, "contribution": 0.25},
        ...
    ]
    """
    __tablename__ = "shap_cache"
    
    pred_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("churn_predictions.pred_id", ondelete="CASCADE"),
        primary_key=True
    )
    shap_values = db.Column(db.JSON, nullable=True)  # [{feature, value, contribution}]
    shap_top = db.Column(db.JSON, nullable=True)  # Top N formatted reasons
    nearest_messages = db.Column(db.JSON, nullable=True)  # Nearest messages (temporal-safe)
    computed_at = db.Column(db.DateTime, default=datetime.utcnow, server_default=db.func.now())
    explainer_version = db.Column(db.String(50), nullable=True)
    
    # Schema binding for reproducibility (CRITICAL)
    feature_schema_hash = db.Column(db.String(64), nullable=True)
    model_version = db.Column(db.String(50), nullable=True)
    explanation_type = db.Column(db.String(20), nullable=True)  # 'shap' or 'heuristic'
    as_of = db.Column(db.DateTime, nullable=True)  # Temporal anchor
    
    # Relationships
    prediction = db.relationship("ChurnPrediction", back_populates="shap_cache")
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary with EPISTEMOLOGICAL CATEGORY LABELING.
        
        IMPORTANT: Each explanation type is explicitly labeled to prevent
        category error (treating semantic similarity as causal attribution).
        """
        return {
            "pred_id": str(self.pred_id),
            
            # MODEL CONTRIBUTION (Mathematical feature attribution)
            "model_contribution": {
                "type": "shap" if self.explanation_type == "shap" else "heuristic",
                "source": "TreeExplainer on XGBoost" if self.explanation_type == "shap" else "domain_heuristic",
                "values": self.shap_top,
                "interpretation": "Mathematical contribution of each feature to model output"
            },
            
            # SUPPORTING EVIDENCE (NOT causal)
            "supporting_evidence": {
                "type": "semantic_similarity",
                "source": "pgvector_cosine_distance",
                "values": self.nearest_messages,
                "interpretation": "Similar past messages for context. NOT model input, NOT causal."
            },
            
            # EXPLICIT INTERPRETATION NOTE
            "interpretation_note": {
                "shap": "Feature contribution to model output (mathematical, not causal)",
                "nearest_messages": "Semantic similarity in embedding space, NOT causal attribution",
                "narrative": "Simplified explanation for non-technical users (may oversimplify)"
            },
            
            # PROVENANCE
            "provenance": {
                "computed_at": self.computed_at.isoformat() if self.computed_at else None,
                "as_of": self.as_of.isoformat() if self.as_of else None,
                "explainer_version": self.explainer_version,
                "feature_schema_hash": self.feature_schema_hash,
                "model_version": self.model_version,
                "explanation_type": self.explanation_type
            },
            
            # LEGACY (for backwards compatibility)
            "shap_values": self.shap_values,
            "shap_top": self.shap_top,
            "nearest_messages": self.nearest_messages
        }
    
    def __repr__(self) -> str:
        return f"<ShapCache {self.pred_id}>"

