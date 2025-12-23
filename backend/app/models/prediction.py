"""
Churn Prediction Model
"""
import uuid
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app import db


class ChurnPrediction(db.Model):
    """
    Churn prediction results
    
    Attributes:
        pred_id: Primary key (UUID)
        customer_id: Foreign key to customers
        churn_score: Probability of churn (0-1)
        churn_label: Label (low, medium, high)
        top_reasons: Top contributing factors with SHAP values
        model_version: Version of model used for prediction
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
    top_reasons = db.Column(JSONB, nullable=True)  # [{feature, impact, description}]
    model_version = db.Column(db.String(50), nullable=False)
    as_of_date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = db.relationship("Customer", back_populates="predictions")
    actions = db.relationship(
        "Action", 
        back_populates="prediction", 
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        db.Index("idx_pred_customer_date", "customer_id", "as_of_date"),
        db.Index("idx_pred_label", "churn_label"),
        db.Index("idx_pred_score", "churn_score"),
    )
    
    @staticmethod
    def score_to_label(score: float) -> str:
        """
        Convert churn score to label
        
        Thresholds:
        - Low: < 0.3
        - Medium: 0.3 - 0.7
        - High: > 0.7
        """
        if score < 0.3:
            return "low"
        elif score < 0.7:
            return "medium"
        else:
            return "high"
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "pred_id": str(self.pred_id),
            "customer_id": str(self.customer_id),
            "churn_score": self.churn_score,
            "churn_label": self.churn_label,
            "top_reasons": self.top_reasons,
            "model_version": self.model_version,
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def to_dict_with_customer(self) -> dict:
        """Convert to dictionary with customer info"""
        result = self.to_dict()
        if self.customer:
            result["customer_name"] = self.customer.name
        return result
    
    def __repr__(self) -> str:
        return f"<ChurnPrediction {self.pred_id} - {self.churn_label}>"
