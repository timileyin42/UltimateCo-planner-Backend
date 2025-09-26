import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.google_oauth_service import GoogleOAuthService, GoogleOAuthError
from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.schemas.user import TokenResponse
from app.models.user_models import User
from app.core.errors import AuthenticationError, ValidationError
from app.tests.conftest import UserFactory
from sqlalchemy.orm import Session

class TestGoogleOAuthService:
    """Test cases for GoogleOAuthService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock(spec=Session)
        self.google_oauth = GoogleOAuthService(self.mock_db)
        self.google_oauth.client_id = "test_client_id"
        self.google_oauth.client_secret = "test_client_secret"
        self.google_oauth.redirect_uri = "http://localhost:3000/auth/google/callback"
    
    def test_get_authorization_url(self):
        """Test Google OAuth authorization URL generation."""
        url = self.google_oauth.get_authorization_url()
        
        assert "https://accounts.google.com/o/oauth2/v2/auth" in url
        assert "client_id=test_client_id" in url
        assert "redirect_uri=http://localhost:3000/auth/google/callback" in url
        assert "scope=openid+email+profile" in url
        assert "response_type=code" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url
    
    def test_get_authorization_url_with_state(self):
        """Test authorization URL generation with custom state."""
        custom_state = "custom_state_123"
        url = self.google_oauth.get_authorization_url(custom_state)
        
        assert f"state={custom_state}" in url
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_exchange_code_for_tokens_success(self, mock_client):
        """Test successful code to token exchange."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access_token_123",
            "refresh_token": "refresh_token_123",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        
        mock_client_instance = Mock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        result = await self.google_oauth.exchange_code_for_tokens("auth_code_123", "state_123")
        
        assert result["access_token"] == "access_token_123"
        assert result["refresh_token"] == "refresh_token_123"
        mock_client_instance.post.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_exchange_code_for_tokens_failure(self, mock_client):
        """Test failed code to token exchange."""
        mock_response = Mock()
        mock_response.status_code = 400
        
        mock_client_instance = Mock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        with pytest.raises(AuthenticationError, match="Failed to exchange code for tokens"):
            await self.google_oauth.exchange_code_for_tokens("invalid_code", "state_123")
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_get_user_info_success(self, mock_client):
        """Test successful user info retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "google_user_123",
            "email": "user@gmail.com",
            "name": "John Doe",
            "given_name": "John",
            "family_name": "Doe",
            "picture": "https://example.com/avatar.jpg",
            "verified_email": True
        }
        
        mock_client_instance = Mock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        result = await self.google_oauth.get_user_info("access_token_123")
        
        assert result["email"] == "user@gmail.com"
        assert result["name"] == "John Doe"
        assert result["picture"] == "https://example.com/avatar.jpg"
        mock_client_instance.get.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_get_user_info_failure(self, mock_client):
        """Test failed user info retrieval."""
        mock_response = Mock()
        mock_response.status_code = 401
        
        mock_client_instance = Mock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        with pytest.raises(AuthenticationError, match="Failed to get user information from Google"):
            await self.google_oauth.get_user_info("invalid_token")
    
    @pytest.mark.asyncio
    @patch.object(GoogleOAuthService, 'exchange_code_for_tokens')
    @patch.object(GoogleOAuthService, 'get_user_info')
    @patch.object(GoogleOAuthService, '_create_user_from_google')
    async def test_authenticate_or_create_user_new_user(self, mock_create_user, mock_get_user_info, mock_exchange_tokens):
        """Test authentication with new user creation."""
        # Mock token exchange
        mock_exchange_tokens.return_value = {"access_token": "access_token_123"}
        
        # Mock user info
        mock_get_user_info.return_value = {
            "email": "newuser@gmail.com",
            "name": "New User",
            "picture": "https://example.com/avatar.jpg"
        }
        
        # Mock user service to return None (user doesn't exist)
        mock_user_service = Mock(spec=UserService)
        mock_user_service.get_user_by_email.return_value = None
        self.google_oauth.user_service = mock_user_service
        
        # Mock new user creation
        mock_new_user = Mock(spec=User)
        mock_new_user.id = 1
        mock_new_user.email = "newuser@gmail.com"
        mock_create_user.return_value = mock_new_user
        
        # Mock auth service
        mock_auth_service = Mock(spec=AuthService)
        mock_auth_service.create_user_session.return_value = ("access_token", "refresh_token")
        self.google_oauth.auth_service = mock_auth_service
        
        result = await self.google_oauth.authenticate_or_create_user(
            "auth_code", "state", "127.0.0.1", "test-agent"
        )
        
        assert isinstance(result, TokenResponse)
        assert result.access_token == "access_token"
        assert result.refresh_token == "refresh_token"
        mock_create_user.assert_called_once()
        mock_auth_service.create_user_session.assert_called_once()
    
    @pytest.mark.asyncio
    @patch.object(GoogleOAuthService, 'exchange_code_for_tokens')
    @patch.object(GoogleOAuthService, 'get_user_info')
    @patch.object(GoogleOAuthService, '_update_user_from_google')
    async def test_authenticate_or_create_user_existing_user(self, mock_update_user, mock_get_user_info, mock_exchange_tokens):
        """Test authentication with existing user."""
        # Mock token exchange
        mock_exchange_tokens.return_value = {"access_token": "access_token_123"}
        
        # Mock user info
        mock_get_user_info.return_value = {
            "email": "existing@gmail.com",
            "name": "Existing User"
        }
        
        # Mock existing user
        mock_existing_user = Mock(spec=User)
        mock_existing_user.id = 1
        mock_existing_user.email = "existing@gmail.com"
        mock_existing_user.is_active = True
        
        # Mock user service to return existing user
        mock_user_service = Mock(spec=UserService)
        mock_user_service.get_user_by_email.return_value = mock_existing_user
        self.google_oauth.user_service = mock_user_service
        
        # Mock auth service
        mock_auth_service = Mock(spec=AuthService)
        mock_auth_service.create_user_session.return_value = ("access_token", "refresh_token")
        self.google_oauth.auth_service = mock_auth_service
        
        result = await self.google_oauth.authenticate_or_create_user(
            "auth_code", "state", "127.0.0.1", "test-agent"
        )
        
        assert isinstance(result, TokenResponse)
        mock_update_user.assert_called_once_with(mock_existing_user, mock_get_user_info.return_value)
        mock_auth_service.create_user_session.assert_called_once()
    
    @pytest.mark.asyncio
    @patch.object(GoogleOAuthService, 'exchange_code_for_tokens')
    @patch.object(GoogleOAuthService, 'get_user_info')
    async def test_authenticate_or_create_user_deactivated_account(self, mock_get_user_info, mock_exchange_tokens):
        """Test authentication with deactivated user account."""
        # Mock token exchange
        mock_exchange_tokens.return_value = {"access_token": "access_token_123"}
        
        # Mock user info
        mock_get_user_info.return_value = {"email": "deactivated@gmail.com"}
        
        # Mock deactivated user
        mock_user = Mock(spec=User)
        mock_user.is_active = False
        
        # Mock user service
        mock_user_service = Mock(spec=UserService)
        mock_user_service.get_user_by_email.return_value = mock_user
        self.google_oauth.user_service = mock_user_service
        
        with pytest.raises(AuthenticationError, match="Account is deactivated"):
            await self.google_oauth.authenticate_or_create_user(
                "auth_code", "state", "127.0.0.1", "test-agent"
            )
    
    @pytest.mark.asyncio
    @patch.object(GoogleOAuthService, 'exchange_code_for_tokens')
    async def test_authenticate_or_create_user_no_access_token(self, mock_exchange_tokens):
        """Test authentication when no access token is received."""
        mock_exchange_tokens.return_value = {}  # No access token
        
        with pytest.raises(AuthenticationError, match="No access token received from Google"):
            await self.google_oauth.authenticate_or_create_user(
                "auth_code", "state", "127.0.0.1", "test-agent"
            )
    
    @pytest.mark.asyncio
    @patch.object(GoogleOAuthService, 'exchange_code_for_tokens')
    @patch.object(GoogleOAuthService, 'get_user_info')
    async def test_authenticate_or_create_user_no_email(self, mock_get_user_info, mock_exchange_tokens):
        """Test authentication when no email is received from Google."""
        mock_exchange_tokens.return_value = {"access_token": "access_token_123"}
        mock_get_user_info.return_value = {}  # No email
        
        with pytest.raises(AuthenticationError, match="No email received from Google"):
            await self.google_oauth.authenticate_or_create_user(
                "auth_code", "state", "127.0.0.1", "test-agent"
            )
    
    @patch('app.services.google_oauth_service.asyncio.create_task')
    def test_create_user_from_google(self, mock_create_task):
        """Test creating a new user from Google data."""
        google_user_data = {
            "email": "newuser@gmail.com",
            "name": "John Doe",
            "given_name": "John",
            "family_name": "Doe",
            "picture": "https://example.com/avatar.jpg"
        }
        
        # Mock database operations
        mock_user = Mock(spec=User)
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        self.mock_db.refresh = Mock()
        
        # Mock auth service
        mock_auth_service = Mock(spec=AuthService)
        mock_auth_service.user_db.get_password_hash.return_value = "hashed_password"
        self.google_oauth.auth_service = mock_auth_service
        
        with patch('app.services.google_oauth_service.User', return_value=mock_user):
            result = self.google_oauth._create_user_from_google(google_user_data)
        
        assert result == mock_user
        self.mock_db.add.assert_called_once_with(mock_user)
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once_with(mock_user)
        mock_create_task.assert_called_once()  # Welcome email task
    
    def test_update_user_from_google(self):
        """Test updating existing user with Google data."""
        mock_user = Mock(spec=User)
        mock_user.full_name = "Old Name"
        mock_user.avatar_url = "old_avatar.jpg"
        mock_user.is_verified = False
        
        google_user_data = {
            "name": "New Name",
            "picture": "new_avatar.jpg"
        }
        
        self.mock_db.commit = Mock()
        
        self.google_oauth._update_user_from_google(mock_user, google_user_data)
        
        assert mock_user.full_name == "New Name"
        assert mock_user.avatar_url == "new_avatar.jpg"
        assert mock_user.is_verified is True
        self.mock_db.commit.assert_called_once()
    
    def test_update_user_from_google_no_changes(self):
        """Test updating user when no changes are needed."""
        mock_user = Mock(spec=User)
        mock_user.full_name = "Same Name"
        mock_user.avatar_url = "same_avatar.jpg"
        mock_user.is_verified = True
        
        google_user_data = {
            "name": "Same Name",
            "picture": "same_avatar.jpg"
        }
        
        self.mock_db.commit = Mock()
        
        self.google_oauth._update_user_from_google(mock_user, google_user_data)
        
        # No commit should be called if no changes
        self.mock_db.commit.assert_not_called()
    
    def test_generate_state(self):
        """Test state parameter generation."""
        state1 = self.google_oauth._generate_state()
        state2 = self.google_oauth._generate_state()
        
        assert len(state1) == 32
        assert len(state2) == 32
        assert state1 != state2  # Should be unique
        assert state1.isalnum()  # Should be alphanumeric
    
    def test_generate_random_password(self):
        """Test random password generation."""
        password1 = self.google_oauth._generate_random_password()
        password2 = self.google_oauth._generate_random_password()
        
        assert len(password1) == 32
        assert len(password2) == 32
        assert password1 != password2  # Should be unique
    
    def test_verify_state_valid(self):
        """Test state verification with valid state."""
        state = "valid_state_123"
        result = self.google_oauth.verify_state(state, state)
        assert result is True
    
    def test_verify_state_invalid(self):
        """Test state verification with invalid state."""
        received_state = "received_state"
        expected_state = "expected_state"
        result = self.google_oauth.verify_state(received_state, expected_state)
        assert result is False
    
    def test_google_oauth_error(self):
        """Test GoogleOAuthError exception."""
        error = GoogleOAuthError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)
    
    @pytest.mark.asyncio
    @patch.object(GoogleOAuthService, 'exchange_code_for_tokens')
    async def test_authenticate_or_create_user_general_exception(self, mock_exchange_tokens):
        """Test handling of general exceptions during authentication."""
        mock_exchange_tokens.side_effect = Exception("Unexpected error")
        
        with pytest.raises(AuthenticationError, match="Google OAuth authentication failed: Unexpected error"):
            await self.google_oauth.authenticate_or_create_user(
                "auth_code", "state", "127.0.0.1", "test-agent"
            )
    
    def test_initialization_with_settings(self):
        """Test service initialization with configuration."""
        # Test that the service initializes with proper settings
        assert self.google_oauth.client_id == "test_client_id"
        assert self.google_oauth.client_secret == "test_client_secret"
        assert "http://localhost:3000/auth/google/callback" in self.google_oauth.redirect_uri
        assert isinstance(self.google_oauth.user_service, UserService)
        assert isinstance(self.google_oauth.auth_service, AuthService)