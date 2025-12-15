"""
Mobile App Utilities

Helper functions for handling mobile vs web client differences.
"""
from typing import Optional
from app.core.config import settings


def get_redirect_uri(
    service: str,
    client_type: Optional[str] = None
) -> str:
    """
    Get the appropriate redirect URI based on client type.
    
    Args:
        service: The OAuth service ('google', 'google_calendar', 'spotify')
        client_type: Type of client ('mobile', 'web', 'ios', 'android')
                    If None, defaults to web
    
    Returns:
        Redirect URI string
    """
    is_mobile = client_type and client_type.lower() in ['mobile', 'ios', 'android']
    
    if service == 'google':
        if is_mobile and settings.GOOGLE_MOBILE_REDIRECT_URI:
            return settings.GOOGLE_MOBILE_REDIRECT_URI
        return settings.GOOGLE_REDIRECT_URI or "http://localhost:8000/auth/google/callback"
    
    elif service == 'google_calendar':
        if is_mobile and settings.GOOGLE_CALENDAR_MOBILE_REDIRECT_URI:
            return settings.GOOGLE_CALENDAR_MOBILE_REDIRECT_URI
        return settings.GOOGLE_CALENDAR_REDIRECT_URI or "http://localhost:8000/api/v1/calendar/google/callback"
    
    elif service == 'spotify':
        if is_mobile and settings.SPOTIFY_MOBILE_REDIRECT_URI:
            return settings.SPOTIFY_MOBILE_REDIRECT_URI
        return settings.SPOTIFY_REDIRECT_URI or "http://localhost:3000/auth/spotify/callback"
    
    else:
        raise ValueError(f"Unknown service: {service}")


def get_frontend_url(client_type: Optional[str] = None, path: str = "") -> str:
    """
    Get the appropriate frontend URL based on client type.
    
    Args:
        client_type: Type of client ('mobile', 'web', 'ios', 'android')
        path: Optional path to append (e.g., '/login', '/events/123')
    
    Returns:
        Frontend URL string with optional path
    """
    is_mobile = client_type and client_type.lower() in ['mobile', 'ios', 'android']
    
    if is_mobile and settings.MOBILE_APP_SCHEME:
        # Mobile deep link (e.g., myapp://login)
        base_url = settings.MOBILE_APP_SCHEME.rstrip('/')
        clean_path = path.lstrip('/')
        return f"{base_url}/{clean_path}" if clean_path else base_url
    else:
        # Web URL (e.g., http://localhost:3000/login)
        base_url = settings.FRONTEND_URL.rstrip('/')
        clean_path = path.lstrip('/')
        return f"{base_url}/{clean_path}" if clean_path else base_url


def is_mobile_client(user_agent: Optional[str] = None, client_type: Optional[str] = None) -> bool:
    """
    Determine if the client is a mobile device.
    
    Args:
        user_agent: HTTP User-Agent header
        client_type: Explicit client type if provided
    
    Returns:
        True if mobile, False otherwise
    """
    if client_type:
        return client_type.lower() in ['mobile', 'ios', 'android']
    
    if user_agent:
        user_agent_lower = user_agent.lower()
        mobile_indicators = [
            'android', 'iphone', 'ipad', 'ipod',
            'mobile', 'webos', 'blackberry', 'windows phone'
        ]
        return any(indicator in user_agent_lower for indicator in mobile_indicators)
    
    return False


def get_platform_specific_message(message: str, mobile_message: Optional[str] = None) -> dict:
    """
    Create a response with platform-specific messages.
    
    Args:
        message: Default/web message
        mobile_message: Optional mobile-specific message
    
    Returns:
        Dict with web and mobile messages
    """
    return {
        "web": message,
        "mobile": mobile_message or message
    }
