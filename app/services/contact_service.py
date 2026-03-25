from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from datetime import datetime, timedelta
import uuid
import re
from fastapi import HTTPException, status
import phonenumbers
from phonenumbers import NumberParseException

from app.models.contact_models import (
    UserContact, ContactGroup, ContactInvitation, ContactInviteStatus, ContactGroupMembership, ContactSource
)
from app.models.user_models import User
from app.models.event_models import Event, EventInvitation
from app.models.shared_models import RSVPStatus
from app.core.database import get_db
from app.core.config import settings
from app.services.sms_service import SMSService
from app.services.email_service import EmailService


class ContactService:
    def __init__(self, db: Session):
        self.db = db
        self.sms_service = SMSService()
        self.email_service = EmailService()

    @staticmethod
    def _respondable_statuses() -> List[ContactInviteStatus]:
        return [
            ContactInviteStatus.PENDING,
            ContactInviteStatus.SENT,
            ContactInviteStatus.DELIVERED,
            ContactInviteStatus.OPENED,
            ContactInviteStatus.ACCEPTED,
            ContactInviteStatus.DECLINED
        ]

    def add_contact(self, user_id: int, contact_data: Dict[str, Any]) -> UserContact:
        """Add a new contact to user's contact list"""
        # Validate phone number format
        phone_number = contact_data.get('phone_number')
        if phone_number and not self._is_valid_phone_number(phone_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone number format"
            )
        
        # Validate name
        name = contact_data.get('name') or contact_data.get('full_name')
        if not name:
            first = contact_data.get('first_name')
            last = contact_data.get('last_name')
            combined = " ".join(part for part in [first, last] if part)
            name = combined.strip() if combined else None
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact name is required"
            )

        # Check if contact already exists
        existing_contact = self.db.query(UserContact).filter(
            and_(
                UserContact.user_id == user_id,
                or_(
                    UserContact.phone_number == phone_number,
                    UserContact.email == contact_data.get('email')
                )
            )
        ).first()
        
        if existing_contact:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact already exists"
            )
        
        contact = UserContact(
            user_id=user_id,
            name=name,
            phone_number=phone_number,
            email=contact_data.get('email'),
            notes=contact_data.get('notes'),
            is_favorite=contact_data.get('is_favorite', False)
        )
        
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        return contact

    def get_user_contacts(
        self, 
        user_id: int, 
        search: Optional[str] = None,
        favorites_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[UserContact]:
        """Get user's contacts with optional filtering"""
        query = self.db.query(UserContact).filter(UserContact.user_id == user_id)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    UserContact.name.ilike(search_term),
                    UserContact.phone_number.ilike(search_term),
                    UserContact.email.ilike(search_term)
                )
            )
        
        if favorites_only:
            query = query.filter(UserContact.is_favorite == True)
        
        return query.order_by(UserContact.name).offset(offset).limit(limit).all()

    def send_invitation(
        self, 
        sender_id: int, 
        contact_id: int, 
        event_id: Optional[int] = None,
        message: Optional[str] = None
    ) -> ContactInvitation:
        """Send invitation to a contact (alias for send_contact_invitation)"""
        return self.send_contact_invitation(sender_id, contact_id, event_id, message)

    def send_contact_invitation(
        self, 
        sender_id: int, 
        contact_id: int, 
        event_id: Optional[int] = None,
        message: Optional[str] = None
    ) -> ContactInvitation:
        """Send invitation to a contact"""
        # Get contact details
        contact = self.db.query(UserContact).filter(
            and_(
                UserContact.id == contact_id,
                UserContact.user_id == sender_id
            )
        ).first()
        
        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found"
            )
        
        # Check if contact is already a user
        recipient_user = None
        if contact.email:
            recipient_user = self.db.query(User).filter(User.email == contact.email).first()

        delivery_method = "sms" if contact.phone_number else "email" if contact.email else None
        if delivery_method is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact must have a phone number or email to receive invitation"
            )
        
        # Create invitation
        invitation = ContactInvitation(
            sender_id=sender_id,
            recipient_id=recipient_user.id if recipient_user else None,
            contact_id=contact_id,
            event_id=event_id,
            invitation_token=str(uuid.uuid4()),
            message=message,
            invitation_type="event_invite" if event_id is not None else "app_invite",
            delivery_method=delivery_method,
            recipient_phone=contact.phone_number if delivery_method == "sms" else None,
            recipient_email=contact.email if delivery_method == "email" else None,
            status=ContactInviteStatus.PENDING
        )
        
        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)
        
        # Send SMS notification if phone number is available
        if contact.phone_number:
            self._send_invitation_sms(invitation, contact)
        
        return invitation

    def bulk_send_invitations(
        self, 
        sender_id: int, 
        contact_ids: List[int], 
        event_id: Optional[int] = None,
        message: Optional[str] = None
    ) -> List[ContactInvitation]:
        """Send invitations to multiple contacts"""
        invitations = []
        
        for contact_id in contact_ids:
            try:
                invitation = self.send_contact_invitation(
                    sender_id=sender_id,
                    contact_id=contact_id,
                    event_id=event_id,
                    message=message
                )
                invitations.append(invitation)
            except HTTPException:
                # Skip invalid contacts and continue
                continue
        
        return invitations

    def bulk_send_phone_invitations(
        self,
        sender_id: int,
        phone_numbers: List[str],
        event_id: Optional[int] = None,
        message: Optional[str] = None,
        auto_add_to_contacts: bool = False
    ) -> Dict[str, Any]:
        """Send invitations directly to phone numbers (with or without adding to contacts)
        
        Args:
            sender_id: User sending the invitations
            phone_numbers: List of phone numbers to invite
            event_id: Optional event ID for event invitations
            message: Optional custom message
            auto_add_to_contacts: If True, add phone numbers to contacts before inviting
        
        Returns:
            Dict with success/failure counts and invitation details
        """
        results = {
            "sent": [],
            "failed": [],
            "total": len(phone_numbers),
            "success_count": 0,
            "failure_count": 0
        }
        
        sender = self.db.query(User).filter(User.id == sender_id).first()
        if not sender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sender not found"
            )
        
        event = None
        if event_id:
            event = self.db.query(Event).filter(Event.id == event_id).first()
        
        for phone_number in phone_numbers:
            try:
                # Clean and validate phone number
                cleaned_phone = self._clean_phone_number(phone_number)
                if not self._is_valid_phone_number(cleaned_phone):
                    results["failed"].append({
                        "phone_number": phone_number,
                        "error": "Invalid phone number format"
                    })
                    results["failure_count"] += 1
                    continue
                
                # Check if contact exists or create one (we need a contact_id for FK)
                contact = self.db.query(UserContact).filter(
                    and_(
                        UserContact.user_id == sender_id,
                        UserContact.phone_number == cleaned_phone
                    )
                ).first()
                
                if not contact:
                    # Always create a contact record so contact_id FK is satisfied
                    contact = UserContact(
                        user_id=sender_id,
                        name=cleaned_phone,  # Use phone as name if not provided
                        phone_number=cleaned_phone,
                        source=ContactSource.PHONE,
                        is_favorite=False
                    )
                    self.db.add(contact)
                    self.db.flush()
                
                # Generate invitation token
                invitation_token = str(uuid.uuid4())
                
                # Check if phone belongs to an existing user
                recipient_user = self.db.query(User).filter(
                    User.phone_number == cleaned_phone
                ).first()
                
                # Create invitation record with required fields populated
                invitation = ContactInvitation(
                    sender_id=sender_id,
                    recipient_id=recipient_user.id if recipient_user else None,
                    contact_id=contact.id if contact else None,
                    event_id=event_id,
                    invitation_token=invitation_token,
                    message=message,
                    invitation_type="app_invite" if event_id is None else "event_invite",
                    delivery_method="sms",
                    recipient_phone=cleaned_phone,
                    status=ContactInviteStatus.PENDING
                )
                self.db.add(invitation)
                self.db.flush()
                
                # Build SMS message
                base_url = (settings.DEEP_LINK_BASE_URL or settings.FRONTEND_URL).rstrip("/")
                if event:
                    sms_message = f"Hi! {sender.full_name} invited you to '{event.title}' on PlanEtAl. Join here: {base_url}/invite/{invitation_token}"
                else:
                    sms_message = f"Hi! {sender.full_name} invited you to join PlanEtAl - the ultimate event planning app! Join here: {base_url}/invite/{invitation_token}"
                
                if message:
                    sms_message += f"\n\nPersonal message: {message}"
                
                # Send SMS via Termii (best-effort; do not crash on failure)
                try:
                    sms_result = self.sms_service.send_sms(
                        to_phone=cleaned_phone,
                        message=sms_message
                    )
                except Exception as sms_err:
                    sms_result = {"status": "failed", "error": str(sms_err)}
                
                # Update invitation status based on SMS result
                sms_status = (
                    (sms_result.get("status") or "").strip().lower()
                    if isinstance(sms_result, dict)
                    else ""
                )
                successful_sms_statuses = {"success", "sent", "queued", "accepted"}
                if sms_status in successful_sms_statuses:
                    invitation.status = ContactInviteStatus.SENT
                    results["sent"].append({
                        "phone_number": cleaned_phone,
                        "invitation_id": invitation.id,
                        "sms_status": sms_result
                    })
                    results["success_count"] += 1
                else:
                    invitation.status = ContactInviteStatus.FAILED
                    results["failed"].append({
                        "phone_number": cleaned_phone,
                        "error": sms_result.get("error") if isinstance(sms_result, dict) else "SMS delivery failed",
                        "details": sms_result
                    })
                    results["failure_count"] += 1
                
            except Exception as e:
                results["failed"].append({
                    "phone_number": phone_number,
                    "error": str(e)
                })
                results["failure_count"] += 1
        
        self.db.commit()
        return results

    def bulk_send_email_invitations(
        self,
        sender_id: int,
        emails: List[str],
        event_id: Optional[int] = None,
        message: Optional[str] = None,
        auto_add_to_contacts: bool = False
    ) -> Dict[str, Any]:
        """Send invitations directly to email addresses.

        Args:
            sender_id: User sending the invitations
            emails: List of email addresses to invite
            event_id: Optional event ID for event invitations
            message: Optional custom message
            auto_add_to_contacts: If True, save email addresses to contacts

        Returns:
            Dict with success/failure counts and invitation details
        """
        results: Dict[str, Any] = {
            "sent": [],
            "failed": [],
            "total": len(emails),
            "success_count": 0,
            "failure_count": 0,
        }

        sender = self.db.query(User).filter(User.id == sender_id).first()
        if not sender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sender not found"
            )

        event = None
        if event_id:
            event = self.db.query(Event).filter(Event.id == event_id).first()

        for email in emails:
            try:
                email = email.strip().lower()

                # Find or optionally create contact record
                contact = self.db.query(UserContact).filter(
                    and_(
                        UserContact.user_id == sender_id,
                        UserContact.email == email
                    )
                ).first()

                if not contact and auto_add_to_contacts:
                    contact = UserContact(
                        user_id=sender_id,
                        name=email,
                        email=email,
                        source=ContactSource.MANUAL,
                        is_favorite=False,
                    )
                    self.db.add(contact)
                    self.db.flush()

                if not contact:
                    # Create a temporary contact to satisfy FK constraint
                    contact = UserContact(
                        user_id=sender_id,
                        name=email,
                        email=email,
                        source=ContactSource.MANUAL,
                        is_favorite=False,
                    )
                    self.db.add(contact)
                    self.db.flush()

                invitation_token = str(uuid.uuid4())

                # Check if email belongs to an existing user
                recipient_user = self.db.query(User).filter(
                    User.email == email
                ).first()

                invitation = ContactInvitation(
                    sender_id=sender_id,
                    recipient_id=recipient_user.id if recipient_user else None,
                    contact_id=contact.id,
                    event_id=event_id,
                    invitation_token=invitation_token,
                    message=message,
                    invitation_type="app_invite" if event_id is None else "event_invite",
                    delivery_method="email",
                    recipient_email=email,
                    status=ContactInviteStatus.PENDING,
                )
                self.db.add(invitation)
                self.db.flush()

                # Send invite email (best-effort; do not crash on failure)
                sent = self.email_service.send_contact_invite_email_sync(
                    to_email=email,
                    inviter_name=sender.full_name,
                    invitation_token=invitation_token,
                    event_title=event.title if event else None,
                    message=message,
                )

                if sent:
                    invitation.status = ContactInviteStatus.SENT
                    results["sent"].append({
                        "email": email,
                        "invitation_id": invitation.id,
                    })
                    results["success_count"] += 1
                else:
                    invitation.status = ContactInviteStatus.FAILED
                    results["failed"].append({
                        "email": email,
                        "error": "Email delivery failed",
                    })
                    results["failure_count"] += 1

            except Exception as e:
                results["failed"].append({
                    "email": email,
                    "error": str(e),
                })
                results["failure_count"] += 1

        self.db.commit()
        return results

    def get_sent_invitations(
        self, 
        user_id: int,
        status: Optional[ContactInviteStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ContactInvitation]:
        """Get invitations sent by user"""
        query = self.db.query(ContactInvitation).filter(
            ContactInvitation.sender_id == user_id
        )
        
        if status:
            query = query.filter(ContactInvitation.status == status)
        
        return query.order_by(desc(ContactInvitation.created_at)).offset(offset).limit(limit).all()

    def get_received_invitations(
        self, 
        user_id: int,
        status: Optional[ContactInviteStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ContactInvitation]:
        """Get invitations received by user"""
        query = self.db.query(ContactInvitation).filter(
            ContactInvitation.recipient_id == user_id
        )
        
        if status:
            query = query.filter(ContactInvitation.status == status)
        
        return query.order_by(desc(ContactInvitation.created_at)).offset(offset).limit(limit).all()

    def respond_to_invitation(
        self, 
        invitation_id: int, 
        user_id: int, 
        rsvp_status: str
    ) -> ContactInvitation:
        """Accept or decline an invitation"""
        allowed_statuses = self._respondable_statuses()
        invitation = self.db.query(ContactInvitation).filter(
            and_(
                ContactInvitation.id == invitation_id,
                ContactInvitation.recipient_id == user_id,
                ContactInvitation.status.in_(allowed_statuses)
            )
        ).first()

        if not invitation:
            invitation = self.db.query(ContactInvitation).filter(
                and_(
                    ContactInvitation.event_id == invitation_id,
                    ContactInvitation.recipient_id == user_id,
                    ContactInvitation.status.in_(allowed_statuses)
                )
            ).order_by(desc(ContactInvitation.created_at)).first()
        
        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found or already responded"
            )
        
        # Map rsvp_status to ContactInviteStatus
        if rsvp_status == "accepted":
            invitation.status = ContactInviteStatus.ACCEPTED
        elif rsvp_status == "declined":
            invitation.status = ContactInviteStatus.DECLINED
        
        invitation.responded_at = datetime.utcnow()
        invitation.recipient_id = user_id  # Ensure recipient is linked

        # If event_id exists, create/update EventInvitation to ensure it appears in upcoming events
        if invitation.event_id:
            # Check if EventInvitation already exists
            event_invite = self.db.query(EventInvitation).filter(
                and_(
                    EventInvitation.event_id == invitation.event_id,
                    EventInvitation.user_id == user_id
                )
            ).first()
            
            # Map rsvp_status to RSVPStatus (for event invitation)
            event_rsvp_status = RSVPStatus.ACCEPTED if rsvp_status == "accepted" else RSVPStatus.DECLINED
            
            if not event_invite:
                event_invite = EventInvitation(
                    event_id=invitation.event_id,
                    user_id=user_id,
                    rsvp_status=event_rsvp_status,
                    invited_at=invitation.created_at,
                    responded_at=datetime.utcnow()
                )
                self.db.add(event_invite)
            else:
                # Update existing invitation status
                event_invite.rsvp_status = event_rsvp_status
                event_invite.responded_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(invitation)
        
        return invitation

    def respond_to_invitation_token(
        self,
        token: str,
        user_id: int,
        rsvp_status: str
    ) -> ContactInvitation:
        allowed_statuses = set(self._respondable_statuses())
        pre_response_statuses = {
            ContactInviteStatus.PENDING,
            ContactInviteStatus.SENT,
            ContactInviteStatus.DELIVERED,
            ContactInviteStatus.OPENED
        }
        invitation = self.db.query(ContactInvitation).filter(
            ContactInvitation.invitation_token == token
        ).first()

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite not found"
            )

        if invitation.status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found or already responded"
            )

        is_expired = invitation.expires_at is not None and invitation.expires_at < datetime.utcnow()
        if is_expired:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invite has expired"
            )

        if (
            invitation.recipient_id is not None
            and invitation.recipient_id != user_id
            and invitation.status not in pre_response_statuses
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to respond to this invite"
            )

        if rsvp_status == "accepted":
            invitation.status = ContactInviteStatus.ACCEPTED
        elif rsvp_status == "declined":
            invitation.status = ContactInviteStatus.DECLINED

        invitation.responded_at = datetime.utcnow()
        invitation.recipient_id = user_id

        if invitation.event_id:
            event_invite = self.db.query(EventInvitation).filter(
                and_(
                    EventInvitation.event_id == invitation.event_id,
                    EventInvitation.user_id == user_id
                )
            ).first()

            event_rsvp_status = RSVPStatus.ACCEPTED if rsvp_status == "accepted" else RSVPStatus.DECLINED

            if not event_invite:
                event_invite = EventInvitation(
                    event_id=invitation.event_id,
                    user_id=user_id,
                    rsvp_status=event_rsvp_status,
                    invited_at=invitation.created_at,
                    responded_at=datetime.utcnow()
                )
                self.db.add(event_invite)
            else:
                event_invite.rsvp_status = event_rsvp_status
                event_invite.responded_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(invitation)
        return invitation

    def create_contact_group(
        self, 
        user_id: int, 
        name: str, 
        description: Optional[str] = None
    ) -> ContactGroup:
        """Create a new contact group"""
        # Check if group name already exists for user
        existing_group = self.db.query(ContactGroup).filter(
            and_(
                ContactGroup.user_id == user_id,
                ContactGroup.name == name
            )
        ).first()
        
        if existing_group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact group with this name already exists"
            )
        
        group = ContactGroup(
            user_id=user_id,
            name=name,
            description=description
        )
        
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        return group

    def add_contact_to_group(self, user_id: int, group_id: int, contact_id: int) -> ContactGroupMembership:
        """Add contact to a group"""
        # Verify group belongs to user
        group = self.db.query(ContactGroup).filter(
            and_(
                ContactGroup.id == group_id,
                ContactGroup.user_id == user_id
            )
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact group not found"
            )
        
        # Verify contact belongs to user
        contact = self.db.query(UserContact).filter(
            and_(
                UserContact.id == contact_id,
                UserContact.user_id == user_id
            )
        ).first()
        
        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found"
            )
        
        # Check if already in group
        existing_membership = self.db.query(ContactGroupMembership).filter(
            and_(
                ContactGroupMembership.group_id == group_id,
                ContactGroupMembership.contact_id == contact_id
            )
        ).first()
        
        if existing_membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact is already in this group"
            )
        
        membership = ContactGroupMembership(
            group_id=group_id,
            contact_id=contact_id
        )
        
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def _is_valid_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format using international standards"""
        try:
            normalized = self._clean_phone_number(phone_number)
            parsed = phonenumbers.parse(normalized, None)
            if phonenumbers.is_valid_number(parsed):
                return True
            return phonenumbers.is_possible_number(parsed)
        except (NumberParseException, ValueError):
            return False
    
    def _clean_phone_number(self, phone_number: str) -> str:
        """Clean and standardize phone number to international E.164 format
        
        Supports international numbers from any country. Examples:
        - UK: +447700900123 or 07700 900123
        - Nigeria: +2348012345678 or 08012345678
        - US: +11234567890 or (123) 456-7890
        - etc.
        
        Returns E.164 format (e.g., +447700900123) suitable for SMS delivery.
        """
        cleaned = re.sub(r"[^\d+]", "", str(phone_number).strip())
        if cleaned.startswith("+"):
            parsed = phonenumbers.parse(cleaned, None)
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

        digits = re.sub(r"[^\d]", "", cleaned)
        if digits.startswith("234"):
            parsed = phonenumbers.parse(f"+{digits}", None)
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

        if len(digits) == 11 and digits.startswith("0") and digits[1] in {"7", "8", "9"}:
            return f"+234{digits[1:]}"

        raise ValueError("Phone number must include country code (E.164) for non-Nigeria local formats")

    def _send_invitation_sms(self, invitation: ContactInvitation, contact: UserContact):
        """Send SMS invitation to contact"""
        try:
            sender = self.db.query(User).filter(User.id == invitation.sender_id).first()
            
            base_url = (settings.DEEP_LINK_BASE_URL or settings.FRONTEND_URL).rstrip("/")
            if invitation.event_id:
                event = self.db.query(Event).filter(Event.id == invitation.event_id).first()
                message = f"Hi! {sender.first_name} {sender.last_name} invited you to '{event.title}' on PlanEtAl. Join here: {base_url}/invite/{invitation.invitation_token}"
            else:
                message = f"Hi! {sender.first_name} {sender.last_name} invited you to join PlanEtAl - the ultimate event planning app! Join here: {base_url}/invite/{invitation.invitation_token}"
            
            if invitation.message:
                message += f"\n\nPersonal message: {invitation.message}"
            
            self.sms_service.send_sms(
                to_phone=contact.phone_number,
                message=message
            )
        except Exception as e:
            # Log error but don't fail the invitation creation
            print(f"Failed to send SMS invitation: {str(e)}")
