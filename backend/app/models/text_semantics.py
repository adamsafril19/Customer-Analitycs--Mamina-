"""
Customer Text Semantics Model

SEMANTIC features (what customer talks about).
Used by DASHBOARD ONLY for explanation and drilldown.

ML model does NOT see this table - prevents data leakage.

Updated: Added avg_sentiment_score, avg_topic_confidence
"""
import uuid
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app import db


class CustomerTextSemantics(db.Model):
    """
    Semantic features from text content (per-customer aggregated)
    
    This answers: "What is this customer talking about?"
    
    Dashboard sees this table.
    ML model does NOT see this table.
    
    Columns from feedback_features that were MOVED here:
    - sentiment_label -> sentiment_dist (distribusi)
    - sentiment_score -> avg_sentiment_score (rata-rata)
    - topic_id -> top_topic_counts (distribusi)
    - topic_confidence -> avg_topic_confidence (rata-rata)
    - complaint_type -> top_complaint_types (distribusi)
    - keywords -> top_keywords (agregat)
    """
    __tablename__ = "customer_text_semantics"
    
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
    
    # === AGGREGATED FROM feedback_features semantic columns ===
    
    # Topic distribution: {topic_id: count}
    # NOTE: topic_id here is BERTopic index, valid only for specific model_version
    top_topic_counts = db.Column(JSONB, nullable=True)
    
    # Average topic similarity (NOT confidence!)
    # NOTE: This is cosine similarity to cluster centroid, NOT probability
    avg_topic_similarity = db.Column(db.Float, nullable=True)
    
    # Which topic model version was used (for semantic continuity)
    topic_model_version = db.Column(db.String(50), nullable=True, index=True)
    
    # Sentiment distribution: {positive: n, neutral: n, negative: n}
    sentiment_dist = db.Column(JSONB, nullable=True)
    
    # Average sentiment score (-1 to 1) using valence = P(pos) - P(neg)
    # NOTE: This is model-relative, not absolute psychological scale
    avg_sentiment_score = db.Column(db.Float, nullable=True)
    
    # Which sentiment model version was used (for semantic continuity)
    sentiment_model_version = db.Column(db.String(100), nullable=True, index=True)
    
    # Extracted keywords: {keyword: count}
    top_keywords = db.Column(JSONB, nullable=True)
    
    # Complaint type distribution: {delivery: n, product: n, ...}
    top_complaint_types = db.Column(JSONB, nullable=True)
    
    # Last N message IDs for drilldown (with timestamps for auditability)
    last_n_msg_ids = db.Column(JSONB, nullable=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = db.relationship("Customer", back_populates="text_semantics")
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint("customer_id", "as_of_date", name="uq_text_semantics_date"),
        db.Index("idx_text_semantics_customer_date", "customer_id", "as_of_date"),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for dashboard/API"""
        return {
            "id": str(self.id),
            "customer_id": str(self.customer_id),
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
            "top_topic_counts": self.top_topic_counts,
            "avg_topic_similarity": self.avg_topic_similarity,
            "topic_model_version": self.topic_model_version,
            "sentiment_dist": self.sentiment_dist,
            "avg_sentiment_score": self.avg_sentiment_score,
            "top_keywords": self.top_keywords,
            "top_complaint_types": self.top_complaint_types,
            "last_n_msg_ids": self.last_n_msg_ids,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def get_dominant_topic(self) -> str:
        """Get the most frequent topic ID"""
        if not self.top_topic_counts:
            return None
        return max(self.top_topic_counts, key=self.top_topic_counts.get)
    
    def get_dominant_sentiment(self) -> str:
        """Get the most frequent sentiment label"""
        if not self.sentiment_dist:
            return None
        return max(self.sentiment_dist, key=self.sentiment_dist.get)
    
    def __repr__(self) -> str:
        return f"<CustomerTextSemantics {self.customer_id} @ {self.as_of_date}>"
