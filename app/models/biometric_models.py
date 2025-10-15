from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
from app.models.shared_models import BaseModel, TimestampMixin
import enum

class BiometricType(str, enum.Enum):
    """Biometric authentication type enumeration"""
    FACE_ID = "face_id"
    FINGERPRINT = "fingerprint"
    VOICE = "voice"
    IRIS = "iris"

class DeviceType(str, enum.Enum):
    """Device type enumeration"""
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"
    DESKTOP = "desktop"

class BiometricStatus(str, enum.Enum):
    """Biometric authentication status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"

class UserDevice(BaseModel, TimestampMixin):
    """User devices for biometric authentication"""
    __tablename__ = "biometric_devices"
    
    # Device info
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)
    device_type: Mapped[DeviceType] = mapped_column(SQLEnum(DeviceType), nullable=False)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Unique device identifier
    device_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    os_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    app_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Device fingerprinting
    device_fingerprint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object
    
    # Security info
    is_trusted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Usage tracking
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    login_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Location info (optional)
    last_known_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Relationships
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="devices")
    biometric_auths = relationship("BiometricAuth", back_populates="device", cascade="all, delete-orphan")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_user_device_user_id', 'user_id'),
        Index('idx_user_device_device_id', 'device_id'),
        Index('idx_user_device_type', 'device_type'),
        Index('idx_user_device_trusted', 'is_trusted'),
        Index('idx_user_device_active', 'is_active'),
        Index('idx_user_device_last_used', 'last_used_at'),
        Index('idx_user_device_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_user_device_user_type', 'user_id', 'device_type'),
        Index('idx_user_device_user_active', 'user_id', 'is_active'),
        Index('idx_user_device_user_trusted', 'user_id', 'is_trusted'),
        Index('idx_user_device_device_user', 'device_id', 'user_id'),
    )
    
    def __repr__(self):
        return f"<UserDevice(id={self.id}, name='{self.device_name}', type='{self.device_type}')>"

class BiometricAuth(BaseModel, TimestampMixin):
    """Biometric authentication configurations"""
    __tablename__ = "biometric_auths"
    
    # Biometric info
    biometric_type: Mapped[BiometricType] = mapped_column(SQLEnum(BiometricType), nullable=False)
    biometric_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Hashed biometric identifier
    
    # Authentication settings
    status: Mapped[BiometricStatus] = mapped_column(SQLEnum(BiometricStatus), default=BiometricStatus.ACTIVE)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Security settings
    requires_passcode_fallback: Mapped[bool] = mapped_column(Boolean, default=True)
    max_failed_attempts: Mapped[int] = mapped_column(Integer, default=5)
    current_failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    
    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Usage tracking
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Metadata
    enrollment_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON metadata
    
    # Relationships
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    device_id: Mapped[int] = mapped_column(ForeignKey("biometric_devices.id"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="biometric_auths")
    device = relationship("UserDevice", back_populates="biometric_auths")
    auth_attempts = relationship("BiometricAuthAttempt", back_populates="biometric_auth", cascade="all, delete-orphan")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_biometric_auth_user_id', 'user_id'),
        Index('idx_biometric_auth_device_id', 'device_id'),
        Index('idx_biometric_auth_type', 'biometric_type'),
        Index('idx_biometric_auth_biometric_id', 'biometric_id'),
        Index('idx_biometric_auth_status', 'status'),
        Index('idx_biometric_auth_primary', 'is_primary'),
        Index('idx_biometric_auth_expires_at', 'expires_at'),
        Index('idx_biometric_auth_last_used', 'last_used_at'),
        Index('idx_biometric_auth_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_biometric_auth_user_type', 'user_id', 'biometric_type'),
        Index('idx_biometric_auth_user_status', 'user_id', 'status'),
        Index('idx_biometric_auth_device_type', 'device_id', 'biometric_type'),
        Index('idx_biometric_auth_user_primary', 'user_id', 'is_primary'),
        Index('idx_biometric_auth_type_status', 'biometric_type', 'status'),
    )
    
    def __repr__(self):
        return f"<BiometricAuth(id={self.id}, type='{self.biometric_type}', status='{self.status}')>"
    
    @property
    def is_expired(self) -> bool:
        """Check if the biometric auth is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_locked(self) -> bool:
        """Check if the biometric auth is locked due to failed attempts"""
        return self.current_failed_attempts >= self.max_failed_attempts
    
    @property
    def is_usable(self) -> bool:
        """Check if the biometric auth can be used"""
        return (
            self.status == BiometricStatus.ACTIVE and
            not self.is_expired and
            not self.is_locked
        )

class BiometricAuthAttempt(BaseModel, TimestampMixin):
    """Biometric authentication attempts for security tracking"""
    __tablename__ = "biometric_auth_attempts"
    
    # Attempt info
    was_successful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Security info
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Timing info
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Relationships
    biometric_auth_id: Mapped[int] = mapped_column(ForeignKey("biometric_auths.id"), nullable=False)
    
    # Relationships
    biometric_auth = relationship("BiometricAuth", back_populates="auth_attempts")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_biometric_attempt_auth_id', 'biometric_auth_id'),
        Index('idx_biometric_attempt_successful', 'was_successful'),
        Index('idx_biometric_attempt_ip', 'ip_address'),
        Index('idx_biometric_attempt_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_biometric_attempt_auth_success', 'biometric_auth_id', 'was_successful'),
        Index('idx_biometric_attempt_auth_created', 'biometric_auth_id', 'created_at'),
        Index('idx_biometric_attempt_ip_created', 'ip_address', 'created_at'),
    )
    
    def __repr__(self):
        return f"<BiometricAuthAttempt(id={self.id}, successful={self.was_successful})>"

class BiometricToken(BaseModel, TimestampMixin):
    """Temporary tokens for biometric authentication flow"""
    __tablename__ = "biometric_tokens"
    
    # Token info
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    token_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'challenge', 'verification'
    
    # Token data
    challenge_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON challenge data
    
    # Expiration
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Usage tracking
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("biometric_devices.id"), nullable=True)
    
    # Relationships
    user = relationship("User")
    device = relationship("UserDevice")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_biometric_token_token', 'token'),
        Index('idx_biometric_token_user_id', 'user_id'),
        Index('idx_biometric_token_device_id', 'device_id'),
        Index('idx_biometric_token_type', 'token_type'),
        Index('idx_biometric_token_expires_at', 'expires_at'),
        Index('idx_biometric_token_used', 'is_used'),
        Index('idx_biometric_token_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_biometric_token_user_type', 'user_id', 'token_type'),
        Index('idx_biometric_token_token_used', 'token', 'is_used'),
        Index('idx_biometric_token_user_expires', 'user_id', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<BiometricToken(id={self.id}, type='{self.token_type}', used={self.is_used})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if the token is expired"""
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if the token is valid (not used and not expired)"""
        return not self.is_used and not self.is_expired