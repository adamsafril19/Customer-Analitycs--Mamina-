"""
Customer Schemas
"""
from marshmallow import Schema, fields, validate, post_load


class CustomerCreateSchema(Schema):
    """Schema for customer creation"""
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    phone = fields.String(validate=validate.Length(max=20))
    city = fields.String(validate=validate.Length(max=100))
    consent_given = fields.Boolean(load_default=False)


class CustomerUpdateSchema(Schema):
    """Schema for customer update"""
    name = fields.String(validate=validate.Length(min=1, max=200))
    city = fields.String(validate=validate.Length(max=100))
    is_active = fields.Boolean()
    consent_given = fields.Boolean()


class CustomerResponseSchema(Schema):
    """Schema for customer response"""
    customer_id = fields.UUID(dump_only=True)
    name = fields.String()
    city = fields.String()
    consent_given = fields.Boolean()
    is_active = fields.Boolean()
    created_at = fields.DateTime()
    last_seen_at = fields.DateTime()


class Customer360ResponseSchema(Schema):
    """Schema for Customer 360 view response"""
    customer = fields.Nested(CustomerResponseSchema)
    rfm_features = fields.Dict()
    sentiment_summary = fields.Dict()
    transaction_summary = fields.Dict()
    latest_prediction = fields.Dict()
