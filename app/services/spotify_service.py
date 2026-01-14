"""
Spotify Web API integration service for playlist and track management.
"""
import base64
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user_models import User
from app.core.logger import get_logger

logger = get_logger(__name__)


class SpotifyService:
    """Service for Spotify Web API integration."""
    
    # Spotify API endpoints
    BASE_URL = "https://api.spotify.com/v1"
    AUTH_URL = "https://accounts.spotify.com/api/token"
    AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
    
    # OAuth scopes needed for playlist management
    SCOPES = [
        "playlist-read-private",
        "playlist-read-collaborative",
        "playlist-modify-public",
        "playlist-modify-private",
        "user-library-read",
        "user-read-email"
    ]
    
    def __init__(self, db: Session):
        self.db = db
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
    def _get_client_credentials(self) -> str:
        """Get base64 encoded client credentials for Spotify API."""
        if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Spotify integration is not configured"
            )
        
        credentials = f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return encoded
    
    async def _get_client_access_token(self) -> str:
        """
        Get access token using client credentials flow (for app-level access).
        This is used for searching tracks, getting track details, etc.
        """
        # Check if we have a valid token
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at:
                return self._access_token
        
        # Request new token
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.AUTH_URL,
                    headers={
                        "Authorization": f"Basic {self._get_client_credentials()}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    data={"grant_type": "client_credentials"}
                )
                
                if response.status_code != 200:
                    logger.error(f"Spotify auth failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Failed to authenticate with Spotify"
                    )
                
                data = response.json()
                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                
                return self._access_token
                
        except httpx.RequestError as e:
            logger.error(f"Spotify API request error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Spotify API"
            )
    
    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """
        Generate Spotify OAuth authorization URL for user authentication.
        Users need this to grant access to their Spotify account.
        """
        params = {
            "client_id": settings.SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.SCOPES),
            "state": state,
            "show_dialog": "false"
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.AUTHORIZE_URL}?{query_string}"
    
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.
        This is called after user authorizes the app.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.AUTH_URL,
                    headers={
                        "Authorization": f"Basic {self._get_client_credentials()}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to exchange authorization code"
                    )
                
                return response.json()
                
        except httpx.RequestError as e:
            logger.error(f"Token exchange error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Spotify API"
            )
    
    async def refresh_user_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh user's access token using refresh token."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.AUTH_URL,
                    headers={
                        "Authorization": f"Basic {self._get_client_credentials()}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Failed to refresh Spotify token"
                    )
                
                return response.json()
                
        except httpx.RequestError as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Spotify API"
            )
    
    async def search_tracks(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search for tracks on Spotify.
        Uses client credentials (doesn't require user auth).
        """
        access_token = await self._get_client_access_token()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/search",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={
                        "q": query,
                        "type": "track",
                        "limit": limit,
                        "offset": offset
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Spotify search failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Failed to search Spotify tracks"
                    )
                
                return response.json()
                
        except httpx.RequestError as e:
            logger.error(f"Spotify search error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Spotify API"
            )
    
    async def get_track(self, track_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific track."""
        access_token = await self._get_client_access_token()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/tracks/{track_id}",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code != 200:
                    logger.error(f"Get track failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Track not found on Spotify"
                    )
                
                return response.json()
                
        except httpx.RequestError as e:
            logger.error(f"Get track error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Spotify API"
            )
    
    async def get_playlist(
        self,
        playlist_id: str,
        user_access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get Spotify playlist details.
        If user_access_token is provided, uses user's token (for private playlists).
        Otherwise uses client credentials (public playlists only).
        """
        access_token = user_access_token or await self._get_client_access_token()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/playlists/{playlist_id}",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code != 200:
                    logger.error(f"Get playlist failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Playlist not found on Spotify"
                    )
                
                return response.json()
                
        except httpx.RequestError as e:
            logger.error(f"Get playlist error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Spotify API"
            )
    
    async def create_playlist(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        public: bool = True,
        user_access_token: str = None
    ) -> Dict[str, Any]:
        """
        Create a new playlist on Spotify for the user.
        Requires user's access token with playlist-modify scope.
        """
        if not user_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User Spotify authentication required to create playlists"
            )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/users/{user_id}/playlists",
                    headers={
                        "Authorization": f"Bearer {user_access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "name": name,
                        "description": description or "",
                        "public": public
                    }
                )
                
                if response.status_code not in [200, 201]:
                    logger.error(f"Create playlist failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to create playlist on Spotify"
                    )
                
                return response.json()
                
        except httpx.RequestError as e:
            logger.error(f"Create playlist error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Spotify API"
            )
    
    async def add_tracks_to_playlist(
        self,
        playlist_id: str,
        track_uris: List[str],
        user_access_token: str
    ) -> Dict[str, Any]:
        """
        Add tracks to a Spotify playlist.
        Requires user's access token with playlist-modify scope.
        """
        if not user_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User Spotify authentication required"
            )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/playlists/{playlist_id}/tracks",
                    headers={
                        "Authorization": f"Bearer {user_access_token}",
                        "Content-Type": "application/json"
                    },
                    json={"uris": track_uris}
                )
                
                if response.status_code not in [200, 201]:
                    logger.error(f"Add tracks failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to add tracks to Spotify playlist"
                    )
                
                return response.json()
                
        except httpx.RequestError as e:
            logger.error(f"Add tracks error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Spotify API"
            )
    
    def parse_spotify_track(self, track_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Spotify track data into our internal format."""
        artists = track_data.get("artists", [])
        artist_names = ", ".join([artist["name"] for artist in artists])
        
        album = track_data.get("album", {})
        
        return {
            "title": track_data.get("name"),
            "artist": artist_names,
            "album": album.get("name"),
            "duration_ms": track_data.get("duration_ms"),
            "duration_seconds": track_data.get("duration_ms", 0) // 1000,
            "spotify_id": track_data.get("id"),
            "spotify_uri": track_data.get("uri"),
            "preview_url": track_data.get("preview_url"),
            "external_url": track_data.get("external_urls", {}).get("spotify"),
            "album_art_url": album.get("images", [{}])[0].get("url") if album.get("images") else None,
            "explicit": track_data.get("explicit", False),
            "popularity": track_data.get("popularity", 0),
            "isrc": track_data.get("external_ids", {}).get("isrc")
        }
