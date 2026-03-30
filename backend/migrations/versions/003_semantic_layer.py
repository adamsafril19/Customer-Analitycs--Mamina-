"""semantic_layer

Revision ID: 003_semantic_layer
Revises: 002_embedding_arch
Create Date: 2026-01-13

Add semantic layer tables and columns:
1. Create topics table
2. Add semantic columns to feedback_features
3. Convert embedding to vector type
4. Add fields to customer_text_features
5. Create model_versions table
6. Create shap_cache table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_semantic_layer'
down_revision = '002_embedding_arch'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create topics table
    op.create_table(
        'topics',
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), nullable=False, 
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('top_keywords', postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column('model_version', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('topic_id')
    )
    
    # 2. Add semantic columns to feedback_features
    op.add_column('feedback_features', 
                  sa.Column('sentiment_score', sa.Float(), nullable=True))
    op.add_column('feedback_features', 
                  sa.Column('sentiment_label', sa.String(20), nullable=True))
    op.add_column('feedback_features', 
                  sa.Column('topic_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('feedback_features', 
                  sa.Column('topic_confidence', sa.Float(), nullable=True))
    op.add_column('feedback_features', 
                  sa.Column('complaint_type', sa.String(50), nullable=True))
    op.add_column('feedback_features', 
                  sa.Column('keywords', postgresql.JSONB, nullable=True))
    
    # Add foreign key for topic_id
    op.create_foreign_key(
        'fk_feedback_features_topic',
        'feedback_features', 'topics',
        ['topic_id'], ['topic_id'],
        ondelete='SET NULL'
    )
    
    # 3. Convert embedding array to vector type
    # First add new vector column
    op.execute('ALTER TABLE feedback_features ADD COLUMN embedding_vec vector(384)')
    
    # Copy data from old embedding column if exists (array -> vector)
    op.execute('''
        UPDATE feedback_features 
        SET embedding_vec = embedding::vector 
        WHERE embedding IS NOT NULL
    ''')
    
    # Drop old embedding column and rename new one
    op.drop_column('feedback_features', 'embedding')
    op.execute('ALTER TABLE feedback_features RENAME COLUMN embedding_vec TO embedding')
    
    # 4. Add fields to customer_text_features
    op.add_column('customer_text_features',
                  sa.Column('embedding_count_30d', sa.Integer(), nullable=True, default=0))
    op.add_column('customer_text_features',
                  sa.Column('last_n_embedding_ids', postgresql.JSONB, nullable=True))
    
    # Convert avg_embedding to vector type
    op.execute('ALTER TABLE customer_text_features ADD COLUMN avg_embedding_vec vector(384)')
    op.execute('''
        UPDATE customer_text_features 
        SET avg_embedding_vec = avg_embedding::vector 
        WHERE avg_embedding IS NOT NULL
    ''')
    op.drop_column('customer_text_features', 'avg_embedding')
    op.execute('ALTER TABLE customer_text_features RENAME COLUMN avg_embedding_vec TO avg_embedding')
    
    # 5. Create model_versions table
    op.create_table(
        'model_versions',
        sa.Column('model_version', sa.String(50), nullable=False),
        sa.Column('model_path', sa.Text(), nullable=True),
        sa.Column('trained_at', sa.DateTime(), nullable=True),
        sa.Column('metrics', postgresql.JSONB, nullable=True),
        sa.Column('deployed', sa.Boolean(), default=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('model_version')
    )
    
    # 6. Create shap_cache table
    op.create_table(
        'shap_cache',
        sa.Column('pred_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('shap_top', postgresql.JSONB, nullable=True),
        sa.Column('nearest_messages', postgresql.JSONB, nullable=True),
        sa.Column('computed_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('explainer_version', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['pred_id'], ['churn_predictions.pred_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('pred_id')
    )


def downgrade():
    # Drop shap_cache
    op.drop_table('shap_cache')
    
    # Drop model_versions
    op.drop_table('model_versions')
    
    # Remove fields from customer_text_features
    op.drop_column('customer_text_features', 'embedding_count_30d')
    op.drop_column('customer_text_features', 'last_n_embedding_ids')
    
    # Revert embedding columns (vector -> array) - simplified, may need data migration
    op.execute('ALTER TABLE customer_text_features ADD COLUMN avg_embedding_arr float[]')
    op.drop_column('customer_text_features', 'avg_embedding')
    op.execute('ALTER TABLE customer_text_features RENAME COLUMN avg_embedding_arr TO avg_embedding')
    
    op.execute('ALTER TABLE feedback_features ADD COLUMN embedding_arr float[]')
    op.drop_column('feedback_features', 'embedding')
    op.execute('ALTER TABLE feedback_features RENAME COLUMN embedding_arr TO embedding')
    
    # Remove semantic columns from feedback_features
    op.drop_constraint('fk_feedback_features_topic', 'feedback_features', type_='foreignkey')
    op.drop_column('feedback_features', 'keywords')
    op.drop_column('feedback_features', 'complaint_type')
    op.drop_column('feedback_features', 'topic_confidence')
    op.drop_column('feedback_features', 'topic_id')
    op.drop_column('feedback_features', 'sentiment_label')
    op.drop_column('feedback_features', 'sentiment_score')
    
    # Drop topics table
    op.drop_table('topics')
