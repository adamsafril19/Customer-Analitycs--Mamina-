"""create_trusted_feedback_view

Revision ID: 018_trusted_feedback_view
Revises: 017_add_link_status
Create Date: 2026-01-16

Create database view for trusted feedback to prevent accidental bypass.
This enforces the identity resolution layer at database level.
"""
from alembic import op
from sqlalchemy import text

revision = '018_trusted_feedback_view'
down_revision = '017_add_link_status'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Create view: trusted_feedback_ml (only verified for ML)
    conn.execute(text("""
        CREATE OR REPLACE VIEW trusted_feedback_ml AS
        SELECT 
            fr.msg_id,
            fr.phone_number,
            fr.text,
            fr.timestamp,
            fr.direction,
            fl.link_id,
            fl.customer_id,
            fl.match_confidence,
            fl.link_status,
            ff.feature_id,
            ff.msg_length,
            ff.num_exclamations,
            ff.num_questions,
            ff.embedding,
            ff.processed_at
        FROM feedback_raw fr
        INNER JOIN feedback_linked fl ON fr.msg_id = fl.msg_id
        LEFT JOIN feedback_features ff ON fl.link_id = ff.link_id
        WHERE fl.link_status = 'verified'
    """))
    
    # Create view: trusted_feedback_dashboard (verified + probable)
    conn.execute(text("""
        CREATE OR REPLACE VIEW trusted_feedback_dashboard AS
        SELECT 
            fr.msg_id,
            fr.phone_number,
            fr.text,
            fr.timestamp,
            fr.direction,
            fl.link_id,
            fl.customer_id,
            fl.match_confidence,
            fl.link_status,
            ff.feature_id,
            ff.msg_length,
            ff.num_exclamations,
            ff.num_questions,
            ff.embedding,
            ff.processed_at
        FROM feedback_raw fr
        INNER JOIN feedback_linked fl ON fr.msg_id = fl.msg_id
        LEFT JOIN feedback_features ff ON fl.link_id = ff.link_id
        WHERE fl.link_status IN ('verified', 'probable')
    """))
    
    # Create view: real_customers (non-provisional for BI)
    conn.execute(text("""
        CREATE OR REPLACE VIEW real_customers AS
        SELECT *
        FROM customers
        WHERE is_provisional = FALSE OR is_provisional IS NULL
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("DROP VIEW IF EXISTS trusted_feedback_ml"))
    conn.execute(text("DROP VIEW IF EXISTS trusted_feedback_dashboard"))
    conn.execute(text("DROP VIEW IF EXISTS real_customers"))
