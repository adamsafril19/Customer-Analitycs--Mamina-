"""create_churn_labels

Revision ID: 011_create_churn_labels
Revises: 010_cleanup_prediction_shap
Create Date: 2026-01-15

Create churn_labels table for ground truth with temporal separation.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '011_create_churn_labels'
down_revision = '010_cleanup_prediction_shap'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('churn_labels',
        sa.Column('label_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('observation_date', sa.Date(), nullable=False),
        sa.Column('outcome_date', sa.Date(), nullable=False),
        sa.Column('is_churned', sa.Boolean(), nullable=False),
        sa.Column('days_to_next_tx', sa.Integer(), nullable=True),
        sa.Column('last_tx_before_obs', sa.Date(), nullable=True),
        sa.Column('labeled_at', sa.DateTime(), nullable=True),
        sa.Column('label_method', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('label_id')
    )
    op.create_index('idx_churn_label_customer_obs', 'churn_labels', ['customer_id', 'observation_date'])
    op.create_unique_constraint('uq_churn_label_customer_date', 'churn_labels', ['customer_id', 'observation_date'])


def downgrade():
    op.drop_table('churn_labels')
