"""cleanup_prediction_shap

Revision ID: 010_cleanup_prediction_shap
Revises: 009_add_raw_tx_signals
Create Date: 2026-01-15

Remove storytelling columns:
- churn_predictions.top_reasons
- shap_cache.nearest_messages
- Rename shap_cache.shap_top to shap_values
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '010_cleanup_prediction_shap'
down_revision = '009_add_raw_tx_signals'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Drop top_reasons from churn_predictions
    conn.execute(text("ALTER TABLE churn_predictions DROP COLUMN IF EXISTS top_reasons"))
    
    # Drop nearest_messages from shap_cache
    conn.execute(text("ALTER TABLE shap_cache DROP COLUMN IF EXISTS nearest_messages"))
    
    # Rename shap_top to shap_values
    conn.execute(text("ALTER TABLE shap_cache RENAME COLUMN shap_top TO shap_values"))


def downgrade():
    pass
