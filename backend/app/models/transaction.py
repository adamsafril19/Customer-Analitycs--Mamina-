"""
Transaction Model
"""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy.dialects.postgresql import UUID
from app import db


class Transaction(db.Model):
    """
    Transaction model - Customer transactions
    
    Attributes:
        tx_id: Primary key (UUID)
        customer_id: Foreign key to customers
        tx_date: Transaction date/time
        service_type: Type of service (e.g., baby_spa, pijat_laktasi)
        amount: Transaction amount
        status: Transaction status (completed, cancelled)
    """
    __tablename__ = "transactions"
    
    tx_id = db.Column(
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
    tx_date = db.Column(db.DateTime, nullable=False, index=True)
    service_type = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    status = db.Column(db.String(20), nullable=False, default="completed")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = db.relationship("Customer", back_populates="transactions")
    
    # Indexes
    __table_args__ = (
        db.Index("idx_tx_customer_date", "customer_id", "tx_date"),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "tx_id": str(self.tx_id),
            "customer_id": str(self.customer_id),
            "tx_date": self.tx_date.isoformat() if self.tx_date else None,
            "service_type": self.service_type,
            "amount": float(self.amount) if self.amount else 0,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self) -> str:
        return f"<Transaction {self.tx_id} - {self.service_type}>"
