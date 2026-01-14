"""
Rate limiting middleware and utilities for the Ultimate Co-planner backend.
Provides configurable rate limiting for different endpoint types.
"""

from typing import Callable, Optional
from fastapi import Request, HTTPException, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import redis.asyncio as redis
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Redis connection for rate limiting
redis_client: Optional[redis.Redis] = None

async def get_redis_client() -> redis.Redis:
    """Get or create Redis client for rate limiting."""
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            await redis_client.ping()
            logger.info("Redis connection established for rate limiting")
        except Exception as e:
            logger.warning(f"Redis connection failed, falling back to in-memory: {e}")
            # Fallback to in-memory storage
            redis_client = None
    return redis_client

class RateLimitConfig:
    """Rate limit configurations for different endpoint types."""
    
    # Authentication endpoints (more restrictive)
    AUTH = settings.RATE_LIMIT_AUTH
    
    # General API endpoints
    API = settings.RATE_LIMIT_API
    
    # AI/ML endpoints (expensive operations)
    AI = settings.RATE_LIMIT_AI
    
    # Payment endpoints (critical operations)
    PAYMENTS = settings.RATE_LIMIT_PAYMENTS
    
    # File upload endpoints
    UPLOADS = settings.RATE_LIMIT_UPLOADS
    
    # Specific endpoint limits
    LOGIN = "5/minute"
    REGISTER = "3/minute"
    PASSWORD_RESET = "3/minute"
    EMAIL_VERIFICATION = "5/minute"
    OTP_REQUEST = "3/minute"
    
    # AI specific limits
    AI_CHAT = "10/minute"
    AI_ANALYSIS = "5/minute"
    
    # Payment specific limits
    PAYMENT_CREATE = "10/minute"
    SUBSCRIPTION_MANAGE = "20/minute"


def get_identifier(request: Request) -> str:
    """
    Get unique identifier for rate limiting.
    Uses user ID if authenticated, otherwise IP address.
    """
    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, 'user_id', None)
    if user_id:
        return f"user:{user_id}"
    
    # Fallback to IP address
    return get_remote_address(request)


# Create limiter instance with a sane default API-wide limit
limiter = Limiter(
    key_func=get_identifier,
    storage_uri=settings.REDIS_URL if settings.RATE_LIMIT_ENABLED else None,
    default_limits=[RateLimitConfig.API] if settings.RATE_LIMIT_ENABLED else []
)


# Custom rate limit exceeded handler
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded errors."""
    logger.warning(
        f"Rate limit exceeded for {get_identifier(request)} "
        f"on {request.url.path} - {exc.detail}"
    )
    
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please try again later.",
            "retry_after": exc.retry_after if hasattr(exc, 'retry_after') else 60
        }
    )

def create_rate_limit_decorator(limit: str, per_method: bool = False):
    """
    Create a rate limit decorator with the specified limit.
    
    Args:
        limit: Rate limit string (e.g., "5/minute")
        per_method: If True, apply limit per HTTP method
    """
    def decorator(func: Callable):
        if settings.RATE_LIMIT_ENABLED:
            return limiter.limit(limit, per_method=per_method)(func)
        return func
    return decorator

# Convenience decorators for common rate limits
auth_rate_limit = create_rate_limit_decorator(RateLimitConfig.AUTH)
api_rate_limit = create_rate_limit_decorator(RateLimitConfig.API)
ai_rate_limit = create_rate_limit_decorator(RateLimitConfig.AI)
payments_rate_limit = create_rate_limit_decorator(RateLimitConfig.PAYMENTS)
uploads_rate_limit = create_rate_limit_decorator(RateLimitConfig.UPLOADS)

# Specific endpoint decorators
login_rate_limit = create_rate_limit_decorator(RateLimitConfig.LOGIN)
register_rate_limit = create_rate_limit_decorator(RateLimitConfig.REGISTER)
password_reset_rate_limit = create_rate_limit_decorator(RateLimitConfig.PASSWORD_RESET)
email_verification_rate_limit = create_rate_limit_decorator(RateLimitConfig.EMAIL_VERIFICATION)
otp_rate_limit = create_rate_limit_decorator(RateLimitConfig.OTP_REQUEST)

# AI specific decorators
ai_chat_rate_limit = create_rate_limit_decorator(RateLimitConfig.AI_CHAT)
ai_analysis_rate_limit = create_rate_limit_decorator(RateLimitConfig.AI_ANALYSIS)

# Payment specific decorators
payment_create_rate_limit = create_rate_limit_decorator(RateLimitConfig.PAYMENT_CREATE)
subscription_rate_limit = create_rate_limit_decorator(RateLimitConfig.SUBSCRIPTION_MANAGE)

async def cleanup_redis():
    """Cleanup Redis connection on shutdown."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
        logger.info("Redis connection closed")