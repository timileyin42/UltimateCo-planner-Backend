from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.core.config import settings
from app.core.errors import (
    http_400_bad_request, http_401_unauthorized, http_409_conflict, http_404_not_found
)
from app.core.rate_limiter import create_rate_limit_decorator, RateLimitConfig
from app.services.auth_service import AuthService
from app.services.google_oauth_service import GoogleOAuthService
from app.services.email_service import email_service
from app.schemas.user import (
    UserLogin, UserRegister, UserResponse, TokenResponse, 
    TokenRefresh, PasswordReset, PasswordResetConfirm
)
from pydantic import BaseModel, Field, model_validator
from app.models.user_models import User
from app.models.user_models import UserSession
from typing import Optional
import asyncio
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# OTP-related models
class OTPVerification(BaseModel):
    email: str = Field(..., description="User's email address")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")

class OTPRequest(BaseModel):
    """Request for email or phone OTP"""
    email: Optional[str] = Field(None, description="User's email address")
    phone_number: Optional[str] = Field(None, description="User's phone number")
    
    @model_validator(mode='after')
    def validate_email_or_phone(self):
        """Validate that either email or phone_number is provided"""
        if not self.email and not self.phone_number:
            raise ValueError("Either email or phone_number must be provided")
        if self.email and self.phone_number:
            raise ValueError("Provide either email or phone_number, not both")
        return self
    
    @property
    def identifier(self) -> str:
        """Get the identifier (email or phone)"""
        return self.email if self.email else self.phone_number

class PhoneOTPVerification(BaseModel):
    phone_number: str = Field(..., description="User's phone number")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")

class PhoneOTPRequest(BaseModel):
    phone_number: str = Field(..., description="User's phone number")

class PasswordResetOTP(BaseModel):
    """Password reset using OTP for email or phone"""
    email: Optional[str] = Field(None, description="User's email address")
    phone_number: Optional[str] = Field(None, description="User's phone number")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., min_length=8, description="Confirm new password")
    
    @model_validator(mode='after')
    def validate_email_or_phone(self):
        """Validate that either email or phone_number is provided"""
        if not self.email and not self.phone_number:
            raise ValueError("Either email or phone_number must be provided")
        if self.email and self.phone_number:
            raise ValueError("Provide either email or phone_number, not both")
        return self
    
    def validate_passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
    
    @property
    def identifier(self) -> str:
        """Get the identifier (email or phone)"""
        return self.email if self.email else self.phone_number

class GoogleMobileSignIn(BaseModel):
    """Google Sign-In from mobile app (Flutter)"""
    id_token: str = Field(..., description="Google ID token from Flutter google_sign_in package")
    access_token: Optional[str] = Field(None, description="Optional: Google access token for additional scopes")

auth_router = APIRouter()
security = HTTPBearer()

# Rate limiting decorators
rate_limit_register = create_rate_limit_decorator(RateLimitConfig.REGISTER)
rate_limit_login = create_rate_limit_decorator(RateLimitConfig.LOGIN)
rate_limit_password_reset = create_rate_limit_decorator(RateLimitConfig.PASSWORD_RESET)
rate_limit_email_verification = create_rate_limit_decorator(RateLimitConfig.EMAIL_VERIFICATION)
rate_limit_otp = create_rate_limit_decorator(RateLimitConfig.OTP_REQUEST)

