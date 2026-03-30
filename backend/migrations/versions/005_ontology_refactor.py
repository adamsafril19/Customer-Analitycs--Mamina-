"""ontology_refactor

Revision ID: 005_ontology_refactor
Revises: 004_milestone2_text_features
Create Date: 2026-01-15

Refactor data ontology:
- Rename customer_features -> customer_numeric_features (RFM only)
- Rename customer_text_features -> customer_text_signals (behavioral only)
- Create customer_text_semantics (dashboard only)
- Drop columns that don't belong in each table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_ontology_refactor'
down_revision = '004_milestone2_text_features'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create customer_numeric_features table (RFM only)
    op.create_table('customer_numeric_features',
        sa.Column('feature_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('r_score', sa.Float(), nullable=True),
        sa.Column('f_score', sa.Float(), nullable=True),
        sa.Column('m_score', sa.Float(), nullable=True),
        sa.Column('tenure_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('feature_id')
    )
    op.create_index('idx_numeric_features_customer_date', 'customer_numeric_features', 
                    ['customer_id', 'as_of_date'], unique=False)
    op.create_unique_constraint('uq_numeric_features_date', 'customer_numeric_features', 
                                ['customer_id', 'as_of_date'])
    
    # 2. Create customer_text_signals table (behavioral only)
    op.create_table('customer_text_signals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('msg_count_7d', sa.Integer(), nullable=True),
        sa.Column('msg_count_30d', sa.Integer(), nullable=True),
        sa.Column('msg_volatility', sa.Float(), nullable=True),
        sa.Column('avg_msg_length_30d', sa.Float(), nullable=True),
        sa.Column('complaint_rate_30d', sa.Float(), nullable=True),
        sa.Column('response_delay_mean', sa.Float(), nullable=True),
        sa.Column('avg_embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('embedding_count_30d', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_text_signals_customer_date', 'customer_text_signals', 
                    ['customer_id', 'as_of_date'], unique=False)
    op.create_unique_constraint('uq_text_signals_date', 'customer_text_signals', 
                                ['customer_id', 'as_of_date'])
    
    # Convert to vector type
    op.execute("""
        ALTER TABLE customer_text_signals 
        ALTER COLUMN avg_embedding TYPE vector(384) 
        USING avg_embedding::vector(384)
    """)
    
    # 3. Create customer_text_semantics table (dashboard only)
    op.create_table('customer_text_semantics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('top_topic_counts', postgresql.JSONB(), nullable=True),
        sa.Column('sentiment_dist', postgresql.JSONB(), nullable=True),
        sa.Column('top_keywords', postgresql.JSONB(), nullable=True),
        sa.Column('top_complaint_types', postgresql.JSONB(), nullable=True),
        sa.Column('last_n_msg_ids', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_text_semantics_customer_date', 'customer_text_semantics', 
                    ['customer_id', 'as_of_date'], unique=False)
    op.create_unique_constraint('uq_text_semantics_date', 'customer_text_semantics', 
                                ['customer_id', 'as_of_date'])
    
    # 4. Migrate data from old tables to new tables
    # Migrate RFM data from customer_features to customer_numeric_features
    op.execute("""
        INSERT INTO customer_numeric_features (feature_id, customer_id, as_of_date, r_score, f_score, m_score, tenure_days, created_at)
        SELECT gen_random_uuid(), customer_id, as_of_date, r_score, f_score, m_score, tenure_days, created_at
        FROM customer_features
        ON CONFLICT DO NOTHING
    """)
    
    # Migrate text signals from customer_text_features to customer_text_signals
    op.execute("""
        INSERT INTO customer_text_signals (id, customer_id, as_of_date, msg_count_7d, msg_count_30d, 
                                           msg_volatility, avg_msg_length_30d, complaint_rate_30d, 
                                           response_delay_mean, avg_embedding, embedding_count_30d, created_at)
        SELECT id, customer_id, as_of_date, msg_count_7d, msg_count_30d, 
               msg_volatility, avg_msg_length_30d, complaint_rate_30d, 
               response_delay_mean, avg_embedding, embedding_count_30d, created_at
        FROM customer_text_features
        ON CONFLICT DO NOTHING
    """)
    
    # Migrate semantic data from customer_text_features to customer_text_semantics
    op.execute("""
        INSERT INTO customer_text_semantics (id, customer_id, as_of_date, top_topic_counts, 
                                             sentiment_dist, created_at)
        SELECT gen_random_uuid(), customer_id, as_of_date, top_topic_counts, 
               sentiment_dist, created_at
        FROM customer_text_features
        WHERE top_topic_counts IS NOT NULL OR sentiment_dist IS NOT NULL
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    # Drop new tables
    op.drop_table('customer_text_semantics')
    op.drop_table('customer_text_signals')
    op.drop_table('customer_numeric_features')
