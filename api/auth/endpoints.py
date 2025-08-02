# api/auth/endpoints.py - Complete Supabase authentication system
from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from supabase import Client
from gotrue.errors import AuthApiError
from typing import Optional, Dict, Any
from datetime import datetime
import os

from api.core.dependencies import get_current_user, get_optional_user, get_supabase_client
from .models import (
    UserRegistrationRequest, UserLoginRequest, MagicLinkRequest, PhoneAuthRequest,
    PhoneVerifyRequest, OAuthRequest, TokenRefreshRequest, PasswordResetRequest,
    PasswordUpdateRequest, UserUpdateRequest, AuthResponse, UserResponse,
    OAuthUrlResponse, ProviderListResponse, SessionResponse
)

router = APIRouter(prefix="/auth", tags=["authentication"])

# ============================================================================
# EMAIL/PASSWORD AUTHENTICATION
# ============================================================================

@router.post("/register", response_model=AuthResponse)
async def register_user(
    user_data: UserRegistrationRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """Register a new user with email and password"""
    try:
        # Prepare user metadata
        metadata = user_data.metadata or {}
        if user_data.full_name:
            metadata["full_name"] = user_data.full_name
        if user_data.phone:
            metadata["phone"] = user_data.phone
        
        # Register user with Supabase
        response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": metadata
            }
        })
        
        if response.user:
            return AuthResponse(
                success=True,
                message="Registration successful! Please check your email to verify your account." if not response.session else "Registration successful!",
                user={
                    "id": response.user.id,
                    "email": response.user.email,
                    "email_verified": response.user.email_confirmed_at is not None,
                    "created_at": response.user.created_at,
                    "user_metadata": response.user.user_metadata
                },
                session={
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_in": response.session.expires_in,
                    "token_type": response.session.token_type
                } if response.session else None,
                access_token=response.session.access_token if response.session else None,
                refresh_token=response.session.refresh_token if response.session else None,
                expires_in=response.session.expires_in if response.session else None
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed"
            )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/login", response_model=AuthResponse)
async def login_user(
    login_data: UserLoginRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """Login user with email and password"""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": login_data.email,
            "password": login_data.password
        })
        
        if response.session and response.user:
            return AuthResponse(
                success=True,
                message="Login successful",
                user={
                    "id": response.user.id,
                    "email": response.user.email,
                    "email_verified": response.user.email_confirmed_at is not None,
                    "phone": response.user.phone,
                    "phone_verified": response.user.phone_confirmed_at is not None,
                    "last_sign_in_at": response.user.last_sign_in_at,
                    "user_metadata": response.user.user_metadata,
                    "provider": response.user.app_metadata.get("provider", "email") if response.user.app_metadata else "email"
                },
                session={
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_in": response.session.expires_in,
                    "token_type": response.session.token_type
                },
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                expires_in=response.session.expires_in
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

# ============================================================================
# OAUTH AUTHENTICATION (Google, GitHub, etc.)
# ============================================================================

@router.get("/providers", response_model=ProviderListResponse)
async def get_auth_providers():
    """Get available OAuth providers"""
    providers = [
        {
            "name": "google",
            "display_name": "Google",
            "icon": "🔍",
            "enabled": bool(os.getenv("SUPABASE_GOOGLE_CLIENT_ID"))
        },
        {
            "name": "github", 
            "display_name": "GitHub",
            "icon": "🐙",
            "enabled": bool(os.getenv("SUPABASE_GITHUB_CLIENT_ID"))
        },
        {
            "name": "facebook",
            "display_name": "Facebook", 
            "icon": "📘",
            "enabled": bool(os.getenv("SUPABASE_FACEBOOK_CLIENT_ID"))
        },
        {
            "name": "apple",
            "display_name": "Apple",
            "icon": "🍎", 
            "enabled": bool(os.getenv("SUPABASE_APPLE_CLIENT_ID"))
        }
    ]
    
    return ProviderListResponse(
        success=True,
        providers=[p for p in providers if p["enabled"]]
    )

@router.post("/oauth/url", response_model=OAuthUrlResponse)
async def get_oauth_url(
    oauth_data: OAuthRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """Get OAuth provider sign-in URL"""
    try:
        # Default redirect URL
        default_redirect = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/auth/callback"
        redirect_to = oauth_data.redirect_to or default_redirect
        
        response = supabase.auth.sign_in_with_oauth({
            "provider": oauth_data.provider,
            "options": {
                "redirect_to": redirect_to
            }
        })
        
        return OAuthUrlResponse(
            success=True,
            url=response.url,
            provider=oauth_data.provider
        )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth URL generation failed: {str(e)}"
        )

@router.post("/oauth/callback")
async def oauth_callback(
    request: Request,
    access_token: Optional[str] = Query(None),
    refresh_token: Optional[str] = Query(None),
    supabase: Client = Depends(get_supabase_client)
):
    """Handle OAuth callback (usually called by frontend)"""
    try:
        if access_token:
            # Set session with tokens
            response = supabase.auth.set_session(access_token, refresh_token)
            
            if response.user:
                return AuthResponse(
                    success=True,
                    message="OAuth authentication successful",
                    user={
                        "id": response.user.id,
                        "email": response.user.email,
                        "email_verified": response.user.email_confirmed_at is not None,
                        "user_metadata": response.user.user_metadata,
                        "provider": response.user.app_metadata.get("provider") if response.user.app_metadata else "oauth"
                    },
                    access_token=access_token,
                    refresh_token=refresh_token
                )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth callback"
        )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {str(e)}"
        )

