from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.core.security import (
    create_access_token, create_refresh_token, verify_refresh_token,
    verify_password, get_password_hash
)
from app.core.errors import AuthenticationError, ValidationError, NotFoundError
from app.db.user_database import UserDatabase
from app.models.user_models import User, UserSession
from app.schemas.user import UserLogin, UserRegister, TokenResponse
from app.core.config import settings
from app.services.email_service import email_service
from app.services.otp_service import OTPService
import secrets
import string
import asyncio

class AuthService:
    """Authentication service for handling user auth flows"""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_db = UserDatabase(db)
        self.otp_service = OTPService(db)
        self.settings = settings
    
    @staticmethod
    def generate_random_password(length: int = 32) -> str:
        """Generate a secure random password for OAuth users.
        
        This password is used when creating users via Google/OAuth providers.
        Users won't know this password - they authenticate via OAuth tokens.
        If they want password access later, they can use 'Forgot Password'.
        """
        # Use cryptographically secure random generator
        alphabet = string.ascii_letters + string.digits + string.punctuation
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def register_user(self, user_data: UserRegister) -> User:
        """Register a new user with email or phone number"""
        # Validate passwords match
        if user_data.password != user_data.confirm_password:
            raise ValidationError("Passwords do not match")
        
        # Validate that either email or phone is provided
        if not user_data.email and not user_data.phone_number:
            raise ValidationError("Either email or phone number is required")
        
        # Check if user already exists by email
        if user_data.email:
            existing_user = self.user_db.get_user_by_email(user_data.email)
            if existing_user:
                raise ValidationError("User with this email already exists")
        
        # Check if user already exists by phone
        if user_data.phone_number:
            existing_user = self.user_db.get_user_by_phone(user_data.phone_number)
            if existing_user:
                raise ValidationError("User with this phone number already exists")
        
        # Check if username is taken (if provided)
        if hasattr(user_data, 'username') and user_data.username:
            existing_username = self.db.query(User).filter(
                User.username == user_data.username
            ).first()
            if existing_username:
                raise ValidationError("Username is already taken")
        
        # Create new user using the updated create_user method
        user = self.user_db.create_user(user_data)
        
        # Send verification OTP based on user's signup method
        try:
            # Use the method the user originally signed up with
            if user.signup_method == "phone":
                self.otp_service.send_verification_otp(user, "sms")
            else:
                self.otp_service.send_verification_otp(user, "email")
        except Exception as e:
            print(f"Failed to send verification OTP: {str(e)}")
        
        return user
    
    def authenticate_user(self, login_data: UserLogin) -> User:
        """Authenticate user with email/phone and password"""
        # Determine identifier (email or phone)
        identifier = login_data.email if login_data.email else login_data.phone_number
        
        if not identifier:
            raise AuthenticationError("Email or phone number is required")
        
        user = self.user_db.authenticate_user(identifier, login_data.password)
        if not user:
            if login_data.email:
                raise AuthenticationError("Invalid email or password")
            else:
                raise AuthenticationError("Invalid phone number or password")
        
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")
        
        return user
    
    def create_user_session(
        self, 
        user: User, 
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_info: Optional[str] = None
    ) -> Tuple[str, str]:
        """Create user session and return access and refresh tokens"""
        # Create tokens
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)
        
        # Create session record
        session = UserSession(
            user_id=user.id,
            session_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info
        )
        
        self.db.add(session)
        self.db.commit()
        
        return access_token, refresh_token
    
    def login(self, login_data: UserLogin, **session_kwargs) -> TokenResponse:
        """Complete login flow"""
        # Authenticate user
        user = self.authenticate_user(login_data)
        
        # Create session
        access_token, refresh_token = self.create_user_session(user, **session_kwargs)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user
        )
    
    def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token"""
        # Verify refresh token
        user_id = verify_refresh_token(refresh_token)
        if not user_id:
            raise AuthenticationError("Invalid refresh token")
        
        # Get user session
        session = self.db.query(UserSession).filter(
            UserSession.refresh_token == refresh_token,
            UserSession.is_active == True
        ).first()
        
        if not session:
            raise AuthenticationError("Session not found or expired")
        
        # Check if session is expired
        if session.expires_at < datetime.utcnow():
            session.is_active = False
            self.db.commit()
            raise AuthenticationError("Session expired")
        
        # Get user
        user = self.user_db.get_user_by_id(int(user_id))
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")
        
        # Create new tokens
        new_access_token = create_access_token(subject=user.id)
        new_refresh_token = create_refresh_token(subject=user.id)
        
        # Update session
        session.session_token = new_access_token
        session.refresh_token = new_refresh_token
        session.expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        self.db.commit()
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    def logout(self, user_id: int, session_token: Optional[str] = None) -> bool:
        """Logout user by deactivating session(s)"""
        query = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        )
        
        if session_token:
            # Logout specific session
            query = query.filter(UserSession.session_token == session_token)
        
        sessions = query.all()
        
        for session in sessions:
            session.is_active = False
        
        self.db.commit()
        return len(sessions) > 0
    
    def logout_all_sessions(self, user_id: int) -> int:
        """Logout user from all sessions"""
        sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ).all()
        
        for session in sessions:
            session.is_active = False
        
        self.db.commit()
        return len(sessions)
    
    def change_password(
        self, 
        user_id: int, 
        current_password: str, 
        new_password: str
    ) -> bool:
        """Change user password"""
        user = self.user_db.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")
        
        # Update password
        user.hashed_password = get_password_hash(new_password)
        self.db.commit()
        
        # Send password changed notification
        try:
            asyncio.create_task(email_service.send_password_changed_notification(user))
        except Exception as e:
            print(f"Failed to send password changed notification: {str(e)}")
        
        # Logout from all sessions (force re-login)
        self.logout_all_sessions(user_id)
        
        return True
    
    def verify_email_otp(self, email: str, otp: str) -> bool:
        """Verify email using OTP."""
        user = self.user_db.get_user_by_email(email)
        if not user:
            raise NotFoundError("User not found")
        
        success, message = self.otp_service.verify_otp(user, otp)
        if not success:
            raise ValidationError(message)
        
        # Mark email as verified
        user.is_verified = True
        self.db.commit()

        # Send welcome email when verification succeeds
        try:
            if user.email:
                asyncio.create_task(email_service.send_welcome_email(user))
        except Exception as e:
            print(f"Failed to send welcome email: {str(e)}")
        
        return True

    def verify_phone_otp(self, phone_number: str, otp: str) -> bool:
        """Verify phone number using OTP."""
        user = self.user_db.get_user_by_phone(phone_number)
        if not user:
            raise NotFoundError("User not found")

        success, message = self.otp_service.verify_otp(user, otp)
        if not success:
            raise ValidationError(message)

        user.is_verified = True
        self.db.commit()
        return True
    
    def generate_password_reset_token(self, email: str) -> str:
        """Generate password reset token and send email."""
        user = self.user_db.get_user_by_email(email)
        if not user:
            # Don't reveal if email exists for security
            return "token_placeholder"
        
        if not user.is_active:
            # Don't reveal account status
            return "token_placeholder"
        
        # Generate secure token
        token = self._generate_secure_token(64)
        
        # Store token with expiry (15 minutes)
        user.password_reset_token = token
        user.password_reset_expires = datetime.utcnow() + timedelta(minutes=15)
        self.db.commit()
        
        # Send password reset email
        try:
            asyncio.create_task(email_service.send_password_reset(user, token))
        except Exception as e:
            print(f"Failed to send password reset email: {str(e)}")
        
        return token
    
    def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using reset token."""
        # Find user by token
        user = self.db.query(User).filter(
            User.password_reset_token == token,
            User.password_reset_expires > datetime.utcnow(),
            User.is_active == True
        ).first()
        
        if not user:
            raise ValidationError("Invalid or expired reset token")
        
        # Update password
        user.hashed_password = get_password_hash(new_password)
        
        # Clear reset token
        user.password_reset_token = None
        user.password_reset_expires = None
        
        self.db.commit()
        
        # Send password changed notification
        try:
            asyncio.create_task(email_service.send_password_changed_notification(user))
        except Exception as e:
            print(f"Failed to send password changed notification: {str(e)}")
        
        # Logout from all sessions (force re-login)
        self.logout_all_sessions(user.id)
        
        return True
    
    def request_password_reset(self, identifier: str) -> bool:
        """Request password reset OTP for user by email or phone."""
        # Try to find user by email or phone
        if "@" in identifier:
            user = self.user_db.get_user_by_email(identifier)
        else:
            user = self.user_db.get_user_by_phone(identifier)
        
        if not user:
            raise NotFoundError("User not found")
        
        if not user.is_active:
            raise ValidationError("Account is deactivated")
        
        # Send password reset OTP based on user's signup method
        if user.signup_method == "phone":
            success = self.otp_service.send_password_reset_otp(user, "sms")
        else:
            success = self.otp_service.send_password_reset_otp(user, "email")
        
        if not success:
            raise ValidationError("Failed to send password reset code")
        
        return True
    
    def reset_password_with_otp(self, identifier: str, otp: str, new_password: str) -> bool:
        """Reset password using OTP verification by email or phone."""
        # Try to find user by email or phone
        if "@" in identifier:
            user = self.user_db.get_user_by_email(identifier)
        else:
            user = self.user_db.get_user_by_phone(identifier)
        
        if not user:
            raise NotFoundError("User not found")
        
        # Verify OTP
        success, message = self.otp_service.verify_password_reset_otp(user, otp)
        if not success:
            raise ValidationError(message)
        
        # Update password
        user.hashed_password = get_password_hash(new_password)
        
        # Clear OTP after successful password reset
        self.otp_service.clear_otp(user)
        
        self.db.commit()
        
        # Send password changed notification
        try:
            asyncio.create_task(email_service.send_password_changed_notification(user))
        except Exception as e:
            print(f"Failed to send password changed notification: {str(e)}")
        
        # Logout from all sessions (force re-login)
        self.logout_all_sessions(user.id)
        
        return True
    
    def verify_otp(self, identifier: str, otp: str) -> bool:
        """Verify OTP using email or phone."""
        # Try to find user by email or phone
        if "@" in identifier:
            user = self.user_db.get_user_by_email(identifier)
        else:
            user = self.user_db.get_user_by_phone(identifier)
        
        if not user:
            raise NotFoundError("User not found")
        
        success, message = self.otp_service.verify_otp(user, otp)
        if not success:
            raise ValidationError(message)
        
        # Send welcome email after successful verification (if user has email)
        try:
            if user.email:
                asyncio.create_task(email_service.send_welcome_email(user))
        except Exception as e:
            print(f"Failed to send welcome email: {str(e)}")
        
        return True
    
    def resend_verification_otp(self, identifier: str) -> bool:
        """Resend verification OTP to user by email or phone."""
        # Try to find user by email or phone
        if "@" in identifier:
            user = self.user_db.get_user_by_email(identifier)
        else:
            user = self.user_db.get_user_by_phone(identifier)
        
        if not user:
            raise NotFoundError("User not found")
        
        # Resend verification OTP based on user's signup method
        if user.signup_method == "phone":
            success, message = self.otp_service.resend_otp(user, "sms")
        else:
            success, message = self.otp_service.resend_otp(user, "email")
        if not success:
            raise ValidationError(message)
        
        return True
    
    def get_otp_status(self, identifier: str) -> dict:
        """Get OTP status for user by email or phone."""
        # Try to find user by email or phone
        if "@" in identifier:
            user = self.user_db.get_user_by_email(identifier)
        else:
            user = self.user_db.get_user_by_phone(identifier)
        
        if not user:
            raise NotFoundError("User not found")
        
        return self.otp_service.get_otp_status(user)
    
    def get_active_sessions(self, user_id: int) -> list:
        """Get all active sessions for a user"""
        sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).all()
        
        return sessions
    
    def send_email_verification_link(self, email: str) -> bool:
        """Send email verification link to user (legacy token-based method)."""
        user = self.user_db.get_user_by_email(email)
        
        if not user:
            # Don't reveal if email exists for security
            return True
        
        if user.is_verified:
            return True  # Already verified
        
        # Generate verification token
        token = self._generate_secure_token(64)
        user.email_verification_token = token
        self.db.commit()
        
        # Send verification email
        try:
            asyncio.create_task(email_service.send_email_verification(user, token))
            return True
        except Exception as e:
            print(f"Failed to send email verification: {str(e)}")
            return False
    
    def _generate_secure_token(self, length: int = 32) -> str:
        """Generate a secure random token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

