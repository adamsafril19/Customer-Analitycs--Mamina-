"""add_identity_constraint

Revision ID: 013_add_identity_constraint
Revises: 012_add_identity_resolution
Create Date: 2026-01-15

Add trigger to enforce:
feedback_features.customer_id MUST = feedback_linked.customer_id
"""
from alembic import op
from sqlalchemy import text

revision = '013_add_identity_constraint'
down_revision = '012_add_identity_resolution'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Create trigger function to validate customer_id consistency
    conn.execute(text("""
        CREATE OR REPLACE FUNCTION validate_feature_customer_id()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.link_id IS NOT NULL THEN
                IF NEW.customer_id != (
                    SELECT customer_id FROM feedback_linked WHERE link_id = NEW.link_id
                ) THEN
                    RAISE EXCEPTION 'customer_id mismatch: feedback_features.customer_id must match feedback_linked.customer_id';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    
    # Create trigger on feedback_features
    conn.execute(text("""
        DROP TRIGGER IF EXISTS trg_validate_feature_customer_id ON feedback_features;
        CREATE TRIGGER trg_validate_feature_customer_id
        BEFORE INSERT OR UPDATE ON feedback_features
        FOR EACH ROW
        EXECUTE FUNCTION validate_feature_customer_id();
    """))
    
    # Add check constraint for match_confidence range
    conn.execute(text("""
        ALTER TABLE feedback_linked
        ADD CONSTRAINT chk_match_confidence_range
        CHECK (match_confidence >= 0 AND match_confidence <= 1);
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("DROP TRIGGER IF EXISTS trg_validate_feature_customer_id ON feedback_features"))
    conn.execute(text("DROP FUNCTION IF EXISTS validate_feature_customer_id"))
    conn.execute(text("ALTER TABLE feedback_linked DROP CONSTRAINT IF EXISTS chk_match_confidence_range"))
