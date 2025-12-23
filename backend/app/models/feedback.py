"""
Feedback Models (Raw and Clean)
"""
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from app import db


class FeedbackRaw(db.Model):
    """
    Raw feedback/message from WhatsApp
    
    Attributes:
        msg_id: Primary key (UUID)
        customer_id: Foreign key to customers
        direction: Message direction (inbound, outbound)
        text: Raw message text
        timestamp: Original message timestamp
        raw_meta: Original metadata from WhatsApp (JSONB)
    """
    __tablename__ = "feedback_raw"
    
    msg_id = db.Column(
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
    direction = db.Column(db.String(20), nullable=False)  # inbound, outbound
    text = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    raw_meta = db.Column(JSONB, nullable=True)  # Original WhatsApp metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = db.relationship("Customer", back_populates="feedback_raw")
    feedback_clean = db.relationship(
        "FeedbackClean", 
        back_populates="feedback_raw", 
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "msg_id": str(self.msg_id),
            "customer_id": str(self.customer_id),
            "direction": self.direction,
            "text": self.text,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self) -> str:
        return f"<FeedbackRaw {self.msg_id}>"


class FeedbackClean(db.Model):
    """
    Processed/cleaned feedback with NLP features
    
    Attributes:
        feedback_id: Primary key (UUID)
        msg_id: Foreign key to feedback_raw
        customer_id: Foreign key to customers
        sentiment_score: Sentiment score (-1 to 1)
        sentiment_label: Sentiment label (positive, neutral, negative)
        topic_labels: Array of detected topics
        keywords_emotion: Emotion keywords with scores (JSONB)
        response_time_secs: Time to respond in seconds
        intensity_7d: Number of messages in last 7 days
    """
    __tablename__ = "feedback_clean"
    
    feedback_id = db.Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    msg_id = db.Column(
        UUID(as_uuid=True), 
        db.ForeignKey("feedback_raw.msg_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    customer_id = db.Column(
        UUID(as_uuid=True), 
        db.ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    sentiment_score = db.Column(db.Float, nullable=True)  # Range: -1 to 1
    sentiment_label = db.Column(db.String(20), nullable=True)  # positive, neutral, negative
    topic_labels = db.Column(ARRAY(db.String), nullable=True)  # Array of topics
    keywords_emotion = db.Column(JSONB, nullable=True)  # {angry: 0.8, sad: 0.2}
    response_time_secs = db.Column(db.Integer, nullable=True)
    intensity_7d = db.Column(db.Integer, nullable=True)  # Messages in last 7 days
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = db.relationship("Customer", back_populates="feedback_clean")
    feedback_raw = db.relationship("FeedbackRaw", back_populates="feedback_clean")
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "feedback_id": str(self.feedback_id),
            "msg_id": str(self.msg_id),
            "customer_id": str(self.customer_id),
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "topic_labels": self.topic_labels,
            "keywords_emotion": self.keywords_emotion,
            "response_time_secs": self.response_time_secs,
            "intensity_7d": self.intensity_7d,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None
        }
    
    def __repr__(self) -> str:
        return f"<FeedbackClean {self.feedback_id}>"
