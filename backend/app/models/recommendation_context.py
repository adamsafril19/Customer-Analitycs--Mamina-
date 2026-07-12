"""Auditable decision-support context attached to a risk prediction."""
import uuid
from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB, UUID

from app import db


class RecommendationContext(db.Model):
    __tablename__ = "recommendation_contexts"

    context_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pred_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("churn_predictions.pred_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    customer_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    as_of_date = db.Column(db.Date, nullable=False, index=True)

    context_status = db.Column(db.String(30), nullable=False, default="unavailable")
    sentiment_label = db.Column(db.String(20), nullable=True)
    sentiment_score = db.Column(db.Float, nullable=True)
    sentiment_trend = db.Column(db.Float, nullable=True)
    dominant_topic_id = db.Column(db.String(50), nullable=True)
    dominant_topic_name = db.Column(db.Text, nullable=True)
    topic_similarity = db.Column(db.Float, nullable=True)
    complaint_ratio = db.Column(db.Float, nullable=True)
    message_count = db.Column(db.Integer, nullable=False, default=0)
    last_message_at = db.Column(db.DateTime, nullable=True)
    evidence_messages = db.Column(JSONB, nullable=True)

    recommended_action_type = db.Column(db.String(50), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    rationale = db.Column(db.Text, nullable=False)
    reason_codes = db.Column(JSONB, nullable=False, default=list)
    recommendation_details = db.Column(JSONB, nullable=True)
    policy_version = db.Column(db.String(50), nullable=False)

    risk_model_version = db.Column(db.String(50), nullable=False)
    sentiment_model_version = db.Column(db.String(100), nullable=True)
    topic_model_version = db.Column(db.String(100), nullable=True)
    embedding_model_version = db.Column(db.String(100), nullable=True)

    review_status = db.Column(db.String(20), nullable=False, default="pending")
    reviewed_by = db.Column(db.String(120), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    prediction = db.relationship(
        "ChurnPrediction",
        back_populates="recommendation_context",
    )

    __table_args__ = (
        db.Index(
            "idx_recommendation_customer_date",
            "customer_id",
            "as_of_date",
        ),
        db.Index("idx_recommendation_review_status", "review_status"),
    )

    def to_dict(self) -> dict:
        return {
            "context_id": str(self.context_id),
            "pred_id": str(self.pred_id),
            "customer_id": str(self.customer_id),
            "as_of_date": self.as_of_date.isoformat(),
            "context_status": self.context_status,
            "customer_voice": {
                "sentiment_label": self.sentiment_label,
                "sentiment_score": self.sentiment_score,
                "sentiment_trend": self.sentiment_trend,
                "dominant_topic_id": self.dominant_topic_id,
                "dominant_topic_name": self.dominant_topic_name,
                "topic_similarity": self.topic_similarity,
                "complaint_ratio": self.complaint_ratio,
                "message_count": self.message_count,
                "last_message_at": (
                    self.last_message_at.isoformat()
                    if self.last_message_at else None
                ),
                "evidence_messages": self.evidence_messages or [],
            },
            "recommendation": {
                "action_type": self.recommended_action_type,
                "priority": self.priority,
                "title": self.title,
                "rationale": self.rationale,
                "reason_codes": self.reason_codes or [],
                "details": self.recommendation_details or {},
                "policy_version": self.policy_version,
            },
            "provenance": {
                "risk_model_version": self.risk_model_version,
                "sentiment_model_version": self.sentiment_model_version,
                "topic_model_version": self.topic_model_version,
                "embedding_model_version": self.embedding_model_version,
                "interpretation": "nlp_context_supports_action_not_risk_causality",
            },
            "review": {
                "status": self.review_status,
                "reviewed_by": self.reviewed_by,
                "reviewed_at": (
                    self.reviewed_at.isoformat() if self.reviewed_at else None
                ),
            },
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
