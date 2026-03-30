"""
Churn Label Model

Ground truth labels for ML training.
Uses TEMPORAL SEPARATION to avoid data leakage.

observation_date = when features are calculated
outcome_date = 90 days after observation_date
is_churned = no transaction between observation_date and outcome_date
"""
import uuid
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
from app import db


class ChurnLabel(db.Model):
    """
    Ground truth churn labels
    
    This stores HISTORICAL outcomes for ML training.
    
    Temporal separation:
    - Features calculated AS OF observation_date
    - Label determined by behavior AFTER observation_date
    
    Definition:
    - is_churned = TRUE if no transaction in 90 days after observation_date
    
    Example:
    - observation_date = 2024-01-01
    - outcome_date = 2024-04-01 (90 days later)
    - is_churned = TRUE if no TX between Jan 1 - Apr 1
    """
    __tablename__ = "churn_labels"
    
    label_id = db.Column(
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
    
    # Temporal separation
    observation_date = db.Column(db.Date, nullable=False, index=True)  # When features calculated
    outcome_date = db.Column(db.Date, nullable=False)  # 90 days after observation
    
    # Ground truth
    is_churned = db.Column(db.Boolean, nullable=False)  # Did customer churn?
    
    # Additional context
    days_to_next_tx = db.Column(db.Integer, nullable=True)  # Days until next TX (if any)
    last_tx_before_obs = db.Column(db.Date, nullable=True)  # Last TX before observation
    
    # Metadata
    labeled_at = db.Column(db.DateTime, default=datetime.utcnow)
    label_method = db.Column(db.String(50), default="automatic")  # automatic, manual
    
    # Relationships
    customer = db.relationship("Customer", backref="churn_labels")
    
    # Unique constraint - one label per customer per observation date
    __table_args__ = (
        db.UniqueConstraint("customer_id", "observation_date", name="uq_churn_label_customer_date"),
        db.Index("idx_churn_label_customer_obs", "customer_id", "observation_date"),
    )
    
    def to_dict(self) -> dict:
        return {
            "label_id": str(self.label_id),
            "customer_id": str(self.customer_id),
            "observation_date": self.observation_date.isoformat() if self.observation_date else None,
            "outcome_date": self.outcome_date.isoformat() if self.outcome_date else None,
            "is_churned": self.is_churned,
            "days_to_next_tx": self.days_to_next_tx,
            "last_tx_before_obs": self.last_tx_before_obs.isoformat() if self.last_tx_before_obs else None,
            "label_method": self.label_method
        }
    
    def __repr__(self) -> str:
        return f"<ChurnLabel {self.customer_id} @ {self.observation_date}: {self.is_churned}>"
