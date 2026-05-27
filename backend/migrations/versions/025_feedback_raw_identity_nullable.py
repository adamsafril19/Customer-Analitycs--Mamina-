"""make legacy feedback_raw customer_id nullable

Revision ID: 025_feedback_raw_nullable
Revises: 024_prediction_features
Create Date: 2026-05-14

The current identity-resolution design stores customer linkage in
feedback_linked. feedback_raw may only contain phone_number, direction, text,
and timestamp. Older databases still have feedback_raw.customer_id from the
initial schema as NOT NULL, which breaks CSV WhatsApp imports.
"""
from alembic import op


revision = "025_feedback_raw_nullable"
down_revision = "024_prediction_features"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE feedback_raw ALTER COLUMN customer_id DROP NOT NULL")


def downgrade():
    op.execute("ALTER TABLE feedback_raw ALTER COLUMN customer_id SET NOT NULL")
