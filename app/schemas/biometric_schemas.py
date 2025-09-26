from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.models.biometric_models import BiometricType, DeviceType, BiometricStatus


class DeviceRegistrationRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=255)
    device_name: str = Field(..., min_length=1, max_length=100)
    device_type: DeviceType
    os_version: Optional[str] = Field(None, max_length=50)
    app_version: Optional[str] = Field(None, max_length=20)


class DeviceResponse(BaseModel):
    id: int
    user_id: int
    device_id: str
    device_name: str
    device_type: DeviceType
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BiometricSetupRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=255)
    biometric_type: BiometricType
    public_key: str = Field(..., min_length=1)
    biometric_template_hash: Optional[str] = Field(None, max_length=255)

    @validator('public_key')
    def validate_public_key(cls, v):
        # Basic validation - in production, validate actual key format
        if len(v) < 50:
            raise ValueError('Public key too short')
        return v


class BiometricAuthResponse(BaseModel):
    id: int
    user_id: int
    device_id: str
    biometric_type: BiometricType
    status: BiometricStatus
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BiometricAuthenticationRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=255)
    biometric_type: BiometricType
    biometric_signature: str = Field(..., min_length=1)
    challenge: str = Field(..., min_length=1)
    user_identifier: Optional[str] = Field(None, description="Email or username for additional verification")

    @validator('biometric_signature')
    def validate_signature(cls, v):
        # Basic validation for base64 encoded signature
        import base64
        try:
            base64.b64decode(v)
        except Exception:
            raise ValueError('Invalid biometric signature format')
        return v

    @validator('challenge')
    def validate_challenge(cls, v):
        # Basic validation for base64 encoded challenge
        import base64
        try:
            base64.b64decode(v)
        except Exception:
            raise ValueError('Invalid challenge format')
        return v


class BiometricAuthenticationResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    biometric_token: str
    expires_in: int
    user: dict


class AuthChallengeResponse(BaseModel):
    challenge: str
    expires_at: datetime


class BiometricTokenResponse(BaseModel):
    id: int
    user_id: int
    device_id: str
    biometric_type: BiometricType
    token: str
    created_at: datetime
    expires_at: datetime
    is_active: bool
    last_used_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BiometricAuthAttemptResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    device_id: str
    biometric_type: BiometricType
    success: bool
    failure_reason: Optional[str] = None
    attempted_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    model_config = {"from_attributes": True}


class DisableBiometricRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=255)
    biometric_type: Optional[BiometricType] = None


class RevokeDeviceRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=255)


class BiometricStatsResponse(BaseModel):
    total_devices: int
    active_devices: int
    total_biometric_auths: int
    active_biometric_auths: int
    successful_attempts_today: int
    failed_attempts_today: int
    last_successful_login: Optional[datetime] = None


class DeviceListResponse(BaseModel):
    devices: List[DeviceResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class BiometricAuthListResponse(BaseModel):
    biometric_auths: List[BiometricAuthResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class AuthAttemptListResponse(BaseModel):
    attempts: List[BiometricAuthAttemptResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class BiometricTokenListResponse(BaseModel):
    tokens: List[BiometricTokenResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class BiometricHealthCheckResponse(BaseModel):
    device_id: str
    biometric_type: BiometricType
    status: BiometricStatus
    last_used: Optional[datetime] = None
    is_healthy: bool
    issues: List[str] = []


class UpdateDeviceRequest(BaseModel):
    device_name: Optional[str] = Field(None, min_length=1, max_length=100)
    os_version: Optional[str] = Field(None, max_length=50)
    app_version: Optional[str] = Field(None, max_length=20)


class BiometricConfigResponse(BaseModel):
    supported_types: List[BiometricType]
    max_devices_per_user: int
    token_expiry_hours: int
    challenge_expiry_minutes: int
    max_failed_attempts: int
    lockout_duration_minutes: int