"""add_raw_transaction_signals

Revision ID: 009_add_raw_tx_signals
Revises: 008_add_semantic_avg_cols
Create Date: 2026-01-15

Add raw transaction signals to customer_numeric_features:
- recency_days, tx_count_30d, tx_count_90d
- spend_30d, spend_90d, avg_tx_value
"""
from alembic import op
import sqlalchemy as sa

revision = '009_add_raw_tx_signals'
down_revision = '008_add_semantic_avg_cols'
branch_labels = None
depends_on = None


def upgrade():
    # Add raw transaction signals
    op.add_column('customer_numeric_features', sa.Column('recency_days', sa.Integer(), nullable=True))
    op.add_column('customer_numeric_features', sa.Column('tx_count_30d', sa.Integer(), nullable=True))
    op.add_column('customer_numeric_features', sa.Column('tx_count_90d', sa.Integer(), nullable=True))
    op.add_column('customer_numeric_features', sa.Column('spend_30d', sa.Float(), nullable=True))
    op.add_column('customer_numeric_features', sa.Column('spend_90d', sa.Float(), nullable=True))
    op.add_column('customer_numeric_features', sa.Column('avg_tx_value', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('customer_numeric_features', 'recency_days')
    op.drop_column('customer_numeric_features', 'tx_count_30d')
    op.drop_column('customer_numeric_features', 'tx_count_90d')
    op.drop_column('customer_numeric_features', 'spend_30d')
    op.drop_column('customer_numeric_features', 'spend_90d')
    op.drop_column('customer_numeric_features', 'avg_tx_value')
