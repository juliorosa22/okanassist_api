# api/auth/endpoints.py
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from typing import Optional
import jwt
from datetime import datetime, timedelta
import bcrypt
from google.auth.transport import requests
from google.oauth2 import id_token
import os

from services.user_registration import UserRegistrationService
from core.database import Database

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

# Pydantic models
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    phone: Optional[str] = None
    currency: str = "USD"
    language: str = "en"
    platform_type: str = "mobile_app"
    device_info: Optional[dict] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleLoginRequest(BaseModel):
    google_token: str
    platform_type: str = "mobile_app"

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
REFRESH_TOKEN_DAYS = 30

def create_access_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow(),
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS),
        "iat": datetime.utcnow(),
        "type": "refresh"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

async def get_current_user(token: str = Depends(security)):
    payload = verify_token(token.credentials)
    user_id = payload.get("user_id")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Get user from database
    database = Database(os.getenv("DATABASE_URL"))
    await database.connect()
    
    try:
        user = await database.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        return user
    finally:
        await database.close()

@router.post("/register")
async def register_user(request: RegisterRequest):
    """Register a new user"""
    database = Database(os.getenv("DATABASE_URL"))
    await database.connect()
    
    try:
        registration_service = UserRegistrationService(database)
        
        # Hash password
        hashed_password = hash_password(request.password)
        
        # Prepare registration data
        registration_data = {
            "email": request.email,
            "password": hashed_password,
            "first_name": request.name.split()[0] if request.name else "",
            "last_name": " ".join(request.name.split()[1:]) if len(request.name.split()) > 1 else "",
            "phone_number": request.phone,
            "platform_type": request.platform_type,
            "default_currency": request.currency,
            "language": request.language,
            "device_info": request.device_info or {}
        }
        
        result = await registration_service.register_user(registration_data)
        
        if result.success:
            # Create tokens
            access_token = create_access_token(result.user.id)
            refresh_token = create_refresh_token(result.user.id)
            
            return {
                "success": True,
                "message": result.message,
                "user": {
                    "id": result.user.id,
                    "email": result.user.email,
                    "name": result.user.get_display_name(),
                    "currency": result.user.default_currency,
                    "language": result.user.language
                },
                "tokens": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "expires_in": JWT_EXPIRATION_HOURS * 3600
                },
                "requires_verification": result.requires_verification
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        await database.close()

@router.post("/login")
async def login_user(request: LoginRequest):
    """Login user with email and password"""
    database = Database(os.getenv("DATABASE_URL"))
    await database.connect()
    
    try:
        # Get user by email
        user = await database.get_user_by_email(request.email)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Verify password (you'll need to store hashed passwords in your User model)
        # For now, assuming you have a password field
        if not verify_password(request.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Create tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        
        # Update last login
        await database.update_user_last_login(user.id)
        
        return {
            "success": True,
            "message": "Login successful",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.get_display_name(),
                "currency": user.default_currency,
                "language": user.language
            },
            "tokens": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": JWT_EXPIRATION_HOURS * 3600
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )
    finally:
        await database.close()

@router.post("/google")
async def google_login(request: GoogleLoginRequest):
    """Login with Google OAuth token"""
    try:
        # Verify Google token
        GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
        idinfo = id_token.verify_oauth2_token(
            request.google_token, 
            requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        # Extract user info from Google
        google_user_id = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name', '')
        
        database = Database(os.getenv("DATABASE_URL"))
        await database.connect()
        
        try:
            registration_service = UserRegistrationService(database)
            
            # Check if user exists
            user = await database.get_user_by_email(email)
            
            if not user:
                # Register new user
                registration_data = {
                    "email": email,
                    "first_name": name.split()[0] if name else "",
                    "last_name": " ".join(name.split()[1:]) if len(name.split()) > 1 else "",
                    "platform_type": request.platform_type,
                    "platform_user_id": google_user_id,
                    "email_verified": True  # Google emails are verified
                }
                
                result = await registration_service.register_user(registration_data)
                if not result.success:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=result.error
                    )
                user = result.user
            
            # Create tokens
            access_token = create_access_token(user.id)
            refresh_token = create_refresh_token(user.id)
            
            # Update last login
            await database.update_user_last_login(user.id)
            
            return {
                "success": True,
                "message": "Google login successful",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.get_display_name(),
                    "currency": user.default_currency,
                    "language": user.language
                },
                "tokens": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "expires_in": JWT_EXPIRATION_HOURS * 3600
                }
            }
        
        finally:
            await database.close()
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google login failed"
        )

@router.post("/refresh")
async def refresh_token(token: str):
    """Refresh access token"""
    payload = verify_token(token)
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("user_id")
    new_access_token = create_access_token(user_id)
    
    return {
        "success": True,
        "tokens": {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": JWT_EXPIRATION_HOURS * 3600
        }
    }

@router.post("/logout")
async def logout_user(current_user = Depends(get_current_user)):
    """Logout user (invalidate token)"""
    # In a production app, you'd want to blacklist the token
    # For now, we'll just return success
    return {"success": True, "message": "Logged out successfully"}

@router.post("/verify-email")
async def verify_email(verification_token: str):
    """Verify user email"""
    database = Database(os.getenv("DATABASE_URL"))
    await database.connect()
    
    try:
        registration_service = UserRegistrationService(database)
        result = await registration_service.verify_user(verification_token)
        
        if result["success"]:
            # Create tokens for verified user
            access_token = create_access_token(result["user"].id)
            refresh_token = create_refresh_token(result["user"].id)
            
            return {
                "success": True,
                "message": result["message"],
                "user": {
                    "id": result["user"].id,
                    "email": result["user"].email,
                    "name": result["user"].get_display_name(),
                    "currency": result["user"].default_currency,
                    "language": result["user"].language
                },
                "tokens": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "expires_in": JWT_EXPIRATION_HOURS * 3600
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
    
    finally:
        await database.close()