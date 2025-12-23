"""
Action Model - Follow-up actions for churn prevention
"""
import uuid
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
from app import db


class Action(db.Model):
    """
    Follow-up action for churn prevention
    
    Attributes:
        action_id: Primary key (UUID)
        pred_id: Foreign key to churn_predictions (optional)
        customer_id: Foreign key to customers
        action_type: Type of action (call, promo, visit, email)
        priority: Priority level (low, medium, high)
        assigned_to: User assigned to action
        status: Action status (pending, in_progress, completed, cancelled)
        notes: Additional notes
        due_date: Due date for action
    """
    __tablename__ = "actions"
    
    action_id = db.Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    pred_id = db.Column(
        UUID(as_uuid=True), 
        db.ForeignKey("churn_predictions.pred_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    customer_id = db.Column(
        UUID(as_uuid=True), 
        db.ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    action_type = db.Column(db.String(50), nullable=False)  # call, promo, visit, email
    priority = db.Column(db.String(20), nullable=False, default="medium")  # low, medium, high
    assigned_to = db.Column(db.String(120), nullable=True)  # Email or username
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending, in_progress, completed, cancelled
    notes = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = db.relationship("Customer", back_populates="actions")
    prediction = db.relationship("ChurnPrediction", back_populates="actions")
    
    # Indexes
    __table_args__ = (
        db.Index("idx_action_status", "status"),
        db.Index("idx_action_priority", "priority"),
        db.Index("idx_action_assigned", "assigned_to"),
        db.Index("idx_action_due_date", "due_date"),
    )
    
    # Valid statuses
    VALID_STATUSES = ["pending", "in_progress", "completed", "cancelled"]
    VALID_PRIORITIES = ["low", "medium", "high"]
    VALID_ACTION_TYPES = ["call", "promo", "visit", "email"]
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "action_id": str(self.action_id),
            "pred_id": str(self.pred_id) if self.pred_id else None,
            "customer_id": str(self.customer_id),
            "action_type": self.action_type,
            "priority": self.priority,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "notes": self.notes,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_dict_with_customer(self) -> dict:
        """Convert to dictionary with customer info"""
        result = self.to_dict()
        if self.customer:
            result["customer_name"] = self.customer.name
        return result
    
    def __repr__(self) -> str:
        return f"<Action {self.action_id} - {self.action_type}>"
