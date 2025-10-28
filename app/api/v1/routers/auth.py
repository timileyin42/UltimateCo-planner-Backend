from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
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
from pydantic import BaseModel, Field
from app.models.user_models import User
from app.models.user_models import UserSession
from typing import Optional
import asyncio

# OTP-related models
class OTPVerification(BaseModel):
    email: str = Field(..., description="User's email address")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")

class OTPRequest(BaseModel):
    email: str = Field(..., description="User's email address")

class PasswordResetOTP(BaseModel):
    email: str = Field(..., description="User's email address")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., min_length=8, description="Confirm new password")
    
    def validate_passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")

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
    user_data: UserRegister,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new user account"""
    try:
        auth_service = AuthService(db)
        user = auth_service.register_user(user_data)
        return user
    except Exception as e:
        if "already exists" in str(e).lower():
            raise http_409_conflict(str(e))
        elif "do not match" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Registration failed")

@auth_router.post("/login", response_model=TokenResponse)
@rate_limit_login
async def login(
    login_data: UserLogin,
    request: Request,
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

@auth_router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    confirm_new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    try:
        if new_password != confirm_new_password:
            raise http_400_bad_request("New passwords do not match")
        
        auth_service = AuthService(db)
        success = auth_service.change_password(
            current_user.id,
            current_password,
            new_password
        )
        
        return {
            "message": "Password changed successfully",
            "success": success
        }
    except Exception as e:
        if "incorrect" in str(e).lower():
            raise http_400_bad_request("Current password is incorrect")
        else:
            raise http_400_bad_request("Password change failed")

@auth_router.post("/forgot-password")
@rate_limit_password_reset
async def forgot_password(
    request: Request,
    password_reset: PasswordReset,
    db: Session = Depends(get_db)
):
    """Request password reset token via email"""
    try:
        auth_service = AuthService(db)
        # This method handles security (doesn't reveal if email exists)
        token = auth_service.generate_password_reset_token(password_reset.email)
        
        # Always return success to prevent email enumeration
        return {
            "message": "If the email exists, a password reset link has been sent",
            "sent": True
        }
    except Exception:
        # Always return success to prevent email enumeration
        return {
            "message": "If the email exists, a password reset link has been sent",
            "sent": True
        }

@auth_router.post("/reset-password")
@rate_limit_password_reset
async def reset_password(
    request: Request,
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """Reset password using reset token"""
    try:
        if reset_data.new_password != reset_data.confirm_new_password:
            raise http_400_bad_request("Passwords do not match")
        
        auth_service = AuthService(db)
        success = auth_service.reset_password(
            reset_data.token,
            reset_data.new_password
        )
        
        return {
            "message": "Password reset successfully",
            "success": success
        }
    except Exception as e:
        if "invalid" in str(e).lower() or "expired" in str(e).lower():
            raise http_400_bad_request("Invalid or expired reset token")
        elif "do not match" in str(e).lower():
            raise http_400_bad_request("Passwords do not match")
        else:
            raise http_400_bad_request("Password reset failed")

@auth_router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user information"""
    return current_user

@auth_router.post("/verify-email")
@rate_limit_email_verification
async def verify_email(
    request: Request,
    verification_token: str,
    db: Session = Depends(get_db)
):
    """Verify user email address using token (legacy method - use /verify-email-otp instead)"""
    try:
        auth_service = AuthService(db)
        
        # Find user by verification token
        user = db.query(User).filter(
            User.email_verification_token == verification_token,
            User.is_verified == False
        ).first()
        
        if not user:
            raise http_400_bad_request("Invalid or expired verification token")
        
        # Mark email as verified
        user.is_verified = True
        user.email_verification_token = None
        db.commit()
        
        # Send welcome email
        try:
            import asyncio
            asyncio.create_task(email_service.send_welcome_email(user))
        except Exception as e:
            print(f"Failed to send welcome email: {str(e)}")
        
        return {
            "message": "Email verified successfully",
            "success": True,
            "recommendation": "Use /verify-email-otp for better security with OTP codes"
        }
    except Exception as e:
        if "Invalid or expired" in str(e):
            raise
        raise http_400_bad_request("Email verification failed")

