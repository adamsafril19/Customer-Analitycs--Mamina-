"""
Customer Feature Model
"""
import uuid
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
from app import db


class CustomerFeature(db.Model):
    """
    Customer features for ML prediction
    
    Features include:
    - RFM (Recency, Frequency, Monetary)
    - Tenure
    - Sentiment metrics
    - Response time metrics
    - Message intensity
    
    Attributes:
        feature_id: Primary key (UUID)
        customer_id: Foreign key to customers
        as_of_date: Date when features were calculated
        r_score: Recency score
        f_score: Frequency score
        m_score: Monetary score
        tenure_days: Days since first transaction
        avg_sentiment_30: Average sentiment in last 30 days
        neg_msg_count_30: Count of negative messages in last 30 days
        avg_response_secs: Average response time in seconds
        intensity_7d: Message count in last 7 days
    """
    __tablename__ = "customer_features"
    
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
    
    # RFM Features
    r_score = db.Column(db.Float, nullable=True)  # Recency
    f_score = db.Column(db.Float, nullable=True)  # Frequency
    m_score = db.Column(db.Float, nullable=True)  # Monetary
    
    # Tenure
    tenure_days = db.Column(db.Integer, nullable=True)
    
    # Sentiment Features
    avg_sentiment_30 = db.Column(db.Float, nullable=True)  # Last 30 days average
    neg_msg_count_30 = db.Column(db.Integer, nullable=True)  # Negative messages count
    
    # Response Metrics
    avg_response_secs = db.Column(db.Float, nullable=True)
    
    # Intensity
    intensity_7d = db.Column(db.Integer, nullable=True)  # Messages in last 7 days
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = db.relationship("Customer", back_populates="features")
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint("customer_id", "as_of_date", name="uq_customer_features_date"),
        db.Index("idx_features_customer_date", "customer_id", "as_of_date"),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "feature_id": str(self.feature_id),
            "customer_id": str(self.customer_id),
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
            "r_score": self.r_score,
            "f_score": self.f_score,
            "m_score": self.m_score,
            "tenure_days": self.tenure_days,
            "avg_sentiment_30": self.avg_sentiment_30,
            "neg_msg_count_30": self.neg_msg_count_30,
            "avg_response_secs": self.avg_response_secs,
            "intensity_7d": self.intensity_7d,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def to_feature_vector(self) -> list:
        """
        Convert to feature vector for ML model
        
        IMPORTANT: Order must match training feature order!
        See models/features.json for expected order.
        """
        return [
            self.r_score or 0,
            self.f_score or 0,
            self.m_score or 0,
            self.tenure_days or 0,
            self.avg_sentiment_30 or 0,
            self.neg_msg_count_30 or 0,
            self.avg_response_secs or 0,
            self.intensity_7d or 0
        ]
    
    def __repr__(self) -> str:
        return f"<CustomerFeature {self.customer_id} @ {self.as_of_date}>"
