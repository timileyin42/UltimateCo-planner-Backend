from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator

# Base user schemas
class UserBase(BaseModel):
    """Base user schema with common fields"""
    email: Optional[EmailStr] = None
    full_name: str = Field(..., min_length=1, max_length=255)
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    phone_number: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    is_public_profile: bool = True

class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str = Field(..., min_length=8, max_length=100)
    
    def validate_passwords_match(self):
        """Validate that passwords match"""
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

class UserUpdate(BaseModel):
    """Schema for updating user information"""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    bio: Optional[str] = None
    phone_number: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    is_public_profile: Optional[bool] = None
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None

class UserPasswordUpdate(BaseModel):
    """Schema for updating user password"""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)
    confirm_new_password: str = Field(..., min_length=8, max_length=100)
    
    def validate_passwords_match(self):
        """Validate that new passwords match"""
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match")
        return self

class UserResponse(UserBase):
    """Schema for user response"""
    id: int
    avatar_url: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    email_notifications: bool
    push_notifications: bool
    sms_notifications: bool
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UserPublicResponse(BaseModel):
    """Schema for public user information (limited fields)"""
    id: int
    full_name: str
    username: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    is_verified: bool
    
    model_config = ConfigDict(from_attributes=True)

class UserSummary(BaseModel):
    """Schema for user summary (minimal fields)"""
    id: int
    full_name: str
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

# Authentication schemas
class UserLogin(BaseModel):
    """Schema for user login"""
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    password: str = Field(..., min_length=1)
    
    @model_validator(mode='after')
    def validate_email_or_phone(self):
        """Validate that either email or phone_number is provided"""
        if not self.email and not self.phone_number:
            raise ValueError("Either email or phone_number must be provided")
        if self.email and self.phone_number:
            raise ValueError("Provide either email or phone_number, not both")
        return self
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        """Validate phone number format"""
        if v is not None:
            # Remove any non-digit characters for validation
            digits_only = ''.join(filter(str.isdigit, v))
            if len(digits_only) < 10 or len(digits_only) > 15:
                raise ValueError("Phone number must be between 10 and 15 digits")
        return v

class UserRegister(BaseModel):
    """Schema for user registration"""
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    full_name: str = Field(..., min_length=1, max_length=255)
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    is_public_profile: bool = True
    password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str = Field(..., min_length=8, max_length=100)
    
    @model_validator(mode='after')
    def validate_email_or_phone(self):
        """Validate that either email or phone_number is provided"""
        if not self.email and not self.phone_number:
            raise ValueError("Either email or phone_number must be provided")
        if self.email and self.phone_number:
            raise ValueError("Provide either email or phone_number, not both")
        return self
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        """Validate phone number format"""
        if v is not None:
            # Remove any non-digit characters for validation
            digits_only = ''.join(filter(str.isdigit, v))
            if len(digits_only) < 10 or len(digits_only) > 15:
                raise ValueError("Phone number must be between 10 and 15 digits")
        return v
    
    def validate_passwords_match(self):
        """Validate that passwords match"""
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

class TokenResponse(BaseModel):
    """Schema for authentication token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: Optional['UserResponse'] = None  # User details
    
    model_config = ConfigDict(from_attributes=True)

class TokenRefresh(BaseModel):
    """Schema for token refresh request"""
    refresh_token: str

class PasswordReset(BaseModel):
    """Schema for password reset request"""
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)
    confirm_new_password: str = Field(..., min_length=8, max_length=100)
    
    def validate_passwords_match(self):
        """Validate that passwords match"""
        if self.new_password != self.confirm_new_password:
            raise ValueError("Passwords do not match")
        return self

# User profile schemas
class UserProfileBase(BaseModel):
    """Base user profile schema"""
    occupation: Optional[str] = None
    company: Optional[str] = None
    website: Optional[str] = None
    instagram_handle: Optional[str] = None
    twitter_handle: Optional[str] = None
    linkedin_url: Optional[str] = None
    planning_style: Optional[str] = None
    budget_range: Optional[str] = None

class UserProfileCreate(UserProfileBase):
    """Schema for creating user profile"""
    pass

class UserProfileUpdate(UserProfileBase):
    """Schema for updating user profile"""
    pass

class UserProfileResponse(UserProfileBase):
    """Schema for user profile response"""
    id: int
    user_id: int
    favorite_event_types: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# User search and listing schemas
class UserSearchQuery(BaseModel):
    """Schema for user search query"""
    query: str = Field(..., min_length=1, max_length=100)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

class UserListResponse(BaseModel):
    """Schema for user list response"""
    users: List[UserPublicResponse]
    total: int
    limit: int
    offset: int
    
class UserStatsResponse(BaseModel):
    """Schema for user statistics"""
    total_events_created: int
    total_events_attended: int
    total_tasks_completed: int
    total_friends: int
    member_since: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Friend management schemas
class FriendRequest(BaseModel):
    """Schema for friend request"""
    friend_id: int

class FriendResponse(BaseModel):
    """Schema for friend response"""
    id: int
    full_name: str
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool
    friendship_date: datetime
    
    model_config = ConfigDict(from_attributes=True)

class FriendListResponse(BaseModel):
    """Schema for friends list response"""
    friends: List[FriendResponse]
    total: int