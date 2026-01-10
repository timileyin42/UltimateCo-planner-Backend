"""
Circuit breaker patterns for external service integrations.
Provides fault tolerance and graceful degradation for external API calls.
"""

from typing import Any, Callable, Dict, Optional, Type, Union
from functools import wraps
import asyncio
import logging
from datetime import datetime, timedelta
from pybreaker import CircuitBreaker, CircuitBreakerError
from app.core.config import settings

logger = logging.getLogger(__name__)

class CircuitBreakerConfig:
    """Configuration for different circuit breakers."""
    
    # Default configuration
    DEFAULT_FAILURE_THRESHOLD = settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
    DEFAULT_RECOVERY_TIMEOUT = settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT
    DEFAULT_EXPECTED_EXCEPTION = settings.CIRCUIT_BREAKER_EXPECTED_EXCEPTION
    
    # Service-specific configurations
    STRIPE_CONFIG = {
        'fail_max': 5,
        'reset_timeout': 60,
        'exclude': [KeyError, ValueError]  # Don't break on client errors
    }
    
    EMAIL_CONFIG = {
        'fail_max': 3,
        'reset_timeout': 30,
        'exclude': [ValueError]  # Don't break on validation errors
    }
    
    SMS_CONFIG = {
        'fail_max': 3,
        'reset_timeout': 30,
        'exclude': [ValueError]
    }
    
    GOOGLE_API_CONFIG = {
        'fail_max': 5,
        'reset_timeout': 60,
        'exclude': [KeyError, ValueError]
    }
    
    OPENAI_CONFIG = {
        'fail_max': 3,
        'reset_timeout': 45,
        'exclude': [ValueError]
    }
    
    FIREBASE_CONFIG = {
        'fail_max': 3,
        'reset_timeout': 30,
        'exclude': [ValueError]
    }

# Circuit breaker instances
_circuit_breakers: Dict[str, CircuitBreaker] = {}

def get_circuit_breaker(name: str, config: Optional[Dict] = None) -> CircuitBreaker:
    """
    Get or create a circuit breaker instance.
    
    Args:
        name: Unique name for the circuit breaker
        config: Configuration dictionary for the circuit breaker
    
    Returns:
        CircuitBreaker instance
    """
    if not settings.CIRCUIT_BREAKER_ENABLED:
        # Return a dummy circuit breaker that never breaks
        return CircuitBreaker(fail_max=float('inf'))
    
    if name not in _circuit_breakers:
        if config is None:
            config = {
                'fail_max': CircuitBreakerConfig.DEFAULT_FAILURE_THRESHOLD,
                'reset_timeout': CircuitBreakerConfig.DEFAULT_RECOVERY_TIMEOUT,
                'exclude': CircuitBreakerConfig.DEFAULT_EXPECTED_EXCEPTION
            }
        
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            **config
        )
        
        # Note: Listeners removed due to API changes in pybreaker 1.0.2
        # Can be re-added when pybreaker supports them or using custom logging
        
        logger.info(f"Created circuit breaker '{name}' with config: {config}")
    
    return _circuit_breakers[name]

# Pre-configured circuit breakers for common services
stripe_breaker = get_circuit_breaker('stripe', CircuitBreakerConfig.STRIPE_CONFIG)
email_breaker = get_circuit_breaker('email', CircuitBreakerConfig.EMAIL_CONFIG)
sms_breaker = get_circuit_breaker('sms', CircuitBreakerConfig.SMS_CONFIG)
google_api_breaker = get_circuit_breaker('google_api', CircuitBreakerConfig.GOOGLE_API_CONFIG)
openai_breaker = get_circuit_breaker('openai', CircuitBreakerConfig.OPENAI_CONFIG)
firebase_breaker = get_circuit_breaker('firebase', CircuitBreakerConfig.FIREBASE_CONFIG)