# ============================================================================
# MAGIC LINK AUTHENTICATION  
# ============================================================================

@router.post("/magic-link", response_model=AuthResponse)
async def send_magic_link(
    magic_data: MagicLinkRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """Send magic link for passwordless authentication"""
    try:
        default_redirect = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/auth/callback"
        redirect_to = magic_data.redirect_to or default_redirect
        
        response = supabase.auth.sign_in_with_otp({
            "email": magic_data.email,
            "options": {
                "email_redirect_to": redirect_to
            }
        })
        
        return AuthResponse(
            success=True,
            message="Magic link sent! Check your email to sign in."
        )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Magic link failed: {str(e)}"
        )


# ============================================================================
# PHONE AUTHENTICATION
# ============================================================================

@router.post("/phone/send-otp", response_model=AuthResponse)
async def send_phone_otp(
    phone_data: PhoneAuthRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """Send OTP to phone number"""
    try:
        response = supabase.auth.sign_in_with_otp({
            "phone": phone_data.phone
        })
        
        return AuthResponse(
            success=True,
            message=f"OTP sent to {phone_data.phone}. Please check your SMS."
        )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Phone OTP failed: {str(e)}"
        )

@router.post("/phone/verify", response_model=AuthResponse)
async def verify_phone_otp(
    verify_data: PhoneVerifyRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """Verify phone OTP and authenticate"""
    try:
        response = supabase.auth.verify_otp({
            "phone": verify_data.phone,
            "token": verify_data.token,
            "type": "sms"
        })
        
        if response.session and response.user:
            return AuthResponse(
                success=True,
                message="Phone verification successful",
                user={
                    "id": response.user.id,
                    "phone": response.user.phone,
                    "phone_verified": response.user.phone_confirmed_at is not None,
                    "created_at": response.user.created_at,
                    "user_metadata": response.user.user_metadata
                },
                session={
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_in": response.session.expires_in,
                    "token_type": response.session.token_type
                },
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                expires_in=response.session.expires_in
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP"
            )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Phone verification failed: {str(e)}"
        )

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

