"""
Actions Endpoints

Handles:
- Create action for customer
- List actions
- Update action status
"""
from datetime import datetime, date
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from flasgger import swag_from

from app import db
from app.models.customer import Customer
from app.models.action import Action
from app.models.prediction import ChurnPrediction
from app.utils.errors import NotFoundError, ValidationError
from app.utils.validators import (
    validate_uuid, 
    validate_pagination, 
    validate_required_fields,
    validate_enum,
    validate_date_string
)

actions_bp = Blueprint("actions", __name__)


@actions_bp.route("/actions", methods=["POST"])
@jwt_required()
@swag_from({
    "tags": ["Actions"],
    "summary": "Create action",
    "description": "Create a follow-up action for a customer",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "pred_id": {"type": "string", "description": "Optional prediction ID"},
                    "action_type": {
                        "type": "string",
                        "enum": ["call", "promo", "visit", "email"]
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"]
                    },
                    "assigned_to": {"type": "string"},
                    "due_date": {"type": "string", "format": "date"},
                    "notes": {"type": "string"}
                },
                "required": ["customer_id", "action_type"]
            }
        }
    ],
    "responses": {
        201: {"description": "Action created"},
        400: {"description": "Validation error"},
        404: {"description": "Customer not found"}
    }
})
def create_action():
    """Create a new action for customer"""
    data = request.get_json()
    
    if not data:
        raise ValidationError("Request body is required")
    
    validate_required_fields(data, ["customer_id", "action_type"])
    
    # Validate customer
    customer_uuid = validate_uuid(data["customer_id"], "customer_id")
    customer = Customer.query.get(customer_uuid)
    if not customer:
        raise NotFoundError(f"Customer {data['customer_id']} not found")
    
    # Validate action_type
    validate_enum(
        data["action_type"], 
        Action.VALID_ACTION_TYPES, 
        "action_type"
    )
    
    # Validate priority if provided
    priority = data.get("priority", "medium")
    validate_enum(priority, Action.VALID_PRIORITIES, "priority")
    
    # Validate prediction if provided
    pred_id = None
    if data.get("pred_id"):
        pred_uuid = validate_uuid(data["pred_id"], "pred_id")
        prediction = ChurnPrediction.query.get(pred_uuid)
        if not prediction:
            raise NotFoundError(f"Prediction {data['pred_id']} not found")
        pred_id = pred_uuid
    
    # Parse due_date if provided
    due_date = None
    if data.get("due_date"):
        due_date = validate_date_string(data["due_date"], "due_date")
    
    # Create action
    action = Action(
        customer_id=customer_uuid,
        pred_id=pred_id,
        action_type=data["action_type"],
        priority=priority,
        assigned_to=data.get("assigned_to"),
        notes=data.get("notes"),
        due_date=due_date,
        status="pending"
    )
    
    db.session.add(action)
    db.session.commit()
    
    current_app.logger.info(
        f"Created action {action.action_id} for customer {customer_uuid}"
    )
    
    return jsonify(action.to_dict_with_customer()), 201


