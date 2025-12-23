"""Initial migration - Create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('username', sa.String(80), unique=True, nullable=False, index=True),
        sa.Column('email', sa.String(120), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, default='operator'),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_login', sa.DateTime, nullable=True),
    )

    # Customers table
    op.create_table(
        'customers',
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('external_id', sa.String(256), unique=True, nullable=True, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('phone_hash', sa.String(256), unique=True, nullable=True, index=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('consent_given', sa.Boolean, default=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime, nullable=True),
    )

    # Transactions table
    op.create_table(
        'transactions',
        sa.Column('tx_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('customers.customer_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('tx_date', sa.DateTime, nullable=False, index=True),
        sa.Column('service_type', sa.String(100), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column('status', sa.String(20), nullable=False, default='completed'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Index for customer + date
    op.create_index('idx_tx_customer_date', 'transactions', ['customer_id', 'tx_date'])

    # Feedback Raw table
    op.create_table(
        'feedback_raw',
        sa.Column('msg_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('customers.customer_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('direction', sa.String(20), nullable=False),
        sa.Column('text', sa.Text, nullable=True),
        sa.Column('timestamp', sa.DateTime, nullable=False, index=True),
        sa.Column('raw_meta', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Feedback Clean table
    op.create_table(
        'feedback_clean',
        sa.Column('feedback_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('msg_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('feedback_raw.msg_id', ondelete='CASCADE'),
                  nullable=False, unique=True, index=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('customers.customer_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('sentiment_score', sa.Float, nullable=True),
        sa.Column('sentiment_label', sa.String(20), nullable=True),
        sa.Column('topic_labels', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('keywords_emotion', postgresql.JSONB, nullable=True),
        sa.Column('response_time_secs', sa.Integer, nullable=True),
        sa.Column('intensity_7d', sa.Integer, nullable=True),
        sa.Column('processed_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Customer Features table
    op.create_table(
        'customer_features',
        sa.Column('feature_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('customers.customer_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('as_of_date', sa.Date, nullable=False, index=True),
        sa.Column('r_score', sa.Float, nullable=True),
        sa.Column('f_score', sa.Float, nullable=True),
        sa.Column('m_score', sa.Float, nullable=True),
        sa.Column('tenure_days', sa.Integer, nullable=True),
        sa.Column('avg_sentiment_30', sa.Float, nullable=True),
        sa.Column('neg_msg_count_30', sa.Integer, nullable=True),
        sa.Column('avg_response_secs', sa.Float, nullable=True),
        sa.Column('intensity_7d', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Unique constraint for customer + date
    op.create_unique_constraint(
        'uq_customer_features_date', 
        'customer_features', 
        ['customer_id', 'as_of_date']
    )
    op.create_index('idx_features_customer_date', 'customer_features', ['customer_id', 'as_of_date'])

    # Churn Predictions table
    op.create_table(
        'churn_predictions',
        sa.Column('pred_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('customers.customer_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('churn_score', sa.Float, nullable=False),
        sa.Column('churn_label', sa.String(20), nullable=False),
        sa.Column('top_reasons', postgresql.JSONB, nullable=True),
        sa.Column('model_version', sa.String(50), nullable=False),
        sa.Column('as_of_date', sa.Date, nullable=False, index=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Indexes for predictions
    op.create_index('idx_pred_customer_date', 'churn_predictions', ['customer_id', 'as_of_date'])
    op.create_index('idx_pred_label', 'churn_predictions', ['churn_label'])
    op.create_index('idx_pred_score', 'churn_predictions', ['churn_score'])

    # Actions table
    op.create_table(
        'actions',
        sa.Column('action_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pred_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('churn_predictions.pred_id', ondelete='SET NULL'),
                  nullable=True, index=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('customers.customer_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('priority', sa.String(20), nullable=False, default='medium'),
        sa.Column('assigned_to', sa.String(120), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('due_date', sa.Date, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Indexes for actions
    op.create_index('idx_action_status', 'actions', ['status'])
    op.create_index('idx_action_priority', 'actions', ['priority'])
    op.create_index('idx_action_assigned', 'actions', ['assigned_to'])
    op.create_index('idx_action_due_date', 'actions', ['due_date'])


def downgrade() -> None:
    op.drop_table('actions')
    op.drop_table('churn_predictions')
    op.drop_table('customer_features')
    op.drop_table('feedback_clean')
    op.drop_table('feedback_raw')
    op.drop_table('transactions')
    op.drop_table('customers')
    op.drop_table('users')