@auth_router.post("/resend-verification-link")
@rate_limit_email_verification
async def resend_verification_link(
    request: Request,
    email_request: OTPRequest,
    db: Session = Depends(get_db)
):
    """Resend email verification link (legacy token-based method - use /resend-verification-otp instead)"""
    try:
        auth_service = AuthService(db)
        success = auth_service.send_email_verification_link(email_request.email)
        
        # Always return success to prevent email enumeration
        return {
            "message": "If the email exists and is not verified, a verification link has been sent",
            "sent": True,
            "recommendation": "Use /resend-verification-otp for better security with OTP codes"
        }
    except Exception:
        # Always return success to prevent email enumeration
        return {
            "message": "If the email exists and is not verified, a verification link has been sent",
            "sent": True,
            "recommendation": "Use /resend-verification-otp for better security with OTP codes"
        }

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
@auth_router.get("/google/url")
async def get_google_auth_url(
    db: Session = Depends(get_db)
):
    """Get Google OAuth authorization URL"""
    try:
        google_oauth = GoogleOAuthService(db)
        auth_url = google_oauth.get_authorization_url()
        
        return {
            "authorization_url": auth_url,
            "message": "Redirect user to this URL for Google authentication"
        }
    except Exception:
        raise http_400_bad_request("Failed to generate Google OAuth URL")

@auth_router.post("/google/callback", response_model=TokenResponse)
async def google_oauth_callback(
    code: str,
    state: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback and authenticate user"""
    try:
        google_oauth = GoogleOAuthService(db)
        
        # Extract session information
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        # Authenticate or create user
        token_response = await google_oauth.authenticate_or_create_user(
            code=code,
            state=state,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return token_response
        
    except Exception as e:
        if "deactivated" in str(e).lower():
            raise http_401_unauthorized("Account is deactivated")
        elif "failed" in str(e).lower():
            raise http_401_unauthorized(str(e))
        else:
            raise http_400_bad_request("Google OAuth authentication failed")

@auth_router.post("/google/link")
async def link_google_account(
    code: str,
    state: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Link Google account to existing user account"""
    try:
        google_oauth = GoogleOAuthService(db)
        
        # Exchange code for tokens and get user info
        tokens = await google_oauth.exchange_code_for_tokens(code, state)
        access_token = tokens.get("access_token")
        
        if not access_token:
            raise http_400_bad_request("Failed to get access token from Google")
        
        google_user = await google_oauth.get_user_info(access_token)
        google_email = google_user.get("email")
        
        if not google_email:
            raise http_400_bad_request("No email received from Google")
        
        # Check if Google email matches current user's email
        if google_email.lower() != current_user.email.lower():
            raise http_400_bad_request("Google account email must match your current account email")
        
        # Update user with Google info
        google_oauth._update_user_from_google(current_user, google_user)
        
        return {
            "message": "Google account linked successfully",
            "google_email": google_email
        }
        
    except Exception as e:
        if "must match" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
             raise http_400_bad_request("Failed to link Google account")

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

@auth_router.post("/resend-verification-otp")
@rate_limit_otp
async def resend_verification_otp(
    request: OTPRequest,
    db: Session = Depends(get_db)
):
    """Resend email verification OTP"""
    try:
        auth_service = AuthService(db)
        success = auth_service.resend_verification_otp(request.email)
        
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
    request: OTPRequest,
    db: Session = Depends(get_db)
):
    """Request password reset OTP"""
    try:
        auth_service = AuthService(db)
        success = auth_service.request_password_reset(request.email)
        
        if success:
            return {
                "message": "Password reset code sent to your email",
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
    """Reset password using OTP"""
    try:
        # Validate password match
        reset_data.validate_passwords_match()
        
        auth_service = AuthService(db)
        success = auth_service.reset_password_with_otp(
            reset_data.email, 
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