@actions_bp.route("/actions", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Actions"],
    "summary": "List actions",
    "description": "Get paginated list of actions with filters",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "status",
            "in": "query",
            "type": "string",
            "enum": ["pending", "in_progress", "completed", "cancelled"]
        },
        {
            "name": "priority",
            "in": "query",
            "type": "string",
            "enum": ["low", "medium", "high"]
        },
        {
            "name": "assigned_to",
            "in": "query",
            "type": "string"
        },
        {
            "name": "customer_id",
            "in": "query",
            "type": "string"
        },
        {
            "name": "limit",
            "in": "query",
            "type": "integer",
            "default": 20
        },
        {
            "name": "offset",
            "in": "query",
            "type": "integer",
            "default": 0
        }
    ],
    "responses": {
        200: {"description": "List of actions"}
    }
})
def list_actions():
    """List actions with filtering"""
    status = request.args.get("status")
    priority = request.args.get("priority")
    assigned_to = request.args.get("assigned_to")
    customer_id = request.args.get("customer_id")
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    
    offset, limit = validate_pagination(offset // limit + 1 if offset else 1, limit)
    
    query = Action.query
    
    if status:
        validate_enum(status, Action.VALID_STATUSES, "status")
        query = query.filter_by(status=status)
    
    if priority:
        validate_enum(priority, Action.VALID_PRIORITIES, "priority")
        query = query.filter_by(priority=priority)
    
    if assigned_to:
        query = query.filter_by(assigned_to=assigned_to)
    
    if customer_id:
        customer_uuid = validate_uuid(customer_id, "customer_id")
        query = query.filter_by(customer_id=customer_uuid)
    
    total = query.count()
    
    # Order by priority (high first) and due date
    priority_order = db.case(
        (Action.priority == "high", 1),
        (Action.priority == "medium", 2),
        (Action.priority == "low", 3),
        else_=4
    )
    
    actions = query.order_by(
        priority_order,
        Action.due_date.asc().nullslast()
    ).offset(offset).limit(limit).all()
    
    return jsonify({
        "total": total,
        "actions": [a.to_dict_with_customer() for a in actions]
    })


@actions_bp.route("/actions/<action_id>", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Actions"],
    "summary": "Get action details",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "action_id",
            "in": "path",
            "type": "string",
            "required": True
        }
    ],
    "responses": {
        200: {"description": "Action details"},
        404: {"description": "Action not found"}
    }
})
def get_action(action_id: str):
    """Get action details"""
    action_uuid = validate_uuid(action_id, "action_id")
    
    action = Action.query.get(action_uuid)
    if not action:
        raise NotFoundError(f"Action {action_id} not found")
    
    return jsonify(action.to_dict_with_customer())


@actions_bp.route("/actions/<action_id>", methods=["PATCH"])
@jwt_required()
@swag_from({
    "tags": ["Actions"],
    "summary": "Update action",
    "description": "Update action status, notes, or assignment",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "action_id",
            "in": "path",
            "type": "string",
            "required": True
        },
        {
            "name": "body",
            "in": "body",
            "schema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "cancelled"]
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"]
                    },
                    "assigned_to": {"type": "string"},
                    "notes": {"type": "string"},
                    "due_date": {"type": "string", "format": "date"}
                }
            }
        }
    ],
    "responses": {
        200: {"description": "Action updated"},
        404: {"description": "Action not found"}
    }
})
def update_action(action_id: str):
    """Update action"""
    action_uuid = validate_uuid(action_id, "action_id")
    
    action = Action.query.get(action_uuid)
    if not action:
        raise NotFoundError(f"Action {action_id} not found")
    
    data = request.get_json()
    if not data:
        raise ValidationError("Request body is required")
    
    # Update status
    if "status" in data:
        validate_enum(data["status"], Action.VALID_STATUSES, "status")
        action.status = data["status"]
    
    # Update priority
    if "priority" in data:
        validate_enum(data["priority"], Action.VALID_PRIORITIES, "priority")
        action.priority = data["priority"]
    
    # Update assigned_to
    if "assigned_to" in data:
        action.assigned_to = data["assigned_to"]
    
    # Update notes
    if "notes" in data:
        action.notes = data["notes"]
    
    # Update due_date
    if "due_date" in data:
        if data["due_date"]:
            action.due_date = validate_date_string(data["due_date"], "due_date")
        else:
            action.due_date = None
    
    db.session.commit()
    
    current_app.logger.info(f"Updated action {action_id}")
    
    return jsonify(action.to_dict_with_customer())


@actions_bp.route("/actions/<action_id>", methods=["DELETE"])
@jwt_required()
@swag_from({
    "tags": ["Actions"],
    "summary": "Delete action",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "action_id",
            "in": "path",
            "type": "string",
            "required": True
        }
    ],
    "responses": {
        200: {"description": "Action deleted"},
        404: {"description": "Action not found"}
    }
})
def delete_action(action_id: str):
    """Delete action"""
    action_uuid = validate_uuid(action_id, "action_id")
    
    action = Action.query.get(action_uuid)
    if not action:
        raise NotFoundError(f"Action {action_id} not found")
    
    db.session.delete(action)
    db.session.commit()
    
    current_app.logger.info(f"Deleted action {action_id}")
    
    return jsonify({
        "message": "Action deleted",
        "action_id": action_id
    })
