"""add_trusted_semantic_embeddings_view

Revision ID: 020_semantic_embeddings_view
Revises: 019_add_embedding_version
Create Date: 2026-01-16

Create view for trusted semantic embeddings access.
This ensures embeddings are only accessible via verified identity layer.
"""
from alembic import op
from sqlalchemy import text

revision = '020_semantic_embeddings_view'
down_revision = '019_add_embedding_version'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Create view: trusted_semantic_embeddings (verified only for ML)
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
    
    # Create view for dashboard (verified + probable)
    conn.execute(text("""
        CREATE OR REPLACE VIEW dashboard_semantic_embeddings AS
        SELECT 
            fl.customer_id,
            fl.link_id,
            fl.link_status,
            ff.embedding,
            ff.embedding_model_version,
            ff.processed_at
        FROM feedback_linked fl
        INNER JOIN feedback_features ff ON fl.link_id = ff.link_id
        WHERE fl.link_status IN ('verified', 'probable')
          AND ff.embedding IS NOT NULL
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("DROP VIEW IF EXISTS trusted_semantic_embeddings"))
    conn.execute(text("DROP VIEW IF EXISTS dashboard_semantic_embeddings"))