@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@rate_limit_register
async def register(
    request: Request,
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """Register a new user account"""
    try:
        auth_service = AuthService(db)
        user = auth_service.register_user(user_data)
        return user
    except Exception as e:
        import traceback
        print(f"Registration error: {str(e)}")
        print(traceback.format_exc())
        if "already exists" in str(e).lower():
            raise http_409_conflict(str(e))
        elif "do not match" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request(f"Registration failed: {str(e)}")

@auth_router.post("/login", response_model=TokenResponse)
@rate_limit_login
async def login(
    request: Request,
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """Authenticate user and return access tokens"""
    try:
        auth_service = AuthService(db)
        
        # Extract session information
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        token_response = auth_service.login(
            login_data,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return token_response
    except Exception as e:
        if "invalid" in str(e).lower() or "incorrect" in str(e).lower():
            raise http_401_unauthorized("Invalid email or password")
        elif "deactivated" in str(e).lower():
            raise http_401_unauthorized("Account is deactivated")
        else:
            raise http_401_unauthorized("Authentication failed")

@auth_router.post("/token", response_model=TokenResponse)
@rate_limit_login
async def oauth2_password_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """OAuth2 Password flow-compatible token endpoint for Swagger UI.

    Accepts `application/x-www-form-urlencoded` fields `username` and `password`,
    maps them to the existing login service (email + password), and returns
    a `TokenResponse` with `access_token`, `token_type`, and optional fields.
    """
    try:
        auth_service = AuthService(db)

        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None

        login_payload = UserLogin(email=form_data.username, password=form_data.password)
        token_response = auth_service.login(
            login_payload,
            ip_address=ip_address,
            user_agent=user_agent
        )
        return token_response
    except Exception as e:
        if "invalid" in str(e).lower() or "incorrect" in str(e).lower():
            raise http_401_unauthorized("Invalid email or password")
        elif "deactivated" in str(e).lower():
            raise http_401_unauthorized("Account is deactivated")
        else:
            raise http_401_unauthorized("Authentication failed")

@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    try:
        auth_service = AuthService(db)
        token_response = auth_service.refresh_token(token_data.refresh_token)
        return token_response
    except Exception as e:
        if "invalid" in str(e).lower() or "expired" in str(e).lower():
            raise http_401_unauthorized("Invalid or expired refresh token")
        else:
            raise http_401_unauthorized("Token refresh failed")

@auth_router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout current user session"""
    try:
        auth_service = AuthService(db)
        
        # Extract session token from Authorization header
        auth_header = request.headers.get("authorization")
        session_token = None
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
        
        success = auth_service.logout(current_user.id, session_token)
        
        return {
            "message": "Successfully logged out",
            "success": success
        }
    except Exception:
        raise http_400_bad_request("Logout failed")

@auth_router.post("/logout-all")
async def logout_all_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout user from all sessions"""
    try:
        auth_service = AuthService(db)
        session_count = auth_service.logout_all_sessions(current_user.id)
        
        return {
            "message": f"Successfully logged out from {session_count} sessions",
            "sessions_terminated": session_count
        }
    except Exception:
        raise http_400_bad_request("Logout failed")

@auth_router.get("/sessions")
async def get_active_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all active sessions for current user"""
    try:
        auth_service = AuthService(db)
        sessions = auth_service.get_active_sessions(current_user.id)
        
        # Format session data for response
        session_data = []
        for session in sessions:
            session_data.append({
                "id": session.id,
                "created_at": session.created_at,
                "expires_at": session.expires_at,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "device_info": session.device_info
            })
        
        return {
            "sessions": session_data,
            "total": len(session_data)
        }
    except Exception:
        raise http_400_bad_request("Failed to retrieve sessions")

@auth_router.delete("/sessions/{session_id}")
async def terminate_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Terminate a specific session"""
    try:
        # Get the session and verify it belongs to current user
        session = db.query(UserSession).filter(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id,
            UserSession.is_active == True
        ).first()
        
        if not session:
            raise http_400_bad_request("Session not found")
        
        # Deactivate session
        session.is_active = False
        db.commit()
        
        return {
            "message": "Session terminated successfully",
            "session_id": session_id
        }
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_400_bad_request("Session not found")
        else:
            raise http_400_bad_request("Failed to terminate session")

# Google OAuth endpoints
@auth_router.post("/google/mobile", response_model=TokenResponse)
@rate_limit_login
async def google_mobile_sign_in(
    request: Request,
    google_data: GoogleMobileSignIn,
    db: Session = Depends(get_db)
):
    """Mobile-first Google Sign-In endpoint for Flutter apps.
    
    This endpoint accepts a Google ID token obtained from the Flutter google_sign_in package.
    The mobile app handles the OAuth flow natively, and sends the ID token to this endpoint.
    
    Flow:
    1. Mobile app uses google_sign_in Flutter package
    2. User signs in with Google (in-app)
    3. App receives ID token from Google
    4. App sends ID token to this endpoint
    5. Backend verifies token and creates/logs in user
    6. Returns access/refresh tokens
    """
    try:
        # Verify the Google ID token
        try:
            idinfo = id_token.verify_oauth2_token(
                google_data.id_token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
        except ValueError as e:
            raise http_401_unauthorized(f"Invalid Google ID token: {str(e)}")
        
        # Extract user information from the verified token
        google_user_id = idinfo.get('sub')
        email = idinfo.get('email')
        email_verified = idinfo.get('email_verified', False)
        name = idinfo.get('name', '')
        given_name = idinfo.get('given_name', '')
        family_name = idinfo.get('family_name', '')
        picture = idinfo.get('picture')
        
        if not email:
            raise http_400_bad_request("No email found in Google token")
        
        if not email_verified:
            raise http_400_bad_request("Google email is not verified")
        
        # Use GoogleOAuthService to handle user creation/authentication
        google_oauth = GoogleOAuthService(db)
        auth_service = AuthService(db)
        
        # Check if user exists
        user = auth_service.user_db.get_user_by_email(email)
        
        if not user:
            # Generate a secure random password for this OAuth user
            # User won't know this password - they authenticate via Google
            random_password = AuthService.generate_random_password()
            
            try:
                # Create new user from Google info
                user_data = UserRegister(
                    email=email,
                    full_name=name or f"{given_name} {family_name}".strip() or 'Google User',
                    password=random_password,
                    confirm_password=random_password,  # Match password for validation
                )
                # Skip verification OTP for Google users (they're pre-verified by Google)
                user = auth_service.register_user(user_data, skip_verification=True)
                
                # Mark as verified since Google verified the email
                user.is_verified = True
                user.google_id = google_user_id
                user.profile_picture_url = picture
                db.commit()
            except Exception as reg_error:
                db.rollback()
                print(f"Error creating Google user: {str(reg_error)}")
                raise http_400_bad_request(f"Failed to create user account: {str(reg_error)}")
        else:
            # Update existing user with Google info if not already linked
            if not user.google_id:
                user.google_id = google_user_id
            if not user.profile_picture_url and picture:
                user.profile_picture_url = picture
            if not user.is_verified:
                user.is_verified = True
            db.commit()
        
        # Check if user account is active
        if not user.is_active:
            raise http_401_unauthorized("Account is deactivated")
        
        # Generate tokens and create session
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        access_token, refresh_token = auth_service.create_user_session(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Return token response
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Google mobile sign-in error: {str(e)}")
        print(traceback.format_exc())
        raise http_400_bad_request(f"Google sign-in failed: {str(e)}")

# OTP-based verification endpoints
@auth_router.post("/verify-email-otp")
@rate_limit_email_verification
async def verify_email_with_otp(
    request: Request,
    verification: OTPVerification,
    db: Session = Depends(get_db)
):
    """Verify email address using OTP"""
    try:
        auth_service = AuthService(db)
        success = auth_service.verify_email_otp(verification.email, verification.otp)
        
        if success:
            return {
                "message": "Email verified successfully!",
                "verified": True
            }
        else:
            raise http_400_bad_request("Email verification failed")
            
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        elif "invalid" in str(e).lower() or "expired" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Email verification failed")

@auth_router.post("/verify-phone-otp")
@rate_limit_email_verification
async def verify_phone_with_otp(
    request: Request,
    verification: PhoneOTPVerification,
    db: Session = Depends(get_db)
):
    """Verify phone number using OTP"""
    try:
        auth_service = AuthService(db)
        success = auth_service.verify_phone_otp(verification.phone_number, verification.otp)
        
        if success:
            return {
                "message": "Phone number verified successfully!",
                "verified": True
            }
        else:
            raise http_400_bad_request("Phone verification failed")
            
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        elif "invalid" in str(e).lower() or "expired" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Phone verification failed")

@auth_router.post("/resend-verification-otp")
@rate_limit_otp
async def resend_verification_otp(
    request: Request,
    otp_request: OTPRequest,
    db: Session = Depends(get_db)
):
    """Resend email verification OTP"""
    try:
        auth_service = AuthService(db)
        success = auth_service.resend_verification_otp(otp_request.identifier)
        
        if success:
            return {
                "message": "Verification code sent to your email",
                "sent": True
            }
        else:
            raise http_400_bad_request("Failed to send verification code")
            
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        elif "already verified" in str(e).lower():
            raise http_400_bad_request("Email is already verified")
        elif "wait" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Failed to send verification code")

@auth_router.post("/resend-phone-otp")
@rate_limit_otp
async def resend_phone_otp(
    request: Request,
    phone_request: PhoneOTPRequest,
    db: Session = Depends(get_db)
):
    """Resend phone verification OTP via SMS"""
    try:
        auth_service = AuthService(db)
        # Use the same method but pass phone number
        success = auth_service.resend_verification_otp(phone_request.phone_number)
        
        if success:
            return {
                "message": "Verification code sent to your phone",
                "sent": True
            }
        else:
            raise http_400_bad_request("Failed to send verification code")
            
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        elif "already verified" in str(e).lower():
            raise http_400_bad_request("Phone number is already verified")
        elif "wait" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Failed to send verification code")

@auth_router.get("/otp-status/{email}")
async def get_otp_status(
    email: str,
    db: Session = Depends(get_db)
):
    """Get OTP status for user"""
    try:
        auth_service = AuthService(db)
        status = auth_service.get_otp_status(email)
        
        return {
            "email": email,
            "otp_status": status
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        else:
            raise http_400_bad_request("Failed to get OTP status")

@auth_router.post("/request-password-reset-otp")
@rate_limit_otp
async def request_password_reset_otp(
    request: Request,
    otp_request: OTPRequest,
    db: Session = Depends(get_db)
):
    """Request password reset OTP via email or SMS"""
    try:
        auth_service = AuthService(db)
        success = auth_service.request_password_reset(otp_request.identifier)
        
        if success:
            return {
                "message": "Password reset code sent successfully",
                "sent": True
            }
        else:
            raise http_400_bad_request("Failed to send password reset code")
            
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        elif "deactivated" in str(e).lower():
            raise http_400_bad_request("Account is deactivated")
        else:
            raise http_400_bad_request("Failed to send password reset code")

@auth_router.post("/reset-password-otp")
@rate_limit_password_reset
async def reset_password_with_otp(
    request: Request,
    reset_data: PasswordResetOTP,
    db: Session = Depends(get_db)
):
    """Reset password using OTP (works for both email and phone users)"""
    try:
        # Validate password match
        reset_data.validate_passwords_match()
        
        auth_service = AuthService(db)
        success = auth_service.reset_password_with_otp(
            reset_data.identifier, 
            reset_data.otp, 
            reset_data.new_password
        )
        
        if success:
            return {
                "message": "Password reset successfully",
                "reset": True
            }
        else:
            raise http_400_bad_request("Password reset failed")
            
    except ValueError as e:
        if "do not match" in str(e):
            raise http_400_bad_request("Passwords do not match")
        else:
            raise http_400_bad_request(str(e))
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        elif "invalid" in str(e).lower() or "expired" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Password reset failed")
