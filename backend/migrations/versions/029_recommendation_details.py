"""add structured recommendation details

Revision ID: 029_recommendation_details
Revises: 028_recommendation_contexts
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "029_recommendation_details"
down_revision = "028_recommendation_contexts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recommendation_contexts",
        sa.Column(
            "recommendation_details",
            postgresql.JSONB(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("recommendation_contexts", "recommendation_details")
