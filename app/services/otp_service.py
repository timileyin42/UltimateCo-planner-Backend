import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.user_models import User
from app.core.errors import ValidationError, AuthenticationError
from app.services.email_service import email_service
from app.services.sms_service import SMSService
import asyncio

class OTPService:
    """Service for managing OTP (One-Time Password) operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.otp_length = 6
        self.otp_expiry_minutes = 10  # OTP expires in 10 minutes
        self.max_attempts = 5  # Maximum verification attempts
        self.sms_service = SMSService()
    
    def generate_otp(self) -> str:
        """Generate a 6-digit OTP."""
        return ''.join(secrets.choice(string.digits) for _ in range(self.otp_length))
    
    def send_verification_otp(self, user: User, method: str = "email") -> bool:
        """Generate and send OTP for verification via email or SMS.
        
        Args:
            user: User object
            method: Verification method - "email", "sms", or "both"
        """
        try:
            # Generate new OTP
            otp = self.generate_otp()
            expires_at = datetime.utcnow() + timedelta(minutes=self.otp_expiry_minutes)
            
            # Update user with OTP details
            user.email_verification_otp = otp
            user.otp_expires_at = expires_at
            user.otp_attempts = 0  # Reset attempts
            
            self.db.commit()
            
            success = True
            
            # Send via email
            if method in ["email", "both"] and user.email:
                try:
                    asyncio.create_task(email_service.send_verification_otp(user, otp))
                except Exception as e:
                    print(f"Failed to send OTP email: {str(e)}")
                    if method == "email":
                        success = False
            
            # Send via SMS
            if method in ["sms", "both"] and user.phone_number:
                try:
                    self.sms_service.send_verification_code_sms(user.phone_number, otp)
                except Exception as e:
                    print(f"Failed to send OTP SMS: {str(e)}")
                    if method == "sms":
                        success = False
            
            return success
            
        except Exception as e:
            self.db.rollback()
            print(f"Failed to generate OTP: {str(e)}")
            return False
    
    def verify_otp(self, user: User, provided_otp: str) -> Tuple[bool, str]:
        """Verify the provided OTP against user's stored OTP.
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Check if user has an OTP
            if not user.email_verification_otp:
                return False, "No OTP found. Please request a new verification code."
            
            # Check if OTP has expired
            if user.otp_expires_at and datetime.utcnow() > user.otp_expires_at:
                # Clear expired OTP
                user.email_verification_otp = None
                user.otp_expires_at = None
                user.otp_attempts = 0
                self.db.commit()
                return False, "OTP has expired. Please request a new verification code."
            
            # Check attempt limit
            if user.otp_attempts >= self.max_attempts:
                # Clear OTP after max attempts
                user.email_verification_otp = None
                user.otp_expires_at = None
                user.otp_attempts = 0
                self.db.commit()
                return False, "Too many failed attempts. Please request a new verification code."
            
            # Increment attempt count
            user.otp_attempts += 1
            
            # Verify OTP
            if user.email_verification_otp == provided_otp:
                # OTP is correct - verify user and clear OTP
                user.is_verified = True
                user.email_verification_otp = None
                user.otp_expires_at = None
                user.otp_attempts = 0
                self.db.commit()
                return True, "Email verified successfully!"
            else:
                # OTP is incorrect
                self.db.commit()
                remaining_attempts = self.max_attempts - user.otp_attempts
                if remaining_attempts > 0:
                    return False, f"Invalid OTP. {remaining_attempts} attempts remaining."
                else:
                    # Clear OTP after max attempts reached
                    user.email_verification_otp = None
                    user.otp_expires_at = None
                    user.otp_attempts = 0
                    self.db.commit()
                    return False, "Too many failed attempts. Please request a new verification code."
                    
        except Exception as e:
            self.db.rollback()
            print(f"OTP verification error: {str(e)}")
            return False, "Verification failed. Please try again."
    
    def resend_otp(self, user: User, method: str = "email") -> Tuple[bool, str]:
        """Resend OTP to user via email or SMS.
        
        Args:
            user: User object
            method: Verification method - "email", "sms", or "both"
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Check if user is already verified
            if user.is_verified:
                return False, "Email is already verified."
            
            # Check rate limiting (prevent spam)
            if (user.otp_expires_at and 
                datetime.utcnow() < user.otp_expires_at - timedelta(minutes=self.otp_expiry_minutes - 2)):
                remaining_time = (user.otp_expires_at - timedelta(minutes=self.otp_expiry_minutes - 2) - datetime.utcnow()).seconds // 60
                return False, f"Please wait {remaining_time + 1} minutes before requesting a new OTP."
            
            # Generate and send new OTP
            success = self.send_verification_otp(user, method)
            
            if success:
                if method == "email":
                    return True, "New verification code sent to your email."
                elif method == "sms":
                    return True, "New verification code sent to your phone."
                else:
                    return True, "New verification code sent to your email and phone."
            else:
                return False, "Failed to send verification code. Please try again."
                
        except Exception as e:
            print(f"Resend OTP error: {str(e)}")
            return False, "Failed to resend verification code. Please try again."
    
    def send_password_reset_otp(self, user: User, method: str = "email") -> bool:
        """Generate and send OTP for password reset via email or SMS.
        
        Args:
            user: User object
            method: Verification method - "email", "sms", or "both"
        """
        try:
            # Generate new OTP
            otp = self.generate_otp()
            expires_at = datetime.utcnow() + timedelta(minutes=self.otp_expiry_minutes)
            
            # Store OTP in user record (reusing email verification fields)
            user.email_verification_otp = otp
            user.otp_expires_at = expires_at
            user.otp_attempts = 0
            
            self.db.commit()
            
            success = True
            
            # Send via email
            if method in ["email", "both"] and user.email:
                try:
                    asyncio.create_task(email_service.send_password_reset_otp(user, otp))
                except Exception as e:
                    print(f"Failed to send password reset OTP email: {str(e)}")
                    if method == "email":
                        success = False
            
            # Send via SMS
            if method in ["sms", "both"] and user.phone_number:
                try:
                    self.sms_service.send_password_reset_sms(user.phone_number, otp)
                except Exception as e:
                    print(f"Failed to send password reset OTP SMS: {str(e)}")
                    if method == "sms":
                        success = False
            
            return success
            
        except Exception as e:
            self.db.rollback()
            print(f"Failed to generate password reset OTP: {str(e)}")
            return False
    
    def verify_password_reset_otp(self, user: User, provided_otp: str) -> Tuple[bool, str]:
        """Verify OTP for password reset.
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Check if user has an OTP
            if not user.email_verification_otp:
                return False, "No verification code found. Please request password reset again."
            
            # Check if OTP has expired
            if user.otp_expires_at and datetime.utcnow() > user.otp_expires_at:
                # Clear expired OTP
                user.email_verification_otp = None
                user.otp_expires_at = None
                user.otp_attempts = 0
                self.db.commit()
                return False, "Verification code has expired. Please request password reset again."
            
            # Check attempt limit
            if user.otp_attempts >= self.max_attempts:
                # Clear OTP after max attempts
                user.email_verification_otp = None
                user.otp_expires_at = None
                user.otp_attempts = 0
                self.db.commit()
                return False, "Too many failed attempts. Please request password reset again."
            
            # Increment attempt count
            user.otp_attempts += 1
            
            # Verify OTP
            if user.email_verification_otp == provided_otp:
                # OTP is correct - don't clear it yet, it will be cleared when password is reset
                self.db.commit()
                return True, "Verification code confirmed. You can now reset your password."
            else:
                # OTP is incorrect
                self.db.commit()
                remaining_attempts = self.max_attempts - user.otp_attempts
                if remaining_attempts > 0:
                    return False, f"Invalid verification code. {remaining_attempts} attempts remaining."
                else:
                    # Clear OTP after max attempts reached
                    user.email_verification_otp = None
                    user.otp_expires_at = None
                    user.otp_attempts = 0
                    self.db.commit()
                    return False, "Too many failed attempts. Please request password reset again."
                    
        except Exception as e:
            self.db.rollback()
            print(f"Password reset OTP verification error: {str(e)}")
            return False, "Verification failed. Please try again."
    
    def clear_otp(self, user: User) -> None:
        """Clear OTP data from user record."""
        try:
            user.email_verification_otp = None
            user.otp_expires_at = None
            user.otp_attempts = 0
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"Failed to clear OTP: {str(e)}")
    
    def get_otp_status(self, user: User) -> dict:
        """Get current OTP status for user."""
        if not user.email_verification_otp:
            return {
                "has_otp": False,
                "is_expired": False,
                "attempts_remaining": self.max_attempts,
                "expires_at": None
            }
        
        is_expired = (user.otp_expires_at and 
                     datetime.utcnow() > user.otp_expires_at)
        
        return {
            "has_otp": True,
            "is_expired": is_expired,
            "attempts_remaining": max(0, self.max_attempts - user.otp_attempts),
            "expires_at": user.otp_expires_at.isoformat() if user.otp_expires_at else None
        }