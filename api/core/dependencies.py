# api/core/dependencies.py - Enhanced Supabase auth version
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client
from core.database import Database
from gotrue.errors import AuthApiError
from typing import Optional, Dict, Any
import jwt

# Global instances (will be set during app startup)
supabase_client: Client = None
app_database: Database = None

security = HTTPBearer(auto_error=False)  # Allow optional auth for some endpoints

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """Get current authenticated user from Supabase with enhanced error handling"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        # Get user from Supabase using the JWT token
        response = supabase_client.auth.get_user(credentials.credentials)
        
        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Return user data in a consistent format
        return {
            "id": response.user.id,
            "email": response.user.email,
            "email_verified": response.user.email_confirmed_at is not None,
            "phone": response.user.phone,
            "phone_verified": response.user.phone_confirmed_at is not None,
            "created_at": response.user.created_at,
            "last_sign_in_at": response.user.last_sign_in_at,
            "user_metadata": response.user.user_metadata,
            "app_metadata": response.user.app_metadata,
            "provider": response.user.app_metadata.get("provider", "email") if response.user.app_metadata else "email",
            "providers": response.user.app_metadata.get("providers", []) if response.user.app_metadata else []
        }
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """Get current user if authenticated, None otherwise (for optional auth endpoints)"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(Depends(lambda: credentials))
    except HTTPException:
        return None

async def get_database() -> Database:
    """Database dependency"""
    if not app_database:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not available"
        )
    return app_database

def set_dependencies(supabase: Client, database: Database):
    """Set global dependencies - called during app startup"""
    global supabase_client, app_database
    supabase_client = supabase
    app_database = database

def get_supabase_client() -> Client:
    """Get Supabase client dependency"""
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase client not available"
        )
    return supabase_client