from typing import Optional, Dict, Any
import requests
from fastapi import HTTPException, status
import logging
from app.core.config import get_settings
from app.core.circuit_breaker import sms_circuit_breaker, sms_fallback

logger = logging.getLogger(__name__)


class SMSService:
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.TERMII_API_KEY
        self.sender_id = self.settings.TERMII_SENDER_ID
        self.base_url = self.settings.TERMII_BASE_URL
        
        if not all([self.api_key, self.sender_id]):
            logger.warning("Termii credentials not configured. SMS functionality will be disabled.")
            self.is_configured_flag = False
        else:
            self.is_configured_flag = True

    @sms_circuit_breaker(fallback=sms_fallback)
    def send_sms(
        self, 
        to_phone: str, 
        message: str, 
        media_url: Optional[str] = None,
        channel: str = "generic"
    ) -> Dict[str, Any]:
        """Send SMS message to a phone number using Termii API
        
        Args:
            to_phone: Recipient phone number in international format
            message: Text message to send
            media_url: Optional media URL (for future use)
            channel: Route to use - 'dnd' for transactional/OTP, 'generic' for promotional
        """
        if not self.is_configured_flag:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS service is not configured"
            )
        
        try:
            # Clean phone number (remove spaces, dashes, etc.)
            cleaned_phone = self._clean_phone_number(to_phone)
            
            # Prepare Termii API payload
            payload = {
                "to": cleaned_phone,
                "from": self.sender_id,
                "sms": message,
                "type": "plain",
                "api_key": self.api_key,
                "channel": channel
            }
            
            # Send request to Termii API
            response = requests.post(
                f"{self.base_url}/sms/send",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Log successful
                logger.info(
                    f"SMS sent successfully | To: {cleaned_phone[:4]}****{cleaned_phone[-4:]} | "
                    f"Message ID: {result.get('message_id')} | Length: {len(message)} chars"
                )
                
                return {
                    'message_id': result.get('message_id'),
                    'status': 'sent',
                    'to': cleaned_phone,
                    'from': self.sender_id,
                    'body': message,
                    'balance': result.get('balance'),
                    'user': result.get('user')
                }
            else:
                error_msg = response.json().get('message', 'Unknown error')
                
                # Log failure
                logger.error(
                    f"SMS send failed | To: {to_phone} | Status: {response.status_code} | "
                    f"Error: {error_msg}"
                )
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to send SMS: {error_msg}"
                )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error sending SMS to {to_phone}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send SMS due to network error"
            )
        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {to_phone}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send SMS due to internal error"
            )

    def send_transactional_sms(
        self,
        to_phone: str,
        message: str
    ) -> Dict[str, Any]:
        """Send transactional/OTP SMS using DND route.
        
        Use this method for:
        - OTP/verification codes
        - Password reset codes
        - Critical account notifications
        - Time-sensitive transactional messages
        
        Per Termii docs: DND route bypasses Do-Not-Disturb restrictions 
        and ensures reliable delivery of critical messages.
        """
        return self.send_sms(to_phone, message, channel="dnd")

    def send_event_invitation_sms(
        self, 
        to_phone: str, 
        sender_name: str, 
        event_title: str,
        event_date: str,
        invitation_link: str,
        personal_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send event invitation SMS"""
        message = f"🎉 Hi! {sender_name} invited you to '{event_title}' on {event_date}.\n\n"
        message += f"Join the event: {invitation_link}\n\n"
        
        if personal_message:
            message += f"Personal message: {personal_message}\n\n"
        
        message += "Powered by PlanEtAl 🌟"
        
        return self.send_sms(to_phone, message)

    def send_event_reminder_sms(
        self, 
        to_phone: str, 
        event_title: str,
        event_date: str,
        event_location: Optional[str] = None,
        hours_before: int = 24
    ) -> Dict[str, Any]:
        """Send event reminder SMS"""
        message = f"⏰ Reminder: '{event_title}' is in {hours_before} hours!\n\n"
        message += f"📅 Date: {event_date}\n"
        
        if event_location:
            message += f" Location: {event_location}\n"
        
        message += "\nDon't miss it! 🎉\n"
        message += "Powered by PlanEtAl"
        
        return self.send_sms(to_phone, message)

    def send_event_update_sms(
        self, 
        to_phone: str, 
        event_title: str,
        update_type: str,  # 'cancelled', 'rescheduled', 'location_changed', 'updated'
        update_details: str
    ) -> Dict[str, Any]:
        """Send event update notification SMS"""
        emoji_map = {
            'cancelled': '',
            'rescheduled': '📅',
            'location_changed': '',
            'updated': ''
        }
        
        emoji = emoji_map.get(update_type, '📝')
        
        message = f"{emoji} Event Update: '{event_title}'\n\n"
        message += f"{update_details}\n\n"
        message += "Check the app for full details.\n"
        message += "Powered by PlanEtAl"
        
        return self.send_sms(to_phone, message)

    def send_app_invitation_sms(
        self, 
        to_phone: str, 
        sender_name: str,
        invitation_link: str,
        personal_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send app invitation SMS"""
        message = f"🌟 Hi! {sender_name} invited you to join PlanEtAl - the ultimate event planning app!\n\n"
        message += f"Download and join: {invitation_link}\n\n"
        
        if personal_message:
            message += f"Personal message: {personal_message}\n\n"
        
        message += "Plan amazing events together! 🎉"
        
        return self.send_sms(to_phone, message)

    def send_verification_code_sms(
        self, 
        to_phone: str, 
        verification_code: str
    ) -> Dict[str, Any]:
        """Send phone verification code SMS
        
        Note: Using 'generic' channel temporarily. For production:
        1. Contact Termii support: support@termii.com
        2. Request DND route activation for your account
        3. Then switch to: return self.send_transactional_sms(to_phone, message)
        """
        message = f"Your PlanEtAl verification code is: {verification_code}\n\n"
        message += "This code will expire in 10 minutes.\n"
        message += "Don't share this code with anyone."
        
        return self.send_sms(to_phone, message, channel="generic")

    def send_password_reset_sms(
        self, 
        to_phone: str, 
        reset_code: str
    ) -> Dict[str, Any]:
        """Send password reset code SMS
        
        Note: Using 'generic' channel temporarily. For production:
        1. Contact Termii support: support@termii.com
        2. Request DND route activation for your account
        3. Then switch to: return self.send_transactional_sms(to_phone, message)
        """
        message = f"Your PlanEtAl password reset code is: {reset_code}\n\n"
        message += "This code will expire in 15 minutes.\n"
        message += "If you didn't request this, please ignore this message."
        
        return self.send_sms(to_phone, message, channel="generic")

    def _clean_phone_number(self, phone_number: str) -> str:
        """Clean and format phone number for Termii API"""
        # Remove all non-digit characters except +
        cleaned = ''.join(char for char in phone_number if char.isdigit() or char == '+')
        
        # If no country code, assume Nigeria (+234) for Termii
        if not cleaned.startswith('+'):
            if len(cleaned) == 11 and cleaned.startswith('0'):  # Nigerian number starting with 0
                cleaned = '+234' + cleaned[1:]  # Replace 0 with +234
            elif len(cleaned) == 10:  # Nigerian number without leading 0
                cleaned = '+234' + cleaned
            elif len(cleaned) == 11 and cleaned.startswith('234'):  # Nigerian with 234 prefix
                cleaned = '+' + cleaned
            else:
                # For other countries, add + if missing
                cleaned = '+' + cleaned
        
        return cleaned

    def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """
        Check SMS delivery status.
        
        Note: Termii doesn't provide a direct status lookup endpoint.
        For detailed SMS analytics, we will use Termii's dashboard
        
        """
        if not self.is_configured_flag:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS service is not configured"
            )
        
        return {
            'message_id': message_id,
            'status': 'sent',
            'note': (
                'SMS was sent to Termii. For delivery confirmation, '
                'check Termii dashboard '
            ),
            'recommendation': (
                'SMS delivery rates are typically 95%+. '
                'Critical delivery tracking should use Termii\'s dashboard.'
            )
        }

    def is_configured(self) -> bool:
        """Check if SMS service is properly configured"""
        return self.is_configured_flag
    
    def get_balance(self) -> Dict[str, Any]:
        """Get account balance from Termii"""
        if not self.is_configured_flag:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS service is not configured"
            )
        
        try:
            response = requests.get(
                f"{self.base_url}/get-balance",
                params={"api_key": self.api_key},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = response.json().get('message', 'Unknown error')
                logger.error(f"Termii API error getting balance: {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to get balance: {error_msg}"
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error getting balance: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get balance due to network error"
            )
    
    def send_token(self, to_phone: str, pin_type: str = "NUMERIC", pin_length: int = 6) -> Dict[str, Any]:
        """Send OTP token using Termii Token API"""
        if not self.is_configured_flag:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS service is not configured"
            )
        
        try:
            cleaned_phone = self._clean_phone_number(to_phone)
            
            payload = {
                "api_key": self.api_key,
                "message_type": "NUMERIC",
                "to": cleaned_phone,
                "from": self.sender_id,
                "channel": "generic",
                "pin_attempts": 3,
                "pin_time_to_live": 10,  # 10 minutes
                "pin_length": pin_length,
                "pin_placeholder": "< 1234 >",
                "message_text": f"Your PlanEtAl verification code is < 1234 >. This code expires in 10 minutes.",
                "pin_type": pin_type
            }
            
            response = requests.post(
                f"{self.base_url}/sms/otp/send",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = response.json().get('message', 'Unknown error')
                logger.error(f"Termii API error sending token to {to_phone}: {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to send token: {error_msg}"
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error sending token to {to_phone}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send token due to network error"
            )
    
    def verify_token(self, pin_id: str, pin_code: str) -> Dict[str, Any]:
        """Verify OTP token using Termii Token API"""
        if not self.is_configured_flag:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS service is not configured"
            )
        
        try:
            payload = {
                "api_key": self.api_key,
                "pin_id": pin_id,
                "pin": pin_code
            }
            
            response = requests.post(
                f"{self.base_url}/sms/otp/verify",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = response.json().get('message', 'Unknown error')
                logger.error(f"Termii API error verifying token: {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to verify token: {error_msg}"
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error verifying token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify token due to network error"
            )


# Create service instance
sms_service = SMSService()