from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
from app.models.shared_models import BaseModel, TimestampMixin
import enum

class ContactSource(str, enum.Enum):
    """Contact source enumeration"""
    PHONE = "phone"
    EMAIL = "email"
    MANUAL = "manual"
    IMPORTED = "imported"

class ContactInviteStatus(str, enum.Enum):
    """Contact invitation status enumeration"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    FAILED = "failed"

class UserContact(BaseModel, TimestampMixin):
    """User contacts for invite system"""
    __tablename__ = "user_contacts"
    
    # Contact info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Contact metadata
    source: Mapped[ContactSource] = mapped_column(SQLEnum(ContactSource), default=ContactSource.MANUAL)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Contact grouping
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Relationships
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    owner = relationship("User", back_populates="contacts")
    invitations = relationship("ContactInvitation", back_populates="contact", cascade="all, delete-orphan")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_user_contact_user_id', 'user_id'),
        Index('idx_user_contact_phone', 'phone_number'),
        Index('idx_user_contact_email', 'email'),
        Index('idx_user_contact_source', 'source'),
        Index('idx_user_contact_favorite', 'is_favorite'),
        Index('idx_user_contact_name', 'name'),
        Index('idx_user_contact_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_user_contact_user_source', 'user_id', 'source'),
        Index('idx_user_contact_user_favorite', 'user_id', 'is_favorite'),
        Index('idx_user_contact_user_name', 'user_id', 'name'),
        Index('idx_user_contact_phone_user', 'phone_number', 'user_id'),
        Index('idx_user_contact_email_user', 'email', 'user_id'),
    )
    
    def __repr__(self):
        return f"<UserContact(id={self.id}, name='{self.name}', user_id={self.user_id})>"

class ContactInvitation(BaseModel, TimestampMixin):
    """Contact invitations sent via SMS/Email"""
    __tablename__ = "contact_invitations"
    
    # Invitation details
    invitation_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'app_invite', 'event_invite'
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    custom_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Delivery info
    delivery_method: Mapped[str] = mapped_column(String(20), nullable=False)  # 'sms', 'email'
    recipient_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Status tracking
    status: Mapped[ContactInviteStatus] = mapped_column(SQLEnum(ContactInviteStatus), default=ContactInviteStatus.PENDING)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Tracking info
    tracking_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # SMS/Email provider tracking ID
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    contact_id: Mapped[int] = mapped_column(ForeignKey("user_contacts.id"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True)  # For event invites
    
    # Relationships
    contact = relationship("UserContact", back_populates="invitations")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_contact_invitations")
    event = relationship("Event", back_populates="contact_invitations")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_contact_invitation_contact_id', 'contact_id'),
        Index('idx_contact_invitation_sender_id', 'sender_id'),
        Index('idx_contact_invitation_event_id', 'event_id'),
        Index('idx_contact_invitation_type', 'invitation_type'),
        Index('idx_contact_invitation_method', 'delivery_method'),
        Index('idx_contact_invitation_status', 'status'),
        Index('idx_contact_invitation_phone', 'recipient_phone'),
        Index('idx_contact_invitation_email', 'recipient_email'),
        Index('idx_contact_invitation_sent_at', 'sent_at'),
        Index('idx_contact_invitation_expires_at', 'expires_at'),
        Index('idx_contact_invitation_tracking_id', 'tracking_id'),
        Index('idx_contact_invitation_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_contact_invitation_sender_status', 'sender_id', 'status'),
        Index('idx_contact_invitation_contact_status', 'contact_id', 'status'),
        Index('idx_contact_invitation_event_status', 'event_id', 'status'),
        Index('idx_contact_invitation_type_status', 'invitation_type', 'status'),
        Index('idx_contact_invitation_method_status', 'delivery_method', 'status'),
        Index('idx_contact_invitation_sender_created', 'sender_id', 'created_at'),
        Index('idx_contact_invitation_phone_status', 'recipient_phone', 'status'),
        Index('idx_contact_invitation_email_status', 'recipient_email', 'status'),
    )
    
    def __repr__(self):
        return f"<ContactInvitation(id={self.id}, type='{self.invitation_type}', status='{self.status}')>"
    
    @property
    def is_expired(self) -> bool:
        """Check if the invitation is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_deliverable(self) -> bool:
        """Check if invitation can be delivered"""
        return (
            self.status == ContactInviteStatus.PENDING and
            not self.is_expired and
            (self.recipient_phone or self.recipient_email)
        )

class ContactGroup(BaseModel, TimestampMixin):
    """Contact groups for organizing contacts"""
    __tablename__ = "contact_groups"
    
    # Group info
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color
    
    # Group settings
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    owner = relationship("User", back_populates="contact_groups")
    memberships = relationship("ContactGroupMembership", back_populates="group", cascade="all, delete-orphan")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_contact_group_user_id', 'user_id'),
        Index('idx_contact_group_name', 'name'),
        Index('idx_contact_group_default', 'is_default'),
        Index('idx_contact_group_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_contact_group_user_name', 'user_id', 'name'),
        Index('idx_contact_group_user_default', 'user_id', 'is_default'),
    )
    
    def __repr__(self):
        return f"<ContactGroup(id={self.id}, name='{self.name}', user_id={self.user_id})>"

class ContactGroupMembership(BaseModel, TimestampMixin):
    """Many-to-many relationship between contacts and groups"""
    __tablename__ = "contact_group_memberships"
    
    # Relationships
    contact_id: Mapped[int] = mapped_column(ForeignKey("user_contacts.id"), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("contact_groups.id"), nullable=False)
    
    # Relationships
    contact = relationship("UserContact")
    group = relationship("ContactGroup", back_populates="memberships")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_contact_group_membership_contact', 'contact_id'),
        Index('idx_contact_group_membership_group', 'group_id'),
        Index('idx_contact_group_membership_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_contact_group_membership_contact_group', 'contact_id', 'group_id'),
    )
    
    def __repr__(self):
        return f"<ContactGroupMembership(contact_id={self.contact_id}, group_id={self.group_id})>"