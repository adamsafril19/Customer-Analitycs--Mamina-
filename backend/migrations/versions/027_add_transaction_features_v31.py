"""add transaction-derived features v3.1

Revision ID: 027_transaction_features_v31
Revises: 28a4ab1f4514
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa


revision = "027_transaction_features_v31"
down_revision = "28a4ab1f4514"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_numeric_features",
        sa.Column("homecare_tx_ratio_90d", sa.Float(), nullable=True),
    )
    op.add_column(
        "customer_numeric_features",
        sa.Column("last_tx_is_homecare", sa.Float(), nullable=True),
    )
    op.add_column(
        "customer_numeric_features",
        sa.Column("zero_amount_tx_count_90d", sa.Integer(), nullable=True),
    )
    op.add_column(
        "customer_numeric_features",
        sa.Column("lifetime_tx_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customer_numeric_features", "lifetime_tx_count")
    op.drop_column("customer_numeric_features", "zero_amount_tx_count_90d")
    op.drop_column("customer_numeric_features", "last_tx_is_homecare")
    op.drop_column("customer_numeric_features", "homecare_tx_ratio_90d")
