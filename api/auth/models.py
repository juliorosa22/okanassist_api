# api/auth/models.py - Pydantic models for authentication
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime

class UserRegistrationRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class MagicLinkRequest(BaseModel):
    email: EmailStr
    redirect_to: Optional[str] = None

class PhoneAuthRequest(BaseModel):
    phone: str
    
    @field_validator('phone')
    def validate_phone(cls, v):
        # Basic phone validation - you can enhance this
        if not v.startswith('+'):
            raise ValueError('Phone number must include country code (start with +)')
        return v

class PhoneVerifyRequest(BaseModel):
    phone: str
    token: str

class OAuthRequest(BaseModel):
    provider: str
    redirect_to: Optional[str] = None
    
    @field_validator('provider')
    def validate_provider(cls, v):
        valid_providers = ['google', 'github', 'facebook', 'apple', 'discord', 'twitter']
        if v not in valid_providers:
            raise ValueError(f'Provider must be one of: {valid_providers}')
        return v

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordUpdateRequest(BaseModel):
    new_password: str
    
    @field_validator('new_password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v

class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

# Response models
class AuthResponse(BaseModel):
    success: bool
    message: str
    user: Optional[Dict[str, Any]] = None
    session: Optional[Dict[str, Any]] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    provider_token: Optional[str] = None
    provider_refresh_token: Optional[str] = None

class UserResponse(BaseModel):
    success: bool
    user: Dict[str, Any]

class OAuthUrlResponse(BaseModel):
    success: bool
    url: str
    provider: str
    
class ProviderListResponse(BaseModel):
    success: bool
    providers: List[Dict[str, Any]]

class SessionResponse(BaseModel):
    success: bool
    session: Optional[Dict[str, Any]] = None
    user: Optional[Dict[str, Any]] = None