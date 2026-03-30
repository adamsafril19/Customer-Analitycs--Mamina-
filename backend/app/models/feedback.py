"""
Feedback Models (Raw, Linked, Features)

REVISED: Proper identity resolution architecture

Layer 1 - FeedbackRaw: NO customer_id (just phone_number)
Layer 2 - FeedbackLinked: Identity resolution (phone → customer)
Layer 3 - FeedbackFeatures: Statistical signals (after linking)
"""
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from app import db


class FeedbackRaw(db.Model):
    """
    Raw WhatsApp messages - NO IDENTITY RESOLUTION HERE
    
    This is raw observational data from WhatsApp export.
    Identity linking happens in FeedbackLinked.
    
    Attributes:
        msg_id: Primary key (UUID)
        phone_number: Hashed phone number from WhatsApp
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
    phone_number = db.Column(db.String(256), nullable=False, index=True)  # Hashed
    direction = db.Column(db.String(20), nullable=False)  # inbound, outbound
    text = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    raw_meta = db.Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    linked = db.relationship(
        "FeedbackLinked", 
        back_populates="feedback_raw", 
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    def to_dict(self) -> dict:
        return {
            "msg_id": str(self.msg_id),
            "phone_number": self.phone_number[:8] + "***",  # Masked
            "direction": self.direction,
            "text": self.text,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self) -> str:
        return f"<FeedbackRaw {self.msg_id}>"


class FeedbackLinked(db.Model):
    """
    Identity resolution layer
    
    This links raw messages to customers.
    Stores match confidence for audit trail.
    
    Attributes:
        link_id: Primary key
        msg_id: FK to feedback_raw
        customer_id: FK to customers (resolved identity)
        match_confidence: Confidence of the linking (0-1)
        match_method: How the linking was done (phone_exact, phone_fuzzy, manual)
        linked_at: When the linking was performed
    """
    __tablename__ = "feedback_linked"
    
    link_id = db.Column(
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
    
    # Linking metadata
    match_confidence = db.Column(db.Float, nullable=True, default=1.0)
    match_method = db.Column(db.String(50), nullable=True, default="phone_exact")
    # Link status for clearer semantics (verified, probable, provisional, rejected)
    link_status = db.Column(db.String(20), nullable=False, default='provisional', index=True)
    linked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    feedback_raw = db.relationship("FeedbackRaw", back_populates="linked")
    customer = db.relationship("Customer", backref="feedback_linked")
    features = db.relationship(
        "FeedbackFeatures", 
        back_populates="linked", 
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    def to_dict(self) -> dict:
        return {
            "link_id": str(self.link_id),
            "msg_id": str(self.msg_id),
            "customer_id": str(self.customer_id),
            "match_confidence": self.match_confidence,
            "match_method": self.match_method,
            "linked_at": self.linked_at.isoformat() if self.linked_at else None
        }
    
    def __repr__(self) -> str:
        return f"<FeedbackLinked {self.msg_id} -> {self.customer_id}>"


class FeedbackFeatures(db.Model):
    """
    Extracted signals from messages (AFTER identity resolution)
    
    Contains both:
    - Statistical signals (msg_length, punctuation) - safe for ML
    - Semantic representation (embedding) - requires verified identity
    
    IMPORTANT: embedding is SEMANTIC (compressed meaning), not statistical.
    """
    __tablename__ = "feedback_features"
    
    feature_id = db.Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    link_id = db.Column(
        UUID(as_uuid=True), 
        db.ForeignKey("feedback_linked.link_id", ondelete="CASCADE"),
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
    
    # =========================================================================
    # STATISTICAL SIGNALS (OK for ML)
    # =========================================================================
    
    msg_length = db.Column(db.Integer, nullable=True)
    num_exclamations = db.Column(db.Integer, nullable=True)
    num_questions = db.Column(db.Integer, nullable=True)
    
    # =========================================================================
    # SEMANTIC REPRESENTATION (requires verified identity)
    # =========================================================================
    
    # Embedding = compressed meaning (NOT statistical!)
    # Only use for verified links in ML
    embedding = db.Column(Vector(384), nullable=True)
    # Track model version for semantic continuity (like sentiment/topic)
    embedding_model_version = db.Column(db.String(100), nullable=True, index=True)
    
    # Rule-based flags (regex patterns, NOT ML predictions)
    has_complaint = db.Column(db.Boolean, nullable=True, default=False)
    has_refund_request = db.Column(db.Boolean, nullable=True, default=False)
    
    language_confidence = db.Column(db.Float, nullable=True)
    response_time_secs = db.Column(db.Integer, nullable=True)
    
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    linked = db.relationship("FeedbackLinked", back_populates="features")
    customer = db.relationship("Customer", back_populates="feedback_features")
    
    def to_dict(self) -> dict:
        return {
            "feature_id": str(self.feature_id),
            "link_id": str(self.link_id),
            "customer_id": str(self.customer_id),
            "msg_length": self.msg_length,
            "num_exclamations": self.num_exclamations,
            "num_questions": self.num_questions,
            "has_complaint": self.has_complaint,
            "has_refund_request": self.has_refund_request,
            "language_confidence": self.language_confidence,
            "response_time_secs": self.response_time_secs,
            "has_embedding": self.embedding is not None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None
        }
    
    def __repr__(self) -> str:
        return f"<FeedbackFeatures {self.feature_id}>"
