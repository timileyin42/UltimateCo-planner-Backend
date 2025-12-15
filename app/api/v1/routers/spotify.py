"""
Spotify OAuth integration router for user authentication.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import secrets

from app.core.deps import get_db, get_current_active_user
from app.core.errors import http_400_bad_request, http_404_not_found
from app.core.config import settings
from app.services.spotify_service import SpotifyService
from app.models.user_models import User

spotify_router = APIRouter()


class SpotifyTokenResponse(BaseModel):
    """Response model for Spotify token storage."""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"
    scope: str


class SpotifyUserProfile(BaseModel):
    """Spotify user profile information."""
    spotify_user_id: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    country: Optional[str] = None
    product: Optional[str] = None  # free, premium
    images: list = []


@spotify_router.get("/authorize")
async def authorize_spotify(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate Spotify OAuth authorization URL.
    Redirects user to Spotify to authorize the app.
    """
    try:
        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store state in session/cache associated with user
        # For now, we'll include user_id in the state (in production, use Redis/session)
        state_with_user = f"{current_user.id}:{state}"
        
        # Get redirect URI from settings
        redirect_uri = settings.SPOTIFY_REDIRECT_URI or f"{settings.FRONTEND_URL}/spotify/callback"
        
        spotify_service = SpotifyService(db)
        auth_url = spotify_service.get_authorization_url(state_with_user, redirect_uri)
        
        return {
            "authorization_url": auth_url,
            "state": state_with_user
        }
        
    except Exception as e:
        if "not configured" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Spotify integration is not configured on the server"
            )
        raise http_400_bad_request(f"Failed to generate authorization URL: {str(e)}")


@spotify_router.get("/callback")
async def spotify_callback(
    code: str = Query(..., description="Authorization code from Spotify"),
    state: str = Query(..., description="State token for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from Spotify"),
    db: Session = Depends(get_db)
):
    """
    Handle Spotify OAuth callback.
    Exchanges authorization code for access and refresh tokens.
    """
    if error:
        raise http_400_bad_request(f"Spotify authorization failed: {error}")
    
    try:
        # Extract user_id from state (in production, validate against stored state)
        try:
            user_id_str, state_token = state.split(":", 1)
            user_id = int(user_id_str)
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state parameter"
            )
        
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise http_404_not_found("User not found")
        
        # Exchange code for tokens
        redirect_uri = settings.SPOTIFY_REDIRECT_URI or f"{settings.FRONTEND_URL}/spotify/callback"
        
        spotify_service = SpotifyService(db)
        token_data = await spotify_service.exchange_code_for_token(code, redirect_uri)
        
        # Store tokens (you'll need to add spotify_access_token, spotify_refresh_token fields to User model)
        # For now, we'll return them to be stored on client side
        
        return SpotifyTokenResponse(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data.get("expires_in", 3600),
            token_type=token_data.get("token_type", "Bearer"),
            scope=token_data.get("scope", "")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise http_400_bad_request(f"Failed to exchange authorization code: {str(e)}")


class SpotifyRefreshRequest(BaseModel):
    refresh_token: str


@spotify_router.post("/refresh")
async def refresh_spotify_token(
    refresh_data: SpotifyRefreshRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Refresh Spotify access token using refresh token.
    """
    try:
        spotify_service = SpotifyService(db)
        token_data = await spotify_service.refresh_user_token(refresh_data.refresh_token)
        
        return {
            "access_token": token_data["access_token"],
            "expires_in": token_data.get("expires_in", 3600),
            "token_type": token_data.get("token_type", "Bearer"),
            "scope": token_data.get("scope", "")
        }
        
    except Exception as e:
        if "unauthorized" in str(e).lower() or "invalid" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        raise http_400_bad_request(f"Failed to refresh token: {str(e)}")


class CreateSpotifyPlaylistRequest(BaseModel):
    name: str
    description: Optional[str] = None
    public: bool = True
    event_id: Optional[int] = None


@spotify_router.post("/create-playlist")
async def create_spotify_playlist(
    playlist_data: CreateSpotifyPlaylistRequest,
    user_access_token: str = Query(..., description="User's Spotify access token"),
    spotify_user_id: str = Query(..., description="User's Spotify user ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new playlist directly on Spotify and optionally link it to an event.
    """
    try:
        spotify_service = SpotifyService(db)
        
        # Create playlist on Spotify
        spotify_playlist = await spotify_service.create_playlist(
            spotify_user_id,
            playlist_data.name,
            playlist_data.description,
            playlist_data.public,
            user_access_token
        )
        
        # If event_id provided, create internal playlist linked to Spotify
        if playlist_data.event_id:
            from app.services.creative_service import CreativeService
            creative_service = CreativeService(db)
            
            internal_playlist_data = {
                "title": playlist_data.name,
                "description": playlist_data.description,
                "provider": "spotify",
                "external_id": spotify_playlist["id"],
                "external_url": spotify_playlist.get("external_urls", {}).get("spotify"),
                "is_collaborative": True,
                "is_public": playlist_data.public
            }
            
            internal_playlist = creative_service.create_playlist(
                playlist_data.event_id,
                current_user.id,
                internal_playlist_data
            )
            
            return {
                "spotify_playlist": spotify_playlist,
                "internal_playlist_id": internal_playlist.id,
                "message": "Playlist created on Spotify and linked to event"
            }
        
        return {
            "spotify_playlist": spotify_playlist,
            "message": "Playlist created on Spotify"
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Spotify authentication"
            )
        raise http_400_bad_request(f"Failed to create Spotify playlist: {str(e)}")


@spotify_router.get("/connection-status")
async def get_spotify_connection_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Check if user has connected their Spotify account.
    In production, check if user has valid Spotify tokens stored.
    """
    # TODO: Check if user has spotify_access_token and spotify_refresh_token in database
    # For now, return placeholder
    return {
        "connected": False,
        "message": "Store Spotify tokens on client side or in user profile to persist connection"
    }
