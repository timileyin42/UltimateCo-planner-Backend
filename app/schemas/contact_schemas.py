from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.models.contact_models import ContactInviteStatus


class ContactBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    phone_number: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    notes: Optional[str] = Field(None, max_length=500)
    is_favorite: bool = False

    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v is not None:
            # Basic phone number validation
            import re
            phone_pattern = r'^\+?[\d\s\-\(\)]{10,15}$'
            if not re.match(phone_pattern, v):
                raise ValueError('Invalid phone number format')
        return v


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    phone_number: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    notes: Optional[str] = Field(None, max_length=500)
    is_favorite: Optional[bool] = None

    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v is not None:
            import re
            phone_pattern = r'^\+?[\d\s\-\(\)]{10,15}$'
            if not re.match(phone_pattern, v):
                raise ValueError('Invalid phone number format')
        return v


class ContactResponse(ContactBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContactInvitationBase(BaseModel):
    contact_id: int
    event_id: Optional[int] = None
    message: Optional[str] = Field(None, max_length=500)


class ContactInvitationCreate(ContactInvitationBase):
    pass


class BulkContactInvitationCreate(BaseModel):
    contact_ids: List[int] = Field(..., min_items=1, max_items=50)
    event_id: Optional[int] = None
    message: Optional[str] = Field(None, max_length=500)


class ContactInvitationResponse(ContactInvitationBase):
    id: int
    sender_id: int
    recipient_id: Optional[int] = None
    invitation_token: str
    status: ContactInviteStatus
    created_at: datetime
    responded_at: Optional[datetime] = None
    
    # Related data
    contact: Optional[ContactResponse] = None
    sender_name: Optional[str] = None
    recipient_name: Optional[str] = None
    event_title: Optional[str] = None

    model_config = {"from_attributes": True}


class InvitationResponseRequest(BaseModel):
    accept: bool


class ContactGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class ContactGroupCreate(ContactGroupBase):
    pass


class ContactGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class ContactGroupResponse(ContactGroupBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    member_count: Optional[int] = 0

    model_config = {"from_attributes": True}


class ContactGroupMembershipResponse(BaseModel):
    id: int
    group_id: int
    contact_id: int
    added_at: datetime
    contact: Optional[ContactResponse] = None

    model_config = {"from_attributes": True}


class AddContactToGroupRequest(BaseModel):
    contact_id: int


class ContactListResponse(BaseModel):
    contacts: List[ContactResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class InvitationListResponse(BaseModel):
    invitations: List[ContactInvitationResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class ContactGroupListResponse(BaseModel):
    groups: List[ContactGroupResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class ContactStatsResponse(BaseModel):
    total_contacts: int
    favorite_contacts: int
    total_groups: int
    pending_invitations_sent: int
    pending_invitations_received: int
    accepted_invitations: int
    declined_invitations: int


class SMSStatusResponse(BaseModel):
    sid: str
    status: str
    to: str
    from_phone: str
    body: str
    date_sent: Optional[datetime] = None


class ContactImportRequest(BaseModel):
    contacts: List[ContactCreate] = Field(..., min_items=1, max_items=100)


class ContactImportResponse(BaseModel):
    imported_count: int
    skipped_count: int
    errors: List[str] = []
    imported_contacts: List[ContactResponse] = []