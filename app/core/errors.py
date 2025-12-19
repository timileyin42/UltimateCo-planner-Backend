from typing import Any, Dict, Optional
from fastapi import HTTPException, status

class PlanEtalException(Exception):
    """Base exception for Plan et al application"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class AuthenticationError(PlanEtalException):
    """Authentication related errors"""
    pass

class AuthorizationError(PlanEtalException):
    """Authorization related errors"""
    pass

class ValidationError(PlanEtalException):
    """Validation related errors"""
    pass

class NotFoundError(PlanEtalException):
    """Resource not found errors"""
    pass

class ConflictError(PlanEtalException):
    """Resource conflict errors"""
    pass

class PaymentError(PlanEtalException):
    """Payment processing errors"""
    pass

# HTTP Exception helpers
def http_400_bad_request(message: str = "Bad request") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message
    )

def http_401_unauthorized(message: str = "Unauthorized") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"}
    )

def http_403_forbidden(message: str = "Forbidden") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message
    )

def http_404_not_found(message: str = "Not found") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=message
    )

def http_409_conflict(message: str = "Conflict") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=message
    )

def http_422_unprocessable_entity(message: str = "Unprocessable entity") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=message
    )

def http_500_internal_server_error(message: str = "Internal server error") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=message
    )