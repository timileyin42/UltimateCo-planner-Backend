from typing import Optional, Dict, Any
import httpx
from app.core.config import settings
from app.core.errors import AuthenticationError, ValidationError
from app.models.user_models import User
from app.services.user_service import UserService
from app.services.email_service import email_service
from app.services.auth_service import AuthService
from app.schemas.user import TokenResponse
from sqlalchemy.orm import Session
import secrets
import string

class GoogleOAuthService:
    """Service for Google OAuth authentication."""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db)
        self.auth_service = AuthService(db)
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = f"{settings.FRONTEND_URL}/auth/google/callback"
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Generate Google OAuth authorization URL."""
        if not state:
            state = self._generate_state()
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "openid email profile",
            "response_type": "code",
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"
    
    async def exchange_code_for_tokens(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access tokens."""
        token_url = "https://oauth2.googleapis.com/token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=data)
            
            if response.status_code != 200:
                raise AuthenticationError("Failed to exchange code for tokens")
            
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Google using access token."""
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(user_info_url, headers=headers)
            
            if response.status_code != 200:
                raise AuthenticationError("Failed to get user information from Google")
            
            return response.json()
    
    async def authenticate_or_create_user(
        self, 
        code: str, 
        state: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> TokenResponse:
        """Authenticate existing user or create new user from Google OAuth."""
        try:
            # Exchange code for tokens
            tokens = await self.exchange_code_for_tokens(code, state)
            access_token = tokens.get("access_token")
            
            if not access_token:
                raise AuthenticationError("No access token received from Google")
            
            # Get user info from Google
            google_user = await self.get_user_info(access_token)
            
            email = google_user.get("email")
            if not email:
                raise AuthenticationError("No email received from Google")
            
            # Check if user already exists
            existing_user = self.user_service.get_user_by_email(email)
            
            if existing_user:
                # User exists, authenticate them
                if not existing_user.is_active:
                    raise AuthenticationError("Account is deactivated")
                
                # Update user info from Google if needed
                self._update_user_from_google(existing_user, google_user)
                
                # Create session and return tokens
                access_token, refresh_token = self.auth_service.create_user_session(
                    existing_user, ip_address, user_agent
                )
                
                return TokenResponse(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_type="bearer",
                    expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
                )
            else:
                # Create new user
                new_user = self._create_user_from_google(google_user)
                
                # Create session and return tokens
                access_token, refresh_token = self.auth_service.create_user_session(
                    new_user, ip_address, user_agent
                )
                
                return TokenResponse(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_type="bearer",
                    expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
                )
                
        except Exception as e:
            if isinstance(e, (AuthenticationError, ValidationError)):
                raise e
            else:
                raise AuthenticationError(f"Google OAuth authentication failed: {str(e)}")
    
    def _create_user_from_google(self, google_user: Dict[str, Any]) -> User:
        """Create a new user from Google user information."""
        email = google_user.get("email")
        name = google_user.get("name", "")
        given_name = google_user.get("given_name", "")
        family_name = google_user.get("family_name", "")
        picture = google_user.get("picture")
        
        # Generate a random password (user won't use it for Google OAuth)
        random_password = self._generate_random_password()
        
        # Create user
        user = User(
            email=email,
            hashed_password=self.auth_service.user_db.get_password_hash(random_password),
            full_name=name or f"{given_name} {family_name}".strip(),
            avatar_url=picture,
            is_verified=True,  # Google emails are pre-verified
            is_active=True
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        # Send welcome email asynchronously
        try:
            import asyncio
            asyncio.create_task(email_service.send_welcome_email(user))
        except Exception as e:
            print(f"Failed to send welcome email: {str(e)}")
        
        return user
    
    def _update_user_from_google(self, user: User, google_user: Dict[str, Any]) -> None:
        """Update existing user with latest Google information."""
        name = google_user.get("name")
        picture = google_user.get("picture")
        
        updated = False
        
        # Update name if it's different and user hasn't customized it
        if name and name != user.full_name:
            user.full_name = name
            updated = True
        
        # Update avatar if it's different
        if picture and picture != user.avatar_url:
            user.avatar_url = picture
            updated = True
        
        # Mark email as verified if not already
        if not user.is_verified:
            user.is_verified = True
            updated = True
        
        if updated:
            self.db.commit()
    
    def _generate_state(self) -> str:
        """Generate a random state parameter for OAuth security."""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    def _generate_random_password(self) -> str:
        """Generate a random password for Google OAuth users."""
        return ''.join(secrets.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(32))
    
    def verify_state(self, received_state: str, expected_state: str) -> bool:
        """Verify OAuth state parameter to prevent CSRF attacks."""
        return received_state == expected_state

class GoogleOAuthError(Exception):
    """Custom exception for Google OAuth errors."""
    pass