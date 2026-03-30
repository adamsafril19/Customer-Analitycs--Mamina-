"""drop_legacy_tables

Revision ID: 006_drop_legacy_tables
Revises: 005_ontology_refactor
Create Date: 2026-01-15

Drop legacy tables replaced by new ontology:
- customer_features (replaced by customer_numeric_features)
- customer_text_features (replaced by customer_text_signals + customer_text_semantics)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_drop_legacy_tables'
down_revision = '005_ontology_refactor'
branch_labels = None
depends_on = None


def upgrade():
    # Drop legacy tables
    op.drop_table('customer_text_features')
    op.drop_table('customer_features')


def downgrade():
    # Recreate customer_features
    op.create_table('customer_features',
        sa.Column('feature_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('r_score', sa.Float(), nullable=True),
        sa.Column('f_score', sa.Float(), nullable=True),
        sa.Column('m_score', sa.Float(), nullable=True),
        sa.Column('tenure_days', sa.Integer(), nullable=True),
        sa.Column('complaint_rate_30', sa.Float(), nullable=True),
        sa.Column('avg_msg_length_30', sa.Float(), nullable=True),
        sa.Column('response_delay_mean', sa.Float(), nullable=True),
        sa.Column('msg_count_7d', sa.Integer(), nullable=True),
        sa.Column('msg_volatility', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('feature_id')
    )
    
    # Recreate customer_text_features
    op.create_table('customer_text_features',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('msg_count_7d', sa.Integer(), nullable=True),
        sa.Column('msg_count_30d', sa.Integer(), nullable=True),
        sa.Column('avg_embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('complaint_rate_30d', sa.Float(), nullable=True),
        sa.Column('avg_msg_length_30d', sa.Float(), nullable=True),
        sa.Column('response_delay_mean', sa.Float(), nullable=True),
        sa.Column('msg_volatility', sa.Float(), nullable=True),
        sa.Column('embedding_count_30d', sa.Integer(), nullable=True),
        sa.Column('last_n_embedding_ids', postgresql.JSONB(), nullable=True),
        sa.Column('top_topic_counts', postgresql.JSONB(), nullable=True),
        sa.Column('sentiment_dist', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
