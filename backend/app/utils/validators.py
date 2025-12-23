"""
Validation Helpers
"""
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, date

from app.utils.errors import ValidationError


def validate_uuid(value: str, field_name: str = "id") -> uuid.UUID:
    """
    Validate and parse UUID string
    
    Args:
        value: UUID string to validate
        field_name: Name of field for error message
        
    Returns:
        Parsed UUID object
        
    Raises:
        ValidationError: If UUID is invalid
    """
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValidationError(
            f"Invalid {field_name} format",
            details={field_name: "Must be a valid UUID"}
        )


def validate_required_fields(
    data: Dict[str, Any], 
    required_fields: List[str]
) -> None:
    """
    Validate that required fields are present
    
    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        
    Raises:
        ValidationError: If any required field is missing
    """
    missing = [field for field in required_fields if field not in data or data[field] is None]
    
    if missing:
        raise ValidationError(
            "Missing required fields",
            details={field: "This field is required" for field in missing}
        )


def validate_enum(
    value: str, 
    valid_values: List[str], 
    field_name: str
) -> str:
    """
    Validate that value is in list of valid values
    
    Args:
        value: Value to validate
        valid_values: List of valid values
        field_name: Name of field for error message
        
    Returns:
        Validated value
        
    Raises:
        ValidationError: If value is not in valid values
    """
    if value not in valid_values:
        raise ValidationError(
            f"Invalid {field_name}",
            details={field_name: f"Must be one of: {', '.join(valid_values)}"}
        )
    return value


def validate_date_string(value: str, field_name: str = "date") -> date:
    """
    Validate and parse date string (YYYY-MM-DD)
    
    Args:
        value: Date string to validate
        field_name: Name of field for error message
        
    Returns:
        Parsed date object
        
    Raises:
        ValidationError: If date format is invalid
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValidationError(
            f"Invalid {field_name} format",
            details={field_name: "Must be in YYYY-MM-DD format"}
        )


def validate_pagination(
    page: Optional[int] = None, 
    limit: Optional[int] = None,
    max_limit: int = 100
) -> tuple:
    """
    Validate pagination parameters
    
    Args:
        page: Page number (1-indexed)
        limit: Items per page
        max_limit: Maximum allowed limit
        
    Returns:
        Tuple of (offset, limit)
    """
    page = page or 1
    limit = limit or 20
    
    if page < 1:
        page = 1
    
    if limit < 1:
        limit = 20
    elif limit > max_limit:
        limit = max_limit
    
    offset = (page - 1) * limit
    
    return offset, limit


def validate_score_range(
    value: float, 
    min_val: float = 0.0, 
    max_val: float = 1.0,
    field_name: str = "score"
) -> float:
    """
    Validate that score is within range
    
    Args:
        value: Score value
        min_val: Minimum value
        max_val: Maximum value
        field_name: Name of field for error message
        
    Returns:
        Validated score
        
    Raises:
        ValidationError: If score is out of range
    """
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValidationError(
            f"Invalid {field_name}",
            details={field_name: "Must be a number"}
        )
    
    if value < min_val or value > max_val:
        raise ValidationError(
            f"Invalid {field_name} range",
            details={field_name: f"Must be between {min_val} and {max_val}"}
        )
    
    return value
