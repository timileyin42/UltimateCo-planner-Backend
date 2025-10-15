from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declared_attr
from app.db.base import Base


class BaseModel(Base):
    """Base model class with common functionality"""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    def soft_delete(self):
        """Mark record as deleted"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()


class EventType(str, Enum):
    """Event type enumeration"""
    BIRTHDAY = "birthday"
    WEDDING = "wedding"
    GRADUATION = "graduation"
    DINNER = "dinner"
    PARTY = "party"
    BABY_SHOWER = "baby_shower"
    REUNION = "reunion"
    CORPORATE = "corporate"
    BRAND_ACTIVATION = "brand_activation"
    TRIP = "trip"
    OTHER = "other"

class EventStatus(str, Enum):
    """Event status enumeration"""
    DRAFT = "draft"
    PLANNING = "planning"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class RSVPStatus(str, Enum):
    """RSVP status enumeration"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    MAYBE = "maybe"

class TaskStatus(str, Enum):
    """Task status enumeration"""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TaskPriority(str, Enum):
    """Task priority enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class MediaType(str, Enum):
    """Media type enumeration"""
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"

class NotificationType(str, Enum):
    """Notification type enumeration"""
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    IN_APP = "in_app"

class TimestampMixin:
    """Mixin for adding timestamp fields"""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=datetime.utcnow, nullable=False)
    
    @declared_attr
    def updated_at(cls):
        return Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    
    @declared_attr
    def is_deleted(cls):
        return Column(Boolean, default=False, nullable=False)
    
    @declared_attr
    def deleted_at(cls):
        return Column(DateTime, nullable=True)
    
    def soft_delete(self):
        """Mark record as deleted"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()

class ActiveMixin:
    """Mixin for active/inactive status"""
    
    @declared_attr
    def is_active(cls):
        return Column(Boolean, default=True, nullable=False)

class IDMixin:
    """Mixin for primary key ID"""
    
    @declared_attr
    def id(cls):
        return Column(Integer, primary_key=True, index=True, autoincrement=True)