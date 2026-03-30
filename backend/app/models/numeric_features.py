"""
Customer Numeric Features Model

TRANSACTION-derived features (ML uses these)

Contains:
- Raw transaction signals (recency_days, tx_count, spend) - ML sees
- Derived RFM scores - Dashboard sees
"""
import uuid
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
from app import db


class CustomerNumericFeatures(db.Model):
    """
    Numeric features from transaction behavior
    
    This answers: "How active is this customer as a buyer?"
    
    ML model sees the RAW signals.
    Dashboard sees the derived RFM.
    """
    __tablename__ = "customer_numeric_features"
    
    feature_id = db.Column(
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
    as_of_date = db.Column(db.Date, nullable=False, index=True)
    
    # =========================================================================
    # RAW TRANSACTION SIGNALS (ML uses these)
    # =========================================================================
    
    # Recency - days since last transaction
    recency_days = db.Column(db.Integer, nullable=True, default=0)
    
    # Frequency - transaction counts
    tx_count_30d = db.Column(db.Integer, nullable=True, default=0)
    tx_count_90d = db.Column(db.Integer, nullable=True, default=0)
    
    # Monetary - spend amounts
    spend_30d = db.Column(db.Float, nullable=True, default=0.0)
    spend_90d = db.Column(db.Float, nullable=True, default=0.0)
    avg_tx_value = db.Column(db.Float, nullable=True, default=0.0)
    
    # Tenure
    tenure_days = db.Column(db.Integer, nullable=True, default=0)
    
    # =========================================================================
    # DERIVED RFM SCORES (Dashboard uses these)
    # =========================================================================
    
    r_score = db.Column(db.Float, nullable=True, default=0.0)
    f_score = db.Column(db.Float, nullable=True, default=0.0)
    m_score = db.Column(db.Float, nullable=True, default=0.0)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = db.relationship("Customer", back_populates="numeric_features")
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint("customer_id", "as_of_date", name="uq_numeric_features_date"),
        db.Index("idx_numeric_features_customer_date", "customer_id", "as_of_date"),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "feature_id": str(self.feature_id),
            "customer_id": str(self.customer_id),
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
            # Raw signals
            "recency_days": self.recency_days,
            "tx_count_30d": self.tx_count_30d,
            "tx_count_90d": self.tx_count_90d,
            "spend_30d": self.spend_30d,
            "spend_90d": self.spend_90d,
            "avg_tx_value": self.avg_tx_value,
            "tenure_days": self.tenure_days,
            # Derived RFM
            "r_score": self.r_score,
            "f_score": self.f_score,
            "m_score": self.m_score,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def to_feature_vector(self) -> list:
        """
        Convert to feature vector for ML
        
        Returns RAW signals: [recency_days, tx_count_30d, tx_count_90d, 
                              spend_30d, spend_90d, avg_tx_value, tenure_days]
        """
        return [
            float(self.recency_days or 0),
            float(self.tx_count_30d or 0),
            float(self.tx_count_90d or 0),
            self.spend_30d or 0.0,
            self.spend_90d or 0.0,
            self.avg_tx_value or 0.0,
            float(self.tenure_days or 0)
        ]
    
    def __repr__(self) -> str:
        return f"<CustomerNumericFeatures {self.customer_id} @ {self.as_of_date}>"
