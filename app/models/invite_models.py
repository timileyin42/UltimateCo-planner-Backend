from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Text, Index
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.shared_models import TimestampMixin, SoftDeleteMixin, ActiveMixin, IDMixin

class InviteType(str, Enum):
    """Invite type enumeration"""
    USER_PROFILE = "user_profile"
    APP_GENERAL = "app_general"
    EVENT = "event"
    FRIEND_REQUEST = "friend_request"

class InviteCode(Base, IDMixin, TimestampMixin, SoftDeleteMixin, ActiveMixin):
    """Invite code model for QR codes and short codes"""
    __tablename__ = "invite_codes"
    
    # Core fields
    code = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False, index=True)
    invite_type = Column(String(50), nullable=False, index=True)
    
    # Expiration and usage tracking
    expires_at = Column(DateTime, nullable=True)
    used_at = Column(DateTime, nullable=True)
    used_by_user_id = Column(ForeignKey("users.id"), nullable=True)
    
    # Optional metadata
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # QR code specific fields
    qr_code_url = Column(String(500), nullable=True)  # URL to generated QR code image
    
    # Relationships
    creator = relationship("User", foreign_keys=[user_id], back_populates="created_invite_codes")
    used_by = relationship("User", foreign_keys=[used_by_user_id], back_populates="used_invite_codes")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_invite_codes_code', 'code'),
        Index('idx_invite_codes_user_id', 'user_id'),
        Index('idx_invite_codes_type', 'invite_type'),
        Index('idx_invite_codes_expires_at', 'expires_at'),
        Index('idx_invite_codes_used_at', 'used_at'),
        Index('idx_invite_codes_active', 'is_active'),
        Index('idx_invite_codes_deleted', 'is_deleted'),
        # Combined indexes for common queries
        Index('idx_invite_codes_user_type', 'user_id', 'invite_type'),
        Index('idx_invite_codes_active_expires', 'is_active', 'expires_at'),
        Index('idx_invite_codes_type_active', 'invite_type', 'is_active'),
    )
    
    def __repr__(self):
        return f"<InviteCode(id={self.id}, code='{self.code}', type='{self.invite_type}')>"
    
    @property
    def is_expired(self) -> bool:
        """Check if the invite code is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_used(self) -> bool:
        """Check if the invite code has been used"""
        return self.used_at is not None
    
    @property
    def is_valid(self) -> bool:
        """Check if the invite code is valid (active, not expired, not used)"""
        return self.is_active and not self.is_expired and not self.is_used and not self.is_deleted

class InviteLink(Base, IDMixin, TimestampMixin, SoftDeleteMixin, ActiveMixin):
    """Invite link model for shareable links with usage tracking"""
    __tablename__ = "invite_links"
    
    # Core fields
    link_id = Column(String(100), unique=True, index=True, nullable=False)  # URL-safe identifier
    user_id = Column(ForeignKey("users.id"), nullable=False, index=True)
    
    # Link metadata
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Usage limits and tracking
    expires_at = Column(DateTime, nullable=True)
    max_uses = Column(Integer, nullable=True)  # NULL means unlimited
    current_uses = Column(Integer, default=0, nullable=False)
    
    # Link type and customization
    invite_type = Column(String(50), nullable=False, index=True)
    custom_message = Column(Text, nullable=True)
    
    # Relationships
    creator = relationship("User", foreign_keys=[user_id], back_populates="created_invite_links")
    usages = relationship("InviteLinkUsage", back_populates="invite_link", cascade="all, delete-orphan")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_invite_links_link_id', 'link_id'),
        Index('idx_invite_links_user_id', 'user_id'),
        Index('idx_invite_links_type', 'invite_type'),
        Index('idx_invite_links_expires_at', 'expires_at'),
        Index('idx_invite_links_active', 'is_active'),
        Index('idx_invite_links_deleted', 'is_deleted'),
        Index('idx_invite_links_current_uses', 'current_uses'),
        # Combined indexes for common queries
        Index('idx_invite_links_user_type', 'user_id', 'invite_type'),
        Index('idx_invite_links_active_expires', 'is_active', 'expires_at'),
        Index('idx_invite_links_type_active', 'invite_type', 'is_active'),
    )
    
    def __repr__(self):
        return f"<InviteLink(id={self.id}, link_id='{self.link_id}', title='{self.title}')>"
    
    @property
    def is_expired(self) -> bool:
        """Check if the invite link is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_usage_exceeded(self) -> bool:
        """Check if the invite link has exceeded its usage limit"""
        if not self.max_uses:
            return False
        return self.current_uses >= self.max_uses
    
    @property
    def is_valid(self) -> bool:
        """Check if the invite link is valid (active, not expired, usage not exceeded)"""
        return self.is_active and not self.is_expired and not self.is_usage_exceeded and not self.is_deleted
    
    @property
    def remaining_uses(self) -> int | None:
        """Get remaining uses for the invite link"""
        if not self.max_uses:
            return None
        return max(0, self.max_uses - self.current_uses)

class InviteLinkUsage(Base, IDMixin, TimestampMixin):
    """Track usage of invite links"""
    __tablename__ = "invite_link_usages"
    
    # Core fields
    invite_link_id = Column(ForeignKey("invite_links.id"), nullable=False, index=True)
    used_by_user_id = Column(ForeignKey("users.id"), nullable=True)  # NULL for anonymous usage
    
    # Usage metadata
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    referrer = Column(String(500), nullable=True)
    
    # Success tracking
    was_successful = Column(Boolean, default=True, nullable=False)
    failure_reason = Column(String(255), nullable=True)
    
    # Relationships
    invite_link = relationship("InviteLink", back_populates="usages")
    used_by = relationship("User", foreign_keys=[used_by_user_id], back_populates="invite_link_usages")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_invite_link_usages_link_id', 'invite_link_id'),
        Index('idx_invite_link_usages_user_id', 'used_by_user_id'),
        Index('idx_invite_link_usages_created_at', 'created_at'),
        Index('idx_invite_link_usages_successful', 'was_successful'),
        Index('idx_invite_link_usages_ip', 'ip_address'),
        # Combined indexes for common queries
        Index('idx_invite_link_usages_link_created', 'invite_link_id', 'created_at'),
        Index('idx_invite_link_usages_user_created', 'used_by_user_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<InviteLinkUsage(id={self.id}, invite_link_id={self.invite_link_id}, successful={self.was_successful})>"