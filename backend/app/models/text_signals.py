"""
Customer Text Signals Model

BEHAVIORAL signals from text (how customer communicates).
Used by ML model for churn prediction.

Does NOT contain semantic features (topic, sentiment) - those go to text_semantics.
"""
import uuid
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app import db


class CustomerTextSignals(db.Model):
    """
    Behavioral signals from text communication
    
    This answers: "How does this customer communicate?"
    
    ML model sees this table.
    
    Attributes:
        id: Primary key (UUID)
        customer_id: Foreign key to customers
        as_of_date: Date when features were calculated
        msg_count_7d: Message count in last 7 days
        msg_count_30d: Message count in last 30 days
        msg_volatility: Std dev of daily message count
        avg_msg_length_30d: Average message length
        complaint_rate_30d: Ratio of complaint messages
        response_delay_mean: Average response time from admin
        avg_embedding: Mean embedding vector (384 dims)
        embedding_count_30d: Number of embeddings aggregated
    """
    __tablename__ = "customer_text_signals"
    
    id = db.Column(
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
    
    # Message volume (behavioral patterns)
    msg_count_7d = db.Column(db.Integer, nullable=True, default=0)
    msg_count_30d = db.Column(db.Integer, nullable=True, default=0)
    
    # Volatility (engagement pattern)
    msg_volatility = db.Column(db.Float, nullable=True, default=0.0)
    
    # Message characteristics
    avg_msg_length_30d = db.Column(db.Float, nullable=True, default=0.0)
    
    # Complaint rate (behavioral, not semantic)
    complaint_rate_30d = db.Column(db.Float, nullable=True, default=0.0)
    
    # Response metrics
    response_delay_mean = db.Column(db.Float, nullable=True, default=0.0)
    
    # Aggregated embedding (384 dims from MiniLM)
    avg_embedding = db.Column(Vector(384), nullable=True)
    embedding_count_30d = db.Column(db.Integer, nullable=True, default=0)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = db.relationship("Customer", back_populates="text_signals")
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint("customer_id", "as_of_date", name="uq_text_signals_date"),
        db.Index("idx_text_signals_customer_date", "customer_id", "as_of_date"),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "customer_id": str(self.customer_id),
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
            "msg_count_7d": self.msg_count_7d,
            "msg_count_30d": self.msg_count_30d,
            "msg_volatility": self.msg_volatility,
            "avg_msg_length_30d": self.avg_msg_length_30d,
            "complaint_rate_30d": self.complaint_rate_30d,
            "response_delay_mean": self.response_delay_mean,
            "embedding_count_30d": self.embedding_count_30d,
            "has_embedding": self.avg_embedding is not None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def to_feature_vector(self) -> list:
        """
        Convert to feature vector for ML (without embedding)
        
        Returns list of: [msg_count_7d, msg_count_30d, msg_volatility, 
                         avg_msg_length_30d, complaint_rate_30d, response_delay_mean]
        """
        return [
            float(self.msg_count_7d or 0),
            float(self.msg_count_30d or 0),
            self.msg_volatility or 0.0,
            self.avg_msg_length_30d or 0.0,
            self.complaint_rate_30d or 0.0,
            self.response_delay_mean or 0.0
        ]
    
    def get_embedding(self) -> list:
        """Get embedding as list (for ML)"""
        if self.avg_embedding is not None:
            if hasattr(self.avg_embedding, 'tolist'):
                return self.avg_embedding.tolist()
            return list(self.avg_embedding)
        return None
    
    def __repr__(self) -> str:
        return f"<CustomerTextSignals {self.customer_id} @ {self.as_of_date}>"
