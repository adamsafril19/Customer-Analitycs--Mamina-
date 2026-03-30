"""milestone2_text_features

Revision ID: 004_milestone2_text_features
Revises: 003_semantic_layer
Create Date: 2026-01-13

Add new columns to customer_text_features for Milestone 2:
- top_topic_counts (JSONB)
- sentiment_dist (JSONB)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_milestone2_text_features'
down_revision = '003_semantic_layer'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to customer_text_features
    op.add_column('customer_text_features', 
                  sa.Column('top_topic_counts', postgresql.JSONB, nullable=True))
    op.add_column('customer_text_features', 
                  sa.Column('sentiment_dist', postgresql.JSONB, nullable=True))


def downgrade():
    op.drop_column('customer_text_features', 'sentiment_dist')
    op.drop_column('customer_text_features', 'top_topic_counts')
