"""add_embedding_model_registry

Revision ID: 021_embedding_registry
Revises: 020_semantic_embeddings_view
Create Date: 2026-01-16

Add embedding_model_registry table for first-class model identity.
Update views to filter by active model hash.
"""
from alembic import op
from sqlalchemy import text

revision = '021_embedding_registry'
down_revision = '020_semantic_embeddings_view'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Create embedding_model_registry table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS embedding_model_registry (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            model_name VARCHAR(200) NOT NULL,
            model_version VARCHAR(100) NOT NULL,
            model_hash VARCHAR(50) NOT NULL UNIQUE,
            embedding_dim INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT FALSE,
            registered_at TIMESTAMP DEFAULT NOW(),
            notes TEXT
        )
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_embedding_registry_hash 
        ON embedding_model_registry(model_hash)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_embedding_registry_active 
        ON embedding_model_registry(is_active) WHERE is_active = true
    """))
    
    # Register default model as active
    conn.execute(text("""
        INSERT INTO embedding_model_registry 
        (model_name, model_version, model_hash, embedding_dim, is_active, notes)
        VALUES (
            'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
            'paraphrase-multilingual-MiniLM-L12-v2|384',
            'initial_v1',
            384,
            true,
            'Initial model registration'
        )
        ON CONFLICT (model_hash) DO NOTHING
    """))
    
    # Update trusted_semantic_embeddings to filter by active model
    conn.execute(text("""
        CREATE OR REPLACE VIEW trusted_semantic_embeddings AS
        SELECT 
            fl.customer_id,
            fl.link_id,
            fl.link_status,
            ff.embedding,
            ff.embedding_model_version,
            ff.processed_at
        FROM feedback_linked fl
        INNER JOIN feedback_features ff ON fl.link_id = ff.link_id
        WHERE fl.link_status = 'verified'
          AND ff.embedding IS NOT NULL
          AND (
              ff.embedding_model_version IS NULL 
              OR ff.embedding_model_version = (
                  SELECT model_version FROM embedding_model_registry WHERE is_active = true LIMIT 1
              )
          )
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS embedding_model_registry"))
    # Restore original view
    conn.execute(text("""
        CREATE OR REPLACE VIEW trusted_semantic_embeddings AS
        SELECT 
            fl.customer_id,
            fl.link_id,
            fl.link_status,
            ff.embedding,
            ff.embedding_model_version,
            ff.processed_at
        FROM feedback_linked fl
        INNER JOIN feedback_features ff ON fl.link_id = ff.link_id
        WHERE fl.link_status = 'verified'
          AND ff.embedding IS NOT NULL
    """))