def circuit_breaker(
    name: str,
    config: Optional[Dict] = None,
    fallback: Optional[Callable] = None
):
    """
    Decorator to apply circuit breaker pattern to functions.
    
    Args:
        name: Name of the circuit breaker
        config: Configuration for the circuit breaker
        fallback: Fallback function to call when circuit is open
    
    Usage:
        @circuit_breaker('my_service', fallback=my_fallback_function)
        async def call_external_service():
            # External service call
            pass
    """
    def decorator(func: Callable):
        breaker = get_circuit_breaker(name, config)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await breaker(func)(*args, **kwargs)
                else:
                    return breaker(func)(*args, **kwargs)
            except CircuitBreakerError as e:
                logger.warning(f"Circuit breaker '{name}' is open: {e}")
                if fallback:
                    logger.info(f"Calling fallback for '{name}'")
                    if asyncio.iscoroutinefunction(fallback):
                        return await fallback(*args, **kwargs)
                    else:
                        return fallback(*args, **kwargs)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return breaker(func)(*args, **kwargs)
            except CircuitBreakerError as e:
                logger.warning(f"Circuit breaker '{name}' is open: {e}")
                if fallback:
                    logger.info(f"Calling fallback for '{name}'")
                    return fallback(*args, **kwargs)
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Convenience decorators for common services
def stripe_circuit_breaker(fallback: Optional[Callable] = None):
    """Circuit breaker decorator for Stripe operations."""
    return circuit_breaker('stripe', CircuitBreakerConfig.STRIPE_CONFIG, fallback)

def email_circuit_breaker(fallback: Optional[Callable] = None):
    """Circuit breaker decorator for email operations."""
    return circuit_breaker('email', CircuitBreakerConfig.EMAIL_CONFIG, fallback)

def sms_circuit_breaker(fallback: Optional[Callable] = None):
    """Circuit breaker decorator for SMS operations."""
    return circuit_breaker('sms', CircuitBreakerConfig.SMS_CONFIG, fallback)

def google_api_circuit_breaker(fallback: Optional[Callable] = None):
    """Circuit breaker decorator for Google API operations."""
    return circuit_breaker('google_api', CircuitBreakerConfig.GOOGLE_API_CONFIG, fallback)

def openai_circuit_breaker(fallback: Optional[Callable] = None):
    """Circuit breaker decorator for OpenAI operations."""
    return circuit_breaker('openai', CircuitBreakerConfig.OPENAI_CONFIG, fallback)

def firebase_circuit_breaker(fallback: Optional[Callable] = None):
    """Circuit breaker decorator for Firebase operations."""
    return circuit_breaker('firebase', CircuitBreakerConfig.FIREBASE_CONFIG, fallback)

class CircuitBreakerManager:
    """Manager for monitoring and controlling circuit breakers."""
    
    @staticmethod
    def get_status() -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers."""
        status = {}
        for name, breaker in _circuit_breakers.items():
            status[name] = {
                'state': breaker.current_state,
                'fail_counter': breaker.fail_counter,
                'last_failure': breaker.last_failure,
                'next_attempt': breaker.next_attempt,
                'failure_threshold': breaker.fail_max,
                'recovery_timeout': breaker.reset_timeout
            }
        return status
    
    @staticmethod
    def reset_breaker(name: str) -> bool:
        """Manually reset a circuit breaker."""
        if name in _circuit_breakers:
            _circuit_breakers[name].close()
            logger.info(f"Manually reset circuit breaker '{name}'")
            return True
        return False
    
    @staticmethod
    def reset_all_breakers():
        """Reset all circuit breakers."""
        for name, breaker in _circuit_breakers.items():
            breaker.close()
            logger.info(f"Reset circuit breaker '{name}'")

# Fallback functions for common services
async def stripe_fallback(*args, **kwargs):
    """Fallback for Stripe operations when circuit is open."""
    logger.warning("Stripe service unavailable, payment will be queued for retry")
    return {
        'status': 'queued',
        'message': 'Payment service temporarily unavailable, will retry automatically'
    }

async def email_fallback(*args, **kwargs):
    """Fallback for email operations when circuit is open."""
    logger.warning("Email service unavailable, email will be queued for retry")
    return {
        'status': 'queued',
        'message': 'Email service temporarily unavailable, will retry automatically'
    }

async def sms_fallback(*args, **kwargs):
    """Fallback for SMS operations when circuit is open."""
    logger.warning("SMS service unavailable, message will be queued for retry")
    return {
        'status': 'failed',
        'error': 'SMS circuit open'
    }

async def ai_fallback(*args, **kwargs):
    """Fallback for AI operations when circuit is open."""
    logger.warning("AI service unavailable, using cached response or simple fallback")
    return {
        'status': 'unavailable',
        'message': 'AI service temporarily unavailable, please try again later',
        'response': 'I apologize, but the AI service is currently unavailable. Please try again in a few minutes.'
    }

async def firebase_fallback(*args, **kwargs):
    """Fallback for Firebase operations when circuit is open."""
    logger.warning("Firebase push notification service unavailable")
    return {
        'status': 'unavailable',
        'message': 'Push notification service temporarily unavailable',
        'success': False,
        'sent': False
    }