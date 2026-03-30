"""add_ml_model_registry

Revision ID: 022_ml_model_registry
Revises: 021_embedding_registry
Create Date: 2026-01-16

Add ml_model_registry table for first-class ML model identity.
"""
from alembic import op
from sqlalchemy import text

revision = '022_ml_model_registry'
down_revision = '021_embedding_registry'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Create ml_model_registry table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ml_model_registry (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            model_name VARCHAR(100) NOT NULL DEFAULT 'churn_model',
            model_version VARCHAR(50) NOT NULL,
            model_hash VARCHAR(64) NOT NULL UNIQUE,
            feature_schema_hash VARCHAR(64) NOT NULL,
            feature_names JSONB,
            expected_feature_count INTEGER NOT NULL,
            trained_on_embedding_model_hash VARCHAR(50),
            trained_on_link_status VARCHAR(50) DEFAULT 'verified',
            training_data_count INTEGER,
            training_date TIMESTAMP,
            shap_explainer_hash VARCHAR(64),
            is_active BOOLEAN DEFAULT FALSE,
            registered_at TIMESTAMP DEFAULT NOW(),
            notes TEXT
        )
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_ml_registry_hash ON ml_model_registry(model_hash)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_ml_registry_active 
        ON ml_model_registry(is_active) WHERE is_active = true
    """))
    
    # Register default model as active
    conn.execute(text("""
        INSERT INTO ml_model_registry 
        (model_name, model_version, model_hash, feature_schema_hash, expected_feature_count, is_active, notes)
        VALUES (
            'churn_model',
            'v1.0.0',
            'initial_v1',
            'initial_schema',
            9,
            true,
            'Initial model registration - update when model is actually loaded'
        )
        ON CONFLICT (model_hash) DO NOTHING
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS ml_model_registry"))
