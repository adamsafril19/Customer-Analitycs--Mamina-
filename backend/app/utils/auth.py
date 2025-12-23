"""
Authentication Helpers
"""
import hashlib
import os
from functools import wraps
from typing import Callable
from flask import current_app
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from app.utils.errors import UnauthorizedError


def hash_phone_number(phone: str, salt: str = None) -> str:
    """
    Hash phone number for privacy
    
    Args:
        phone: Raw phone number
        salt: Salt for hashing (defaults to config)
        
    Returns:
        Hashed phone number
    """
    if salt is None:
        salt = current_app.config.get("PHONE_HASH_SALT", "default-salt")
    
    # Normalize phone number
    phone = phone.strip().replace(" ", "").replace("-", "")
    
    # Hash with salt
    salted = f"{salt}{phone}"
    return hashlib.sha256(salted.encode()).hexdigest()


def hash_external_id(external_id: str, salt: str = None) -> str:
    """
    Hash external identifier for privacy
    
    Args:
        external_id: Raw external ID
        salt: Salt for hashing (defaults to config)
        
    Returns:
        Hashed external ID
    """
    if salt is None:
        salt = current_app.config.get("PHONE_HASH_SALT", "default-salt")
    
    salted = f"{salt}{external_id}"
    return hashlib.sha256(salted.encode()).hexdigest()


def admin_required(fn: Callable) -> Callable:
    """
    Decorator to require admin role for endpoint
    
    Usage:
        @admin_required
        def admin_only_endpoint():
            ...
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        
        if claims.get("role") != "admin":
            raise UnauthorizedError("Admin access required")
        
        return fn(*args, **kwargs)
    
    return wrapper


def operator_required(fn: Callable) -> Callable:
    """
    Decorator to require operator or admin role for endpoint
    
    Usage:
        @operator_required
        def operator_endpoint():
            ...
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        
        if claims.get("role") not in ["admin", "operator"]:
            raise UnauthorizedError("Operator access required")
        
        return fn(*args, **kwargs)
    
    return wrapper
