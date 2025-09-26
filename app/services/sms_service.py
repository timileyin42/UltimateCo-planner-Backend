from typing import Optional, Dict, Any
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from fastapi import HTTPException, status
import logging
from app.core.config import get_settings
from app.core.circuit_breaker import sms_circuit_breaker, sms_fallback

logger = logging.getLogger(__name__)


class SMSService:
    def __init__(self):
        self.settings = get_settings()
        self.account_sid = self.settings.TWILIO_ACCOUNT_SID
        self.auth_token = self.settings.TWILIO_AUTH_TOKEN
        self.from_phone = self.settings.TWILIO_PHONE_NUMBER
        
        if not all([self.account_sid, self.auth_token, self.from_phone]):
            logger.warning("Twilio credentials not configured. SMS functionality will be disabled.")
            self.client = None
        else:
            self.client = Client(self.account_sid, self.auth_token)

    @sms_circuit_breaker(fallback=sms_fallback)
    def send_sms(
        self, 
        to_phone: str, 
        message: str, 
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send SMS message to a phone number"""
        if not self.client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS service is not configured"
            )
        
        try:
            # Clean phone number (remove spaces, dashes, etc.)
            cleaned_phone = self._clean_phone_number(to_phone)
            
            # Prepare message data
            message_data = {
                'body': message,
                'from_': self.from_phone,
                'to': cleaned_phone
            }
            
            if media_url:
                message_data['media_url'] = [media_url]
            
            # Send message
            twilio_message = self.client.messages.create(**message_data)
            
            return {
                'sid': twilio_message.sid,
                'status': twilio_message.status,
                'to': cleaned_phone,
                'from': self.from_phone,
                'body': message,
                'date_sent': twilio_message.date_sent
            }
            
        except TwilioException as e:
            logger.error(f"Twilio error sending SMS to {to_phone}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to send SMS: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {to_phone}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send SMS due to internal error"
            )

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
        """Send phone verification code SMS"""
        message = f"Your PlanEtAl verification code is: {verification_code}\n\n"
        message += "This code will expire in 10 minutes.\n"
        message += "Don't share this code with anyone."
        
        return self.send_sms(to_phone, message)

    def send_password_reset_sms(
        self, 
        to_phone: str, 
        reset_code: str
    ) -> Dict[str, Any]:
        """Send password reset code SMS"""
        message = f"Your PlanEtAl password reset code is: {reset_code}\n\n"
        message += "This code will expire in 15 minutes.\n"
        message += "If you didn't request this, please ignore this message."
        
        return self.send_sms(to_phone, message)

    def _clean_phone_number(self, phone_number: str) -> str:
        """Clean and format phone number for Twilio"""
        # Remove all non-digit characters except +
        cleaned = ''.join(char for char in phone_number if char.isdigit() or char == '+')
        
        # If no country code, assume US (+1)
        if not cleaned.startswith('+'):
            if len(cleaned) == 10:  # US number without country code
                cleaned = '+1' + cleaned
            elif len(cleaned) == 11 and cleaned.startswith('1'):  # US number with 1 prefix
                cleaned = '+' + cleaned
            else:
                # For other countries, add + if missing
                cleaned = '+' + cleaned
        
        return cleaned

    def get_message_status(self, message_sid: str) -> Dict[str, Any]:
        """Get status of a sent message"""
        if not self.client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS service is not configured"
            )
        
        try:
            message = self.client.messages(message_sid).fetch()
            
            return {
                'sid': message.sid,
                'status': message.status,
                'error_code': message.error_code,
                'error_message': message.error_message,
                'date_sent': message.date_sent,
                'date_updated': message.date_updated
            }
            
        except TwilioException as e:
            logger.error(f"Error fetching message status for {message_sid}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to get message status: {str(e)}"
            )

    def is_configured(self) -> bool:
        """Check if SMS service is properly configured"""
        return self.client is not None