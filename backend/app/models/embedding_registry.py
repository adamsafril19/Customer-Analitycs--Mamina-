"""
Embedding Model Registry

First-class model identity tracking.
All workers must use the same active_model_hash.
"""
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from app import db


class EmbeddingModelRegistry(db.Model):
    """
    Registry of embedding models used in the system.
    
    This ensures:
    1. All workers use same model identity
    2. Embeddings can be traced to specific model version
    3. Version drift is detectable
    """
    __tablename__ = "embedding_model_registry"
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Model identity
    model_name = db.Column(db.String(200), nullable=False)
    model_version = db.Column(db.String(100), nullable=False)
    model_hash = db.Column(db.String(50), nullable=False, unique=True, index=True)
    embedding_dim = db.Column(db.Integer, nullable=False)
    
    # Status
    is_active = db.Column(db.Boolean, default=False, index=True)  # Only one active at a time
    
    # Metadata
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    
    __table_args__ = (
        # Only one active model at a time
        db.Index("idx_active_model", "is_active", postgresql_where=db.text("is_active = true")),
    )
    
    @classmethod
    def get_active(cls) -> 'EmbeddingModelRegistry':
        """Get currently active model registration"""
        return cls.query.filter_by(is_active=True).first()
    
    @classmethod
    def get_active_hash(cls) -> str:
        """Get hash of currently active model"""
        active = cls.get_active()
        return active.model_hash if active else None
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_hash": self.model_hash,
            "embedding_dim": self.embedding_dim,
            "is_active": self.is_active,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None
        }
    
    def __repr__(self) -> str:
        active = " [ACTIVE]" if self.is_active else ""
        return f"<EmbeddingModel {self.model_version} ({self.model_hash}){active}>"
