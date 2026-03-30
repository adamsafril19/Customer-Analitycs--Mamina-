"""add_shap_cache_schema_binding

Revision ID: 023_shap_cache_schema_binding
Revises: 022_ml_model_registry
Create Date: 2026-01-16

Add schema binding columns to shap_cache table.
"""
from alembic import op
from sqlalchemy import text

revision = '023_shap_cache_schema_binding'
down_revision = '022_ml_model_registry'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Add new columns for schema binding and temporal safety
    conn.execute(text("""
        ALTER TABLE shap_cache
        ADD COLUMN IF NOT EXISTS shap_top JSONB,
        ADD COLUMN IF NOT EXISTS nearest_messages JSONB,
        ADD COLUMN IF NOT EXISTS feature_schema_hash VARCHAR(64),
        ADD COLUMN IF NOT EXISTS model_version VARCHAR(50),
        ADD COLUMN IF NOT EXISTS explanation_type VARCHAR(20),
        ADD COLUMN IF NOT EXISTS as_of TIMESTAMP
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("""
        ALTER TABLE shap_cache
        DROP COLUMN IF EXISTS shap_top,
        DROP COLUMN IF EXISTS nearest_messages,
        DROP COLUMN IF EXISTS feature_schema_hash,
        DROP COLUMN IF EXISTS model_version,
        DROP COLUMN IF EXISTS explanation_type,
        DROP COLUMN IF EXISTS as_of
    """))