@router.post("/refresh", response_model=AuthResponse)
async def refresh_session(
    refresh_data: TokenRefreshRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """Refresh authentication session"""
    try:
        response = supabase.auth.refresh_session(refresh_data.refresh_token)
        
        if response.session and response.user:
            return AuthResponse(
                success=True,
                message="Session refreshed successfully",
                user={
                    "id": response.user.id,
                    "email": response.user.email,
                    "user_metadata": response.user.user_metadata
                },
                session={
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_in": response.session.expires_in,
                    "token_type": response.session.token_type
                },
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                expires_in=response.session.expires_in
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Session refresh failed: {str(e)}"
        )

@router.get("/session", response_model=SessionResponse)
async def get_session(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Get current session information"""
    try:
        session = supabase.auth.get_session()
        
        return SessionResponse(
            success=True,
            session={
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "expires_in": session.expires_in,
                "token_type": session.token_type
            } if session else None,
            user=current_user
        )
        
    except Exception as e:
        return SessionResponse(
            success=True,
            session=None,
            user=None
        )

@router.post("/logout", response_model=AuthResponse)
async def logout_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Logout current user"""
    try:
        supabase.auth.sign_out()
        
        return AuthResponse(
            success=True,
            message="Logged out successfully"
        )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )

# ============================================================================
# PASSWORD MANAGEMENT
# ============================================================================

@router.post("/password/reset", response_model=AuthResponse)
async def request_password_reset(
    reset_data: PasswordResetRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """Send password reset email"""
    try:
        response = supabase.auth.reset_password_email(
            reset_data.email,
            {
                "redirect_to": f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/auth/reset-password"
            }
        )
        
        return AuthResponse(
            success=True,
            message="Password reset email sent. Please check your inbox."
        )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password reset failed: {str(e)}"
        )

@router.post("/password/update", response_model=AuthResponse)
async def update_password(
    password_data: PasswordUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Update user password"""
    try:
        response = supabase.auth.update_user({
            "password": password_data.new_password
        })
        
        if response.user:
            return AuthResponse(
                success=True,
                message="Password updated successfully",
                user={
                    "id": response.user.id,
                    "email": response.user.email,
                    "updated_at": response.user.updated_at
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password update failed"
            )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password update failed: {str(e)}"
        )

# ============================================================================
# USER PROFILE WITH DATABASE SYNC
# ============================================================================

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get comprehensive user profile with app preferences"""
    from api.core.dependencies import get_database
    
    try:
        database = await get_database()
        
        # Get user preferences from app database if they exist
        app_preferences = await database.get_user_preferences(current_user["id"])
        
        profile = {
            "id": current_user["id"],
            "email": current_user["email"],
            "email_verified": current_user["email_verified"],
            "phone": current_user.get("phone"),
            "phone_verified": current_user.get("phone_verified", False),
            "created_at": current_user["created_at"],
            "last_sign_in_at": current_user["last_sign_in_at"],
            "provider": current_user["provider"],
            "providers": current_user.get("providers", []),
            "user_metadata": current_user["user_metadata"],
            
            # App-specific preferences
            "app_preferences": app_preferences or {
                "language": "en",
                "currency": "USD",
                "timezone": "UTC",
                "country": None,
                "notifications_enabled": True,
                "theme": "light"
            }
        }
        
        return UserResponse(
            success=True,
            user=profile
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )

@router.put("/profile", response_model=UserResponse)
async def update_user_profile(
    update_data: UserUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Update user profile and sync with app database"""
    from api.core.dependencies import get_database
    
    try:
        database = await get_database()
        
        # Update Supabase user metadata
        supabase_updates = {}
        if update_data.metadata:
            supabase_updates["data"] = {
                **current_user.get("user_metadata", {}),
                **update_data.metadata
            }
        
        if update_data.full_name:
            supabase_updates["data"] = {
                **supabase_updates.get("data", {}),
                "full_name": update_data.full_name
            }
        
        if update_data.phone:
            supabase_updates["phone"] = update_data.phone
        
        # Update in Supabase
        if supabase_updates:
            response = supabase.auth.update_user(supabase_updates)
            if not response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update user profile"
                )
        
        # Sync with app database for preferences
        if update_data.metadata:
            app_preferences = {
                "language": update_data.metadata.get("language", "en"),
                "currency": update_data.metadata.get("currency", "USD"),
                "timezone": update_data.metadata.get("timezone", "UTC"),
                "country": update_data.metadata.get("country"),
                "notifications_enabled": update_data.metadata.get("notifications_enabled", True),
                "theme": update_data.metadata.get("theme", "light")
            }
            
            await database.sync_user_preferences(current_user["id"], app_preferences)
        
        # Return updated profile
        return await get_user_profile(current_user)
        
    except HTTPException:
        raise
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profile update failed: {str(e)}"
        )

# ============================================================================
# MOBILE APP OAUTH CALLBACKS
# ============================================================================

@router.get("/mobile/oauth/{provider}")
async def mobile_oauth_url(
    provider: str,
    redirect_scheme: str = Query(..., description="Mobile app URL scheme (e.g., 'myapp')"),
    supabase: Client = Depends(get_supabase_client)
):
    """Generate OAuth URL for mobile apps with custom scheme redirect"""
    try:
        # Validate provider
        valid_providers = ["google", "apple", "facebook"]
        if provider not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider must be one of: {valid_providers}"
            )
        
        # Mobile redirect URL with custom scheme
        mobile_redirect = f"{redirect_scheme}://auth/callback"
        
        response = supabase.auth.sign_in_with_oauth({
            "provider": provider,
            "options": {
                "redirect_to": mobile_redirect,
                "query_params": {
                    "access_type": "offline",
                    "prompt": "consent"
                }
            }
        })
        
        return {
            "success": True,
            "provider": provider,
            "auth_url": response.url,
            "redirect_uri": mobile_redirect,
            "instructions": f"Open this URL in browser, then return to app via {redirect_scheme}:// scheme"
        }
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mobile OAuth failed: {str(e)}"
        )

@router.post("/mobile/exchange-code")
async def exchange_mobile_auth_code(
    request: Request,
    supabase: Client = Depends(get_supabase_client)
):
    """Exchange authorization code from mobile OAuth callback"""
    try:
        body = await request.json()
        auth_code = body.get("code")
        
        if not auth_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization code required"
            )
        
        # Exchange code for session
        response = supabase.auth.exchange_code_for_session(auth_code)
        
        if response.session and response.user:
            # Sync user with app database
            await _sync_oauth_user_to_database(response.user)
            
            return AuthResponse(
                success=True,
                message="Mobile OAuth authentication successful",
                user={
                    "id": response.user.id,
                    "email": response.user.email,
                    "email_verified": response.user.email_confirmed_at is not None,
                    "user_metadata": response.user.user_metadata,
                    "provider": response.user.app_metadata.get("provider") if response.user.app_metadata else "oauth"
                },
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                expires_in=response.session.expires_in
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid authorization code"
            )
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code exchange failed: {str(e)}"
        )

# ============================================================================
# DATABASE SYNC HELPERS
# ============================================================================

async def _sync_oauth_user_to_database(user):
    """Sync OAuth user to app database with default preferences"""
    from api.core.dependencies import get_database
    
    try:
        database = await get_database()
        
        # Extract user info from OAuth metadata
        user_metadata = user.user_metadata or {}
        app_metadata = user.app_metadata or {}
        
        # Detect language and currency from locale if available
        locale = user_metadata.get("locale", "en-US")
        language = locale.split("-")[0] if locale else "en"
        
        # Map common locales to currencies
        currency_map = {
            "en": "USD", "es": "USD", "pt": "BRL", "fr": "EUR", 
            "de": "EUR", "it": "EUR", "ja": "JPY", "ko": "KRW",
            "zh": "CNY", "ru": "RUB", "ar": "USD"
        }
        currency = currency_map.get(language, "USD")
        
        # Default preferences for new OAuth users
        preferences = {
            "language": language,
            "currency": currency,
            "timezone": "UTC",  # Will be updated when user sets location
            "country": None,
            "notifications_enabled": True,
            "theme": "light",
            "full_name": user_metadata.get("full_name") or user_metadata.get("name"),
            "avatar_url": user_metadata.get("avatar_url") or user_metadata.get("picture"),
            "provider": app_metadata.get("provider", "oauth")
        }
        
        await database.sync_user_preferences(user.id, preferences)
        print(f"✅ Synced OAuth user {user.email} to database")
        
    except Exception as e:
        print(f"⚠️ Failed to sync OAuth user to database: {e}")