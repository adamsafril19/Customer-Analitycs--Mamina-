"""
Authentication Endpoints

Handles:
- User login
- Token refresh
- User registration (admin only)
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt
)
from flasgger import swag_from

from app import db
from app.models.user import User
from app.utils.errors import ValidationError, UnauthorizedError
from app.utils.validators import validate_required_fields
from app.utils.auth import admin_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
@swag_from({
    "tags": ["Authentication"],
    "summary": "User login",
    "description": "Authenticate user and return JWT tokens",
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "example": "admin"},
                    "password": {"type": "string", "example": "password123"}
                },
                "required": ["username", "password"]
            }
        }
    ],
    "responses": {
        200: {
            "description": "Login successful",
            "schema": {
                "type": "object",
                "properties": {
                    "access_token": {"type": "string"},
                    "refresh_token": {"type": "string"},
                    "user": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string"},
                            "username": {"type": "string"},
                            "role": {"type": "string"}
                        }
                    }
                }
            }
        },
        401: {"description": "Invalid credentials"}
    }
})
def login():
    """
    User login endpoint
    
    Validates credentials and returns JWT tokens.
    """
    data = request.get_json()
    
    if not data:
        raise ValidationError("Request body is required")
    
    validate_required_fields(data, ["username", "password"])
    
    username = data["username"]
    password = data["password"]
    
    # Find user
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        raise UnauthorizedError("Invalid username or password")
    
    if not user.is_active:
        raise UnauthorizedError("Account is disabled")
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Create tokens with additional claims
    additional_claims = {
        "role": user.role,
        "email": user.email
    }
    
    access_token = create_access_token(
        identity=str(user.user_id),
        additional_claims=additional_claims
    )
    refresh_token = create_refresh_token(
        identity=str(user.user_id),
        additional_claims=additional_claims
    )
    
    current_app.logger.info(f"User {username} logged in successfully")
    
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "user_id": str(user.user_id),
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    })


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
@swag_from({
    "tags": ["Authentication"],
    "summary": "Refresh access token",
    "description": "Get new access token using refresh token",
    "security": [{"Bearer": []}],
    "responses": {
        200: {
            "description": "Token refreshed",
            "schema": {
                "type": "object",
                "properties": {
                    "access_token": {"type": "string"}
                }
            }
        },
        401: {"description": "Invalid or expired refresh token"}
    }
})
def refresh():
    """
    Refresh access token
    
    Uses refresh token to generate new access token.
    """
    identity = get_jwt_identity()
    claims = get_jwt()
    
    # Get user to ensure they still exist and are active
    user = User.query.get(identity)
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    
    additional_claims = {
        "role": user.role,
        "email": user.email
    }
    
    access_token = create_access_token(
        identity=identity,
        additional_claims=additional_claims
    )
    
    return jsonify({"access_token": access_token})


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Authentication"],
    "summary": "Get current user info",
    "description": "Get information about the currently authenticated user",
    "security": [{"Bearer": []}],
    "responses": {
        200: {
            "description": "User info",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "username": {"type": "string"},
                    "email": {"type": "string"},
                    "role": {"type": "string"}
                }
            }
        }
    }
})
def get_current_user():
    """Get current authenticated user info"""
    identity = get_jwt_identity()
    user = User.query.get(identity)
    
    if not user:
        raise UnauthorizedError("User not found")
    
    return jsonify(user.to_dict())


@auth_bp.route("/register", methods=["POST"])
@jwt_required()
@admin_required
@swag_from({
    "tags": ["Authentication"],
    "summary": "Register new user (admin only)",
    "description": "Create a new user account. Requires admin privileges.",
    "security": [{"Bearer": []}],
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "email": {"type": "string"},
                    "password": {"type": "string"},
                    "role": {"type": "string", "enum": ["admin", "operator", "viewer"]}
                },
                "required": ["username", "email", "password"]
            }
        }
    ],
    "responses": {
        201: {"description": "User created successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Admin access required"}
    }
})
def register_user():
    """
    Register new user (admin only)
    
    Creates a new user account with specified role.
    """
    data = request.get_json()
    
    if not data:
        raise ValidationError("Request body is required")
    
    validate_required_fields(data, ["username", "email", "password"])
    
    # Check if username or email already exists
    if User.query.filter_by(username=data["username"]).first():
        raise ValidationError("Username already exists", {"username": "Already taken"})
    
    if User.query.filter_by(email=data["email"]).first():
        raise ValidationError("Email already exists", {"email": "Already registered"})
    
    # Validate role
    role = data.get("role", "operator")
    if role not in ["admin", "operator", "viewer"]:
        raise ValidationError("Invalid role", {"role": "Must be admin, operator, or viewer"})
    
    # Create user
    user = User(
        username=data["username"],
        email=data["email"],
        role=role
    )
    user.set_password(data["password"])
    
    db.session.add(user)
    db.session.commit()
    
    current_app.logger.info(f"New user created: {user.username} with role {role}")
    
    return jsonify({
        "message": "User created successfully",
        "user": user.to_dict()
    }), 201
