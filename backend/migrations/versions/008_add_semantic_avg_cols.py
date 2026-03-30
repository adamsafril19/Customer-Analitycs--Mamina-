"""add_semantic_avg_cols

Revision ID: 008_add_semantic_avg_cols
Revises: 007_drop_semantic_cols
Create Date: 2026-01-15

Add avg columns to customer_text_semantics:
- avg_sentiment_score (from feedback_features.sentiment_score)
- avg_topic_confidence (from feedback_features.topic_confidence)
"""
from alembic import op
import sqlalchemy as sa

revision = '008_add_semantic_avg_cols'
down_revision = '007_drop_semantic_cols'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('customer_text_semantics', 
                  sa.Column('avg_sentiment_score', sa.Float(), nullable=True))
    op.add_column('customer_text_semantics', 
                  sa.Column('avg_topic_confidence', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('customer_text_semantics', 'avg_sentiment_score')
    op.drop_column('customer_text_semantics', 'avg_topic_confidence')
