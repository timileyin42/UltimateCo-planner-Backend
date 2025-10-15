from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from app.models.invite_models import InviteType


class InviteCodeBase(BaseModel):
    """Base schema for invite codes"""
    invite_type: InviteType = Field(default=InviteType.APP_GENERAL, description="Type of invite")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    

class InviteCodeCreate(InviteCodeBase):
    """Schema for creating invite codes"""
    pass


class InviteCodeResponse(InviteCodeBase):
    """Schema for invite code responses"""
    id: int
    code: str
    user_id: int
    used_at: Optional[datetime] = None
    used_by_user_id: Optional[int] = None
    created_at: datetime
    is_active: bool
    qr_code_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class InviteLinkBase(BaseModel):
    """Base schema for invite links"""
    title: str = Field(..., min_length=1, max_length=100, description="Title for the invite link")
    description: Optional[str] = Field(None, max_length=500, description="Description of the invite")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    max_uses: Optional[int] = Field(None, ge=1, description="Maximum number of uses")
    

class InviteLinkCreate(InviteLinkBase):
    """Schema for creating invite links"""
    pass


class InviteLinkResponse(InviteLinkBase):
    """Schema for invite link responses"""
    id: int
    link_id: str
    user_id: int
    current_uses: int = 0
    created_at: datetime
    is_active: bool
    qr_code_url: Optional[str] = None
    
    @property
    def invite_url(self) -> str:
        """Generate the full invite URL"""
        return f"/invite/{self.link_id}"
    
    class Config:
        from_attributes = True


class InviteLinkUsageResponse(BaseModel):
    """Schema for invite link usage responses"""
    id: int
    invite_link_id: int
    used_by_user_id: Optional[int] = None
    used_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    class Config:
        from_attributes = True


class QRCodeRequest(BaseModel):
    """Schema for QR code generation requests"""
    data: str = Field(..., description="Data to encode in QR code")
    size: Optional[int] = Field(200, ge=100, le=1000, description="QR code size in pixels")
    

class QRCodeResponse(BaseModel):
    """Schema for QR code generation responses"""
    qr_code_url: str = Field(..., description="URL to the generated QR code image")
    data: str = Field(..., description="Data encoded in the QR code")
    

class InviteStatsResponse(BaseModel):
    """Schema for invite statistics responses"""
    total_invite_codes: int
    active_invite_codes: int
    used_invite_codes: int
    total_invite_links: int
    active_invite_links: int
    total_link_uses: int
    

class ProcessInviteRequest(BaseModel):
    """Schema for processing invite codes/links"""
    invite_code: Optional[str] = Field(None, description="Invite code to process")
    invite_link_id: Optional[str] = Field(None, description="Invite link ID to process")
    
    @validator('*')
    def validate_at_least_one(cls, v, values):
        """Ensure at least one of invite_code or invite_link_id is provided"""
        if not any([v, values.get('invite_code'), values.get('invite_link_id')]):
            raise ValueError('Either invite_code or invite_link_id must be provided')
        return v


class ProcessInviteResponse(BaseModel):
    """Schema for processing invite responses"""
    success: bool
    message: str
    invite_type: Optional[InviteType] = None
    creator_id: Optional[int] = None