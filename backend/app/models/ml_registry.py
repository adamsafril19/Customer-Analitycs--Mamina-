"""
ML Model Registry

First-class ML model identity tracking.
All predictions must be traceable to specific model version.
"""
import uuid
import hashlib
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app import db


class MLModelRegistry(db.Model):
    """
    Registry of ML models used for predictions.
    
    Ensures:
    1. Predictions are traceable to model version
    2. Model-feature schema binding
    3. Model-SHAP explainer binding
    4. Training data provenance
    """
    __tablename__ = "ml_model_registry"
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Model identity
    model_name = db.Column(db.String(100), nullable=False, default="churn_model")
    model_version = db.Column(db.String(50), nullable=False)
    model_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    
    # Feature schema binding
    feature_schema_hash = db.Column(db.String(64), nullable=False)
    feature_names = db.Column(JSONB, nullable=True)  # List of feature names in order
    expected_feature_count = db.Column(db.Integer, nullable=False)
    
    # Training provenance
    trained_on_embedding_model_hash = db.Column(db.String(50), nullable=True)
    trained_on_link_status = db.Column(db.String(50), default="verified")  # What identity level
    training_data_count = db.Column(db.Integer, nullable=True)
    training_date = db.Column(db.DateTime, nullable=True)
    
    # SHAP binding
    shap_explainer_hash = db.Column(db.String(64), nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=False, index=True)
    
    # Metadata
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    
    __table_args__ = (
        db.Index("idx_ml_active_model", "is_active", postgresql_where=db.text("is_active = true")),
    )
    
    @classmethod
    def get_active(cls) -> 'MLModelRegistry':
        """Get currently active model"""
        return cls.query.filter_by(is_active=True).first()
    
    @classmethod
    def get_active_hash(cls) -> str:
        """Get hash of currently active model"""
        active = cls.get_active()
        return active.model_hash if active else None
    
    @classmethod
    def compute_feature_schema_hash(cls, feature_names: list) -> str:
        """Compute hash of feature schema for binding"""
        schema_str = "|".join(sorted(feature_names))
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]
    
    def validate_features(self, feature_vector: list, feature_names: list = None) -> bool:
        """
        Validate feature vector against model's expected schema.
        
        Returns True if valid, raises ValueError if not.
        """
        if len(feature_vector) != self.expected_feature_count:
            raise ValueError(
                f"Feature count mismatch: got {len(feature_vector)}, "
                f"model expects {self.expected_feature_count}"
            )
        
        if feature_names and self.feature_names:
            if feature_names != self.feature_names:
                raise ValueError(
                    f"Feature schema mismatch: got {feature_names}, "
                    f"model expects {self.feature_names}"
                )
        
        return True
    
    def validate_shap(self, shap_hash: str) -> bool:
        """Validate SHAP explainer matches this model"""
        if self.shap_explainer_hash and shap_hash != self.shap_explainer_hash:
            raise ValueError(
                f"SHAP explainer mismatch: got {shap_hash}, "
                f"model expects {self.shap_explainer_hash}"
            )
        return True
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_hash": self.model_hash,
            "feature_schema_hash": self.feature_schema_hash,
            "expected_feature_count": self.expected_feature_count,
            "trained_on_link_status": self.trained_on_link_status,
            "is_active": self.is_active,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None
        }
    
    def __repr__(self) -> str:
        active = " [ACTIVE]" if self.is_active else ""
        return f"<MLModel {self.model_version} ({self.model_hash[:8]}){active}>"
