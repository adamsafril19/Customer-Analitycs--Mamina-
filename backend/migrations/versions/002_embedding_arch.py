"""embedding_rearchitecture

Revision ID: 002_embedding_arch
Revises: 001_initial
Create Date: 2026-01-13

This migration transforms the database from sentiment-label-based 
to embedding-based ML features as per rearchitect.md.

Changes:
1. Enable pgvector extension
2. Create feedback_features table (replaces feedback_clean)
3. Create customer_text_features table
4. Update customer_features columns
5. Migrate data from feedback_clean to feedback_features
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_embedding_arch'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # 2. Create feedback_features table
    op.create_table(
        'feedback_features',
        sa.Column('feature_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('msg_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('embedding', sa.dialects.postgresql.ARRAY(sa.Float), nullable=True),  # Will hold 384 dims
        sa.Column('msg_length', sa.Integer(), nullable=True),
        sa.Column('num_exclamations', sa.Integer(), nullable=True, default=0),
        sa.Column('num_questions', sa.Integer(), nullable=True, default=0),
        sa.Column('has_complaint', sa.Boolean(), nullable=True, default=False),
        sa.Column('has_refund_request', sa.Boolean(), nullable=True, default=False),
        sa.Column('language_confidence', sa.Float(), nullable=True),
        sa.Column('response_time_secs', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['msg_id'], ['feedback_raw.msg_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('feature_id')
    )
    op.create_index('ix_feedback_features_customer_id', 'feedback_features', ['customer_id'])
    op.create_index('ix_feedback_features_msg_id', 'feedback_features', ['msg_id'], unique=True)
    
    # 3. Create customer_text_features table
    op.create_table(
        'customer_text_features',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('msg_count_7d', sa.Integer(), nullable=True, default=0),
        sa.Column('msg_count_30d', sa.Integer(), nullable=True, default=0),
        sa.Column('avg_embedding', sa.dialects.postgresql.ARRAY(sa.Float), nullable=True),
        sa.Column('complaint_rate_30d', sa.Float(), nullable=True, default=0.0),
        sa.Column('avg_msg_length_30d', sa.Float(), nullable=True, default=0.0),
        sa.Column('response_delay_mean', sa.Float(), nullable=True, default=0.0),
        sa.Column('msg_volatility', sa.Float(), nullable=True, default=0.0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'as_of_date', name='uq_customer_text_features_date')
    )
    op.create_index('ix_customer_text_features_customer_id', 'customer_text_features', ['customer_id'])
    op.create_index('idx_text_features_customer_date', 'customer_text_features', ['customer_id', 'as_of_date'])
    
    # 4. Migrate data from feedback_clean to feedback_features (basic data only)
    # Note: Embeddings will need to be computed separately
    op.execute('''
        INSERT INTO feedback_features (feature_id, msg_id, customer_id, response_time_secs, processed_at)
        SELECT feedback_id, msg_id, customer_id, response_time_secs, processed_at
        FROM feedback_clean
    ''')
    
    # 5. Update customer_features table - remove old columns, add new ones
    # Remove old sentiment columns
    op.drop_column('customer_features', 'avg_sentiment_30')
    op.drop_column('customer_features', 'neg_msg_count_30')
    op.drop_column('customer_features', 'avg_response_secs')
    op.drop_column('customer_features', 'intensity_7d')
    
    # Add new text signal columns
    op.add_column('customer_features', sa.Column('complaint_rate_30', sa.Float(), nullable=True, default=0.0))
    op.add_column('customer_features', sa.Column('avg_msg_length_30', sa.Float(), nullable=True, default=0.0))
    op.add_column('customer_features', sa.Column('response_delay_mean', sa.Float(), nullable=True, default=0.0))
    op.add_column('customer_features', sa.Column('msg_count_7d', sa.Integer(), nullable=True, default=0))
    op.add_column('customer_features', sa.Column('msg_volatility', sa.Float(), nullable=True, default=0.0))
    
    # 6. Drop feedback_clean table (after data migration)
    op.drop_table('feedback_clean')


def downgrade():
    # Recreate feedback_clean
    op.create_table(
        'feedback_clean',
        sa.Column('feedback_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('msg_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('sentiment_label', sa.String(20), nullable=True),
        sa.Column('topic_labels', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('keywords_emotion', postgresql.JSONB, nullable=True),
        sa.Column('response_time_secs', sa.Integer(), nullable=True),
        sa.Column('intensity_7d', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['msg_id'], ['feedback_raw.msg_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('feedback_id')
    )
    
    # Remove new columns from customer_features
    op.drop_column('customer_features', 'complaint_rate_30')
    op.drop_column('customer_features', 'avg_msg_length_30')
    op.drop_column('customer_features', 'response_delay_mean')
    op.drop_column('customer_features', 'msg_count_7d')
    op.drop_column('customer_features', 'msg_volatility')
    
    # Add back old columns
    op.add_column('customer_features', sa.Column('avg_sentiment_30', sa.Float(), nullable=True))
    op.add_column('customer_features', sa.Column('neg_msg_count_30', sa.Integer(), nullable=True))
    op.add_column('customer_features', sa.Column('avg_response_secs', sa.Float(), nullable=True))
    op.add_column('customer_features', sa.Column('intensity_7d', sa.Integer(), nullable=True))
    
    # Drop new tables
    op.drop_table('customer_text_features')
    op.drop_table('feedback_features')
    
    # Drop pgvector extension (optional - might affect other uses)
    # op.execute('DROP EXTENSION IF EXISTS vector')
