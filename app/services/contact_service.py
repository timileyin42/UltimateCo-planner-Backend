from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from datetime import datetime, timedelta
import uuid
import re
from fastapi import HTTPException, status

from app.models.contact_models import (
    UserContact, ContactInvitation, ContactGroup, ContactGroupMembership,
    InvitationStatus
)
from app.models.user_models import User
from app.models.event_models import Event
from app.core.database import get_db
from app.services.sms_service import SMSService


class ContactService:
    def __init__(self, db: Session):
        self.db = db
        self.sms_service = SMSService()

    def add_contact(self, user_id: int, contact_data: Dict[str, Any]) -> UserContact:
        """Add a new contact to user's contact list"""
        # Validate phone number format
        phone_number = contact_data.get('phone_number')
        if phone_number and not self._is_valid_phone_number(phone_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone number format"
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
            first_name=contact_data.get('first_name'),
            last_name=contact_data.get('last_name'),
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
                    UserContact.first_name.ilike(search_term),
                    UserContact.last_name.ilike(search_term),
                    UserContact.phone_number.ilike(search_term),
                    UserContact.email.ilike(search_term)
                )
            )
        
        if favorites_only:
            query = query.filter(UserContact.is_favorite == True)
        
        return query.order_by(UserContact.first_name).offset(offset).limit(limit).all()

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
        
        # Create invitation
        invitation = ContactInvitation(
            sender_id=sender_id,
            recipient_id=recipient_user.id if recipient_user else None,
            contact_id=contact_id,
            event_id=event_id,
            invitation_token=str(uuid.uuid4()),
            message=message,
            status=InvitationStatus.PENDING
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

    def get_sent_invitations(
        self, 
        user_id: int,
        status: Optional[InvitationStatus] = None,
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
        status: Optional[InvitationStatus] = None,
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
        accept: bool
    ) -> ContactInvitation:
        """Accept or decline an invitation"""
        invitation = self.db.query(ContactInvitation).filter(
            and_(
                ContactInvitation.id == invitation_id,
                ContactInvitation.recipient_id == user_id,
                ContactInvitation.status == InvitationStatus.PENDING
            )
        ).first()
        
        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found or already responded"
            )
        
        invitation.status = InvitationStatus.ACCEPTED if accept else InvitationStatus.DECLINED
        invitation.responded_at = datetime.utcnow()
        
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
        """Validate phone number format"""
        # Basic phone number validation (can be enhanced)
        phone_pattern = r'^\+?[\d\s\-\(\)]{10,15}$'
        return bool(re.match(phone_pattern, phone_number))

    def _send_invitation_sms(self, invitation: ContactInvitation, contact: UserContact):
        """Send SMS invitation to contact"""
        try:
            sender = self.db.query(User).filter(User.id == invitation.sender_id).first()
            
            if invitation.event_id:
                event = self.db.query(Event).filter(Event.id == invitation.event_id).first()
                message = f"Hi! {sender.first_name} {sender.last_name} invited you to '{event.title}' on PlanEtAl. Join here: https://planetal.app/invite/{invitation.invitation_token}"
            else:
                message = f"Hi! {sender.first_name} {sender.last_name} invited you to join PlanEtAl - the ultimate event planning app! Join here: https://planetal.app/invite/{invitation.invitation_token}"
            
            if invitation.message:
                message += f"\n\nPersonal message: {invitation.message}"
            
            self.sms_service.send_sms(
                to_phone=contact.phone_number,
                message=message
            )
        except Exception as e:
            # Log error but don't fail the invitation creation
            print(f"Failed to send SMS invitation: {str(e)}")