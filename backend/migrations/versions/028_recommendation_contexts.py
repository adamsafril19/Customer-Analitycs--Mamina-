"""add auditable recommendation contexts

Revision ID: 028_recommendation_contexts
Revises: 027_transaction_features_v31
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "028_recommendation_contexts"
down_revision = "027_transaction_features_v31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_contexts",
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pred_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("context_status", sa.String(30), nullable=False),
        sa.Column("sentiment_label", sa.String(20), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("sentiment_trend", sa.Float(), nullable=True),
        sa.Column("dominant_topic_id", sa.String(50), nullable=True),
        sa.Column("dominant_topic_name", sa.Text(), nullable=True),
        sa.Column("topic_similarity", sa.Float(), nullable=True),
        sa.Column("complaint_ratio", sa.Float(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("evidence_messages", postgresql.JSONB(), nullable=True),
        sa.Column("recommended_action_type", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(), nullable=False),
        sa.Column("policy_version", sa.String(50), nullable=False),
        sa.Column("risk_model_version", sa.String(50), nullable=False),
        sa.Column("sentiment_model_version", sa.String(100), nullable=True),
        sa.Column("topic_model_version", sa.String(100), nullable=True),
        sa.Column("embedding_model_version", sa.String(100), nullable=True),
        sa.Column("review_status", sa.String(20), nullable=False),
        sa.Column("reviewed_by", sa.String(120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.customer_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["pred_id"], ["churn_predictions.pred_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("context_id"),
        sa.UniqueConstraint("pred_id"),
    )
    op.create_index(
        "ix_recommendation_contexts_pred_id",
        "recommendation_contexts",
        ["pred_id"],
    )
    op.create_index(
        "ix_recommendation_contexts_customer_id",
        "recommendation_contexts",
        ["customer_id"],
    )
    op.create_index(
        "ix_recommendation_contexts_as_of_date",
        "recommendation_contexts",
        ["as_of_date"],
    )
    op.create_index(
        "idx_recommendation_customer_date",
        "recommendation_contexts",
        ["customer_id", "as_of_date"],
    )
    op.create_index(
        "idx_recommendation_review_status",
        "recommendation_contexts",
        ["review_status"],
    )


def downgrade() -> None:
    op.drop_table("recommendation_contexts")
