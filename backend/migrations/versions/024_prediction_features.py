"""
Migration: Add features_used and provenance columns to churn_predictions

EPISTEMOLOGICAL FIX:
Explainer should reference prediction artifacts, not reconstruct.
This stores the immutable feature snapshot at prediction time.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = '024_prediction_features'
down_revision = '023_shap_cache_schema_binding'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns to churn_predictions for immutable feature provenance
    op.add_column('churn_predictions', 
        sa.Column('features_used', JSONB, nullable=True,
                  comment='Immutable snapshot of features at prediction time')
    )
    op.add_column('churn_predictions',
        sa.Column('feature_as_of', sa.DateTime, nullable=True,
                  comment='Exact timestamp features were computed')
    )
    op.add_column('churn_predictions',
        sa.Column('feature_schema_hash', sa.String(64), nullable=True,
                  comment='Hash of feature schema at prediction time')
    )
    op.add_column('churn_predictions',
        sa.Column('model_hash', sa.String(32), nullable=True,
                  comment='Hash of model used for prediction')
    )
    
    # Index for feature_as_of for temporal queries
    op.create_index('idx_pred_feature_as_of', 'churn_predictions', ['feature_as_of'])


def downgrade():
    op.drop_index('idx_pred_feature_as_of', table_name='churn_predictions')
    op.drop_column('churn_predictions', 'model_hash')
    op.drop_column('churn_predictions', 'feature_schema_hash')
    op.drop_column('churn_predictions', 'feature_as_of')
    op.drop_column('churn_predictions', 'features_used')
