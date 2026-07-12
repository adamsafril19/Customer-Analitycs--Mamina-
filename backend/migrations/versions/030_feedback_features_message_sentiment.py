"""add per-message sentiment to feedback features

Revision ID: 030_msg_sentiment
Revises: 029_recommendation_details
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa


revision = "030_msg_sentiment"
down_revision = "029_recommendation_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feedback_features",
        sa.Column("sentiment_label", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "feedback_features",
        sa.Column("sentiment_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "feedback_features",
        sa.Column("sentiment_model_version", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "feedback_features",
        sa.Column("sentiment_processed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_feedback_features_sentiment_label",
        "feedback_features",
        ["sentiment_label"],
        unique=False,
    )
    op.create_index(
        "ix_feedback_features_sentiment_model_version",
        "feedback_features",
        ["sentiment_model_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_features_sentiment_model_version", table_name="feedback_features")
    op.drop_index("ix_feedback_features_sentiment_label", table_name="feedback_features")
    op.drop_column("feedback_features", "sentiment_processed_at")
    op.drop_column("feedback_features", "sentiment_model_version")
    op.drop_column("feedback_features", "sentiment_score")
    op.drop_column("feedback_features", "sentiment_label")
