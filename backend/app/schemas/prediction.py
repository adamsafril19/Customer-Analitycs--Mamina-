"""
Prediction Schemas
"""
from marshmallow import Schema, fields, validate


class TopReasonSchema(Schema):
    """Schema for top reason in prediction"""
    feature = fields.String()
    impact = fields.Float()
    value = fields.Float()
    description = fields.String()


class PredictionResponseSchema(Schema):
    """Schema for prediction response"""
    pred_id = fields.UUID(dump_only=True)
    customer_id = fields.UUID()
    customer_name = fields.String()
    churn_score = fields.Float()
    churn_label = fields.String()
    top_reasons = fields.List(fields.Nested(TopReasonSchema))
    model_version = fields.String()
    as_of_date = fields.Date()
    created_at = fields.DateTime()


class PredictionListResponseSchema(Schema):
    """Schema for prediction list response"""
    total = fields.Integer()
    predictions = fields.List(fields.Nested(PredictionResponseSchema))


class PredictionRequestSchema(Schema):
    """Schema for prediction request"""
    customer_id = fields.UUID(required=True)


class BatchPredictionRequestSchema(Schema):
    """Schema for batch prediction request"""
    customer_ids = fields.List(fields.UUID())


class ActionCreateSchema(Schema):
    """Schema for action creation"""
    customer_id = fields.UUID(required=True)
    pred_id = fields.UUID()
    action_type = fields.String(
        required=True,
        validate=validate.OneOf(["call", "promo", "visit", "email"])
    )
    priority = fields.String(
        load_default="medium",
        validate=validate.OneOf(["low", "medium", "high"])
    )
    assigned_to = fields.String(validate=validate.Length(max=120))
    due_date = fields.Date()
    notes = fields.String()


class ActionUpdateSchema(Schema):
    """Schema for action update"""
    status = fields.String(
        validate=validate.OneOf(["pending", "in_progress", "completed", "cancelled"])
    )
    priority = fields.String(
        validate=validate.OneOf(["low", "medium", "high"])
    )
    assigned_to = fields.String(validate=validate.Length(max=120))
    notes = fields.String()
    due_date = fields.Date()


class ActionResponseSchema(Schema):
    """Schema for action response"""
    action_id = fields.UUID(dump_only=True)
    pred_id = fields.UUID()
    customer_id = fields.UUID()
    customer_name = fields.String()
    action_type = fields.String()
    priority = fields.String()
    assigned_to = fields.String()
    status = fields.String()
    notes = fields.String()
    due_date = fields.Date()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
