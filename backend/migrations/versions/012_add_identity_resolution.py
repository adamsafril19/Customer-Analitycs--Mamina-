"""add_identity_resolution_layer

Revision ID: 012_add_identity_resolution
Revises: 011_create_churn_labels
Create Date: 2026-01-15

Create proper identity resolution architecture:
1. Add phone_number to feedback_raw
2. Create feedback_linked table
3. Update feedback_features to use link_id
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = '012_add_identity_resolution'
down_revision = '011_create_churn_labels'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # 1. Add phone_number to feedback_raw
    conn.execute(text("""
        ALTER TABLE feedback_raw 
        ADD COLUMN IF NOT EXISTS phone_number VARCHAR(256)
    """))
    
    # 2. Create feedback_linked table
    op.create_table('feedback_linked',
        sa.Column('link_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('msg_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('match_confidence', sa.Float(), nullable=True),
        sa.Column('match_method', sa.String(50), nullable=True),
        sa.Column('linked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['msg_id'], ['feedback_raw.msg_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('link_id')
    )
    op.create_index('idx_feedback_linked_customer', 'feedback_linked', ['customer_id'])
    op.create_index('idx_feedback_linked_msg', 'feedback_linked', ['msg_id'], unique=True)
    
    # 3. Migrate existing data: create linked records from existing feedback_features
    conn.execute(text("""
        INSERT INTO feedback_linked (link_id, msg_id, customer_id, match_confidence, match_method, linked_at)
        SELECT 
            gen_random_uuid(),
            msg_id,
            customer_id,
            1.0,
            'legacy_migration',
            NOW()
        FROM feedback_features
        WHERE msg_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """))
    
    # 4. Add link_id to feedback_features
    conn.execute(text("""
        ALTER TABLE feedback_features 
        ADD COLUMN IF NOT EXISTS link_id UUID
    """))
    
    # 5. Update link_id in feedback_features
    conn.execute(text("""
        UPDATE feedback_features f
        SET link_id = l.link_id
        FROM feedback_linked l
        WHERE f.msg_id = l.msg_id
    """))
    
    # 6. Copy customer_id to phone_number in feedback_raw (placeholder - will be replaced with actual phone)
    conn.execute(text("""
        UPDATE feedback_raw 
        SET phone_number = COALESCE(
            (SELECT c.phone_hash FROM customers c WHERE c.customer_id = feedback_raw.customer_id),
            'unknown'
        )
        WHERE phone_number IS NULL
    """))


def downgrade():
    op.drop_table('feedback_linked')
