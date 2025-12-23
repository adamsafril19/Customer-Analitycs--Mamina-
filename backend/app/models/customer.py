"""
Customer Model
"""
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from app import db


class Customer(db.Model):
    """
    Customer model - Core entity
    
    Attributes:
        customer_id: Primary key (UUID)
        external_id: Hashed external identifier (for privacy)
        name: Customer name
        phone_hash: Hashed phone number (for privacy)
        city: Customer city
        consent_given: Whether customer has given data processing consent
        is_active: Whether customer is active
    """
    __tablename__ = "customers"
    
    customer_id = db.Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    external_id = db.Column(db.String(256), unique=True, nullable=True, index=True)
    name = db.Column(db.String(200), nullable=False)
    phone_hash = db.Column(db.String(256), unique=True, nullable=True, index=True)
    city = db.Column(db.String(100), nullable=True)
    consent_given = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    transactions = db.relationship(
        "Transaction", 
        back_populates="customer", 
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    feedback_raw = db.relationship(
        "FeedbackRaw", 
        back_populates="customer", 
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    feedback_clean = db.relationship(
        "FeedbackClean", 
        back_populates="customer", 
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    features = db.relationship(
        "CustomerFeature", 
        back_populates="customer", 
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    predictions = db.relationship(
        "ChurnPrediction", 
        back_populates="customer", 
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    actions = db.relationship(
        "Action", 
        back_populates="customer", 
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "customer_id": str(self.customer_id),
            "name": self.name,
            "city": self.city,
            "consent_given": self.consent_given,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None
        }
    
    def to_dict_summary(self) -> dict:
        """Convert to summary dictionary (for list views)"""
        return {
            "customer_id": str(self.customer_id),
            "name": self.name,
            "city": self.city,
            "is_active": self.is_active
        }
    
    def __repr__(self) -> str:
        return f"<Customer {self.name}>"
