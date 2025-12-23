"""
Custom Error Classes
"""
from typing import Dict, Any, Optional


class APIError(Exception):
    """Base API Error"""
    
    def __init__(
        self, 
        message: str, 
        code: str = "API_ERROR",
        status_code: int = 500
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(Exception):
    """Validation Error"""
    
    def __init__(
        self, 
        message: str, 
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(Exception):
    """Resource Not Found Error"""
    
    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(self.message)


class UnauthorizedError(Exception):
    """Unauthorized Access Error"""
    
    def __init__(self, message: str = "Unauthorized access"):
        self.message = message
        super().__init__(self.message)


class ModelNotLoadedError(Exception):
    """ML Model Not Loaded Error"""
    
    def __init__(self, message: str = "ML model is not loaded"):
        self.message = message
        super().__init__(self.message)


class FeatureEngineeringError(Exception):
    """Feature Engineering Error"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
