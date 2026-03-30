"""
Churn Prediction Model

REVISED: Semantically dumb - only numerical output, no storytelling
"""
import uuid
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
from app import db


class ChurnPrediction(db.Model):
    """
    Churn prediction results (numerical output only)
    
    This is MODEL OUTPUT layer - no interpretations/narratives.
    
    Attributes:
        pred_id: Primary key (UUID)
        customer_id: Foreign key to customers
        churn_score: Probability of churn (0-1)
        churn_label: Label (low, medium, high)
        model_version: Version of model used
        as_of_date: Date of prediction
    """
    __tablename__ = "churn_predictions"
    
    pred_id = db.Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    customer_id = db.Column(
        UUID(as_uuid=True), 
        db.ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    churn_score = db.Column(db.Float, nullable=False)  # Probability 0-1
    churn_label = db.Column(db.String(20), nullable=False)  # low, medium, high
    model_version = db.Column(db.String(50), nullable=False)
    as_of_date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # EPISTEMOLOGICAL PROVENANCE (Immutable prediction artifacts)
    # Explainer should reference these, not reconstruct
    features_used = db.Column(
        db.JSON, 
        nullable=True,
        comment="Immutable snapshot of features at prediction time"
    )
    feature_as_of = db.Column(
        db.DateTime, 
        nullable=True,
        comment="Exact timestamp features were computed (for Explainer)"
    )
    feature_schema_hash = db.Column(
        db.String(64), 
        nullable=True,
        comment="Hash of feature schema at prediction time"
    )
    model_hash = db.Column(
        db.String(32), 
        nullable=True,
        comment="Hash of model used for prediction"
    )
    
    # Relationships
    customer = db.relationship("Customer", back_populates="predictions")
    actions = db.relationship(
        "Action", 
        back_populates="prediction", 
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    shap_cache = db.relationship(
        "ShapCache",
        back_populates="prediction",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        db.Index("idx_pred_customer_date", "customer_id", "as_of_date"),
        db.Index("idx_pred_label", "churn_label"),
        db.Index("idx_pred_score", "churn_score"),
        db.Index("idx_pred_feature_as_of", "feature_as_of"),
    )
    
    @staticmethod
    def score_to_label(score: float) -> str:
        """Convert churn score to label"""
        if score < 0.3:
            return "low"
        elif score < 0.7:
            return "medium"
        else:
            return "high"
    
    def to_dict(self) -> dict:
        """Convert to dictionary with full epistemological provenance"""
        return {
            "pred_id": str(self.pred_id),
            "customer_id": str(self.customer_id),
            "churn_score": self.churn_score,
            "churn_label": self.churn_label,
            "model_version": self.model_version,
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            # EPISTEMOLOGICAL PROVENANCE
            "provenance": {
                "features_used": self.features_used,
                "feature_as_of": self.feature_as_of.isoformat() if self.feature_as_of else None,
                "feature_schema_hash": self.feature_schema_hash,
                "model_hash": self.model_hash
            }
        }
    
    def __repr__(self) -> str:
        return f"<ChurnPrediction {self.pred_id} - {self.churn_label}>"
