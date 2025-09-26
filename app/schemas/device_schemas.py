from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from app.models.notification_models import DevicePlatform


class DeviceRegistrationRequest(BaseModel):
    """Schema for device registration request."""
    device_token: str = Field(..., description="FCM device token")
    device_id: str = Field(..., description="Unique device identifier")
    platform: DevicePlatform = Field(..., description="Device platform (iOS, Android, Web)")
    device_name: Optional[str] = Field(None, description="Human-readable device name")
    app_version: Optional[str] = Field(None, description="App version")
    os_version: Optional[str] = Field(None, description="Operating system version")

    @validator('device_token')
    def validate_device_token(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Device token cannot be empty')
        return v.strip()

    @validator('device_id')
    def validate_device_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Device ID cannot be empty')
        return v.strip()


class DeviceUpdateRequest(BaseModel):
    """Schema for device update request."""
    device_token: Optional[str] = Field(None, description="Updated FCM device token")
    device_name: Optional[str] = Field(None, description="Updated device name")
    app_version: Optional[str] = Field(None, description="Updated app version")
    os_version: Optional[str] = Field(None, description="Updated OS version")
    is_active: Optional[bool] = Field(None, description="Device active status")


class DeviceResponse(BaseModel):
    """Schema for device response."""
    id: int
    device_token: str
    device_id: str
    platform: DevicePlatform
    device_name: Optional[str]
    app_version: Optional[str]
    os_version: Optional[str]
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeviceListResponse(BaseModel):
    """Schema for device list response."""
    devices: List[DeviceResponse]
    total: int


class PushNotificationRequest(BaseModel):
    """Schema for sending push notifications."""
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification body")
    data: Optional[dict] = Field(None, description="Additional data payload")
    device_tokens: Optional[List[str]] = Field(None, description="Specific device tokens to send to")
    user_ids: Optional[List[int]] = Field(None, description="User IDs to send notifications to")
    topic: Optional[str] = Field(None, description="FCM topic to send to")

    @validator('title')
    def validate_title(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Title cannot be empty')
        return v.strip()

    @validator('body')
    def validate_body(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Body cannot be empty')
        return v.strip()


class PushNotificationResponse(BaseModel):
    """Schema for push notification response."""
    success: bool
    message: str
    success_count: Optional[int] = None
    failure_count: Optional[int] = None
    failed_tokens: Optional[List[str]] = None