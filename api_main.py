# api_main.py - FastAPI application for Supabase

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import os,uvicorn
import uuid,secrets,jwt
from dotenv import load_dotenv
from typing import Optional

from datetime import datetime, timedelta
import bcrypt
from pydantic import BaseModel, EmailStr, field_validator
import re
# Load environment variables
load_dotenv()

# Import your existing modules
from config import Config
from core.database import Database
from core.models import User
from services.user_registration import UserRegistrationService, RegistrationRequest
# Global instances
database = None
registration_service = None
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global database, registration_service
    try:
        # Validate config first
        Config.validate()
        
        # Initialize database
        database = Database(Config.DATABASE_URL)
        await database.connect()
        print("✅ Supabase database connected")
        
        # Initialize registration service
        registration_service = UserRegistrationService(database)
        print("✅ Registration service initialized")
        
    except Exception as e:
        print(f"❌ Startup error: {e}")
        raise
    
    yield
    
    # Shutdown
    try:
        if database:
            await database.close()
            print("✅ Database disconnected")
    except Exception as e:
        print(f"⚠️ Shutdown error: {e}")

# Create FastAPI app
app = FastAPI(
    title="Okan Personal Assistant API",
    description="Multi-platform personal assistant with expense tracking and reminders",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration for mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:19006",
        "http://192.168.1.100:19006",
        "exp://192.168.1.100:19000",
        "exp://192.168.1.100:8081",
        "*"  # Allow all for development (restrict in production)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# JWT utility functions with enhanced security
def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=int(os.getenv("JWT_EXPIRATION_HOURS", 24))),
        "iat": datetime.utcnow(),
        "type": "access",
        "jti": str(uuid.uuid4())  # JWT ID for token tracking
    }
    return jwt.encode(payload, os.getenv("JWT_SECRET"), algorithm=os.getenv("JWT_ALGORITHM", "HS256"))

def create_refresh_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=int(os.getenv("REFRESH_TOKEN_DAYS", 30))),
        "iat": datetime.utcnow(),
        "type": "refresh",
        "jti": str(uuid.uuid4())
    }
    return jwt.encode(payload, os.getenv("JWT_SECRET"), algorithm=os.getenv("JWT_ALGORITHM", "HS256"))


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM", "HS256")])
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

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user with enhanced validation"""
    payload = verify_token(credentials.credentials)
    user_id = payload.get("user_id")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = await database.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated"
        )
    
    if user.is_account_locked():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is temporarily locked"
        )
    
    return user

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Okan Personal Assistant API",
        "docs": "/docs",
        "health": "/api/health",
        "version": "1.0.0"
    }

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    db_status = "connected" if database and database.pool else "disconnected"
    
    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "service": "Okan Personal Assistant API",
        "version": "1.0.0",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }

# Authentication endpoints
from pydantic import BaseModel
from typing import Optional
import hashlib

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None
    currency: str = "USD"
    language: str = "en"
    
    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        if len(v) > 128:
            raise ValueError('Password must be less than 128 characters long')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('Password must contain at least one letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v
    
    @field_validator('name')
    def validate_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters long')
        if len(v) > 100:
            raise ValueError('Name must be less than 100 characters long')
        return v.strip()
    
    @field_validator('currency')
    def validate_currency(cls, v):
        valid_currencies = ['USD', 'EUR', 'BRL', 'GBP', 'JPY', 'CAD', 'AUD']
        if v not in valid_currencies:
            raise ValueError(f'Currency must be one of: {", ".join(valid_currencies)}')
        return v
    
    @field_validator('language')
    def validate_language(cls, v):
        valid_languages = ['en', 'es', 'pt', 'fr', 'de']
        if v not in valid_languages:
            raise ValueError(f'Language must be one of: {", ".join(valid_languages)}')
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    
    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 1:
            raise ValueError('Password is required')
        return v

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str
    
    @field_validator('new_password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('Password must contain at least one letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v

class GoogleLoginRequest(BaseModel):
    google_token: str

def hash_password(password: str) -> str:
    """Hash password using a simple method (use bcrypt in production)"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password"""
    return hashlib.sha256(password.encode()).hexdigest() == hashed

#Rate limiting decorator
from functools import wraps
from time import time

# Simple in-memory rate limiting (use Redis in production)
rate_limit_storage = {}

def rate_limit(max_attempts: int, window_seconds: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get client IP (simplified - use proper IP extraction in production)
            client_id = "default"  # In production, extract from request
            
            current_time = time()
            
            # Clean old entries
            rate_limit_storage[client_id] = [
                timestamp for timestamp in rate_limit_storage.get(client_id, [])
                if current_time - timestamp < window_seconds
            ]
            
            # Check rate limit
            if len(rate_limit_storage.get(client_id, [])) >= max_attempts:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many attempts. Try again in {window_seconds} seconds."
                )
            
            # Record this attempt
            rate_limit_storage.setdefault(client_id, []).append(current_time)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


@app.post("/api/auth/register")
@rate_limit(max_attempts=5, window_seconds=300)  # 5 attempts per 5 minutes
async def register_user(request: RegisterRequest):
    """Enhanced user registration with security"""
    try:
        # Check if user exists
        existing_user = await database.get_user_by_email(request.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Create registration request
        reg_request = RegistrationRequest(
            email=request.email,
            password=request.password,  # Will be hashed in service
            first_name=request.name.split()[0] if request.name else "",
            last_name=" ".join(request.name.split()[1:]) if len(request.name.split()) > 1 else "",
            phone_number=request.phone,
            platform_type="mobile_app",
            default_currency=request.currency,
            language=request.language
        )
        
        result = await registration_service.register_user(reg_request)
        
        if result.success:
            # Create tokens
            access_token = create_access_token(result.user.id, result.user.email)
            refresh_token = create_refresh_token(result.user.id)
            
            return {
                "success": True,
                "message": "Registration successful",
                "user": {
                    "id": result.user.id,
                    "email": result.user.email,
                    "name": result.user.get_display_name(),
                    "currency": result.user.default_currency,
                    "language": result.user.language,
                    "email_verified": result.user.email_verified
                },
                "tokens": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "expires_in": int(os.getenv("JWT_EXPIRATION_HOURS", 24)) * 3600
                },
                "requires_verification": result.requires_verification
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error
            )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@app.post("/api/auth/login")
@rate_limit(max_attempts=5, window_seconds=900)  # 5 attempts per 15 minutes
async def login_user(request: LoginRequest):
    """Enhanced login with security"""
    try:
        # Authenticate user
        auth_result = await registration_service.authenticate_user(
            request.email, request.password
        )
        
        if not auth_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=auth_result["error"]
            )
        
        user = auth_result["user"]
        
        # Create tokens
        access_token = create_access_token(user.id, user.email)
        refresh_token = create_refresh_token(user.id)
        
        return {
            "success": True,
            "message": "Login successful",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.get_display_name(),
                "currency": user.default_currency,
                "language": user.language,
                "email_verified": user.email_verified
            },
            "tokens": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": int(os.getenv("JWT_EXPIRATION_HOURS", 24)) * 3600
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )
    
@app.post("/api/auth/password-reset")
@rate_limit(max_attempts=3, window_seconds=300)  # 3 attempts per 5 minutes
async def request_password_reset(request: PasswordResetRequest):
    """Request password reset"""
    try:
        # Get user
        user = await database.get_user_by_email(request.email)
        
        # Always return success to prevent email enumeration
        if user:
            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            user.password_reset_token = reset_token
            user.password_reset_expires = datetime.now() + timedelta(hours=1)
            
            await database.update_user(user)
            
            # In production, send email with reset link
            print(f"Password reset token for {request.email}: {reset_token}")
        
        return {
            "success": True,
            "message": "If the email exists, you will receive password reset instructions"
        }
    
    except Exception as e:
        print(f"Password reset error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset request failed"
        )

@app.post("/api/auth/password-reset-confirm")
async def confirm_password_reset(request: PasswordResetConfirm):
    """Confirm password reset with token"""
    try:
        # Find user with valid reset token
        user = await database.get_user_by_password_reset_token(request.token)
        
        if not user or not user.password_reset_expires or datetime.now() > user.password_reset_expires:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Update password
        user.set_password(request.new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        user.reset_failed_login()  # Reset any account locks
        
        await database.update_user(user)
        
        return {
            "success": True,
            "message": "Password updated successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Password reset confirm error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset confirmation failed"
        )


@app.post("/api/auth/google")
async def google_login(request: GoogleLoginRequest):
    """Login with Google OAuth token"""
    try:
        from google.auth.transport import requests
        from google.oauth2 import id_token
        
        # Verify Google token
        idinfo = id_token.verify_oauth2_token(
            request.google_token, 
            requests.Request(), 
            os.getenv("GOOGLE_CLIENT_ID")
        )
        
        # Extract user info
        google_user_id = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name', '')
        
        # Check if user exists
        user = await database.get_user_by_email(email)
        
        if not user:
            # Register new user
            from services.user_registration import RegistrationRequest
            reg_request = RegistrationRequest(
                email=email,
                first_name=name.split()[0] if name else "",
                last_name=" ".join(name.split()[1:]) if len(name.split()) > 1 else "",
                platform_type="mobile_app",
                platform_user_id=google_user_id
            )
            
            result = await registration_service.register_user(reg_request)
            if not result.success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result.error
                )
            user = result.user
        
        # Create tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        
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
                "expires_in": int(os.getenv("JWT_EXPIRATION_HOURS", 24)) * 3600
            }
        }
    
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )
    except Exception as e:
        print(f"Google login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google login failed"
        )

@app.get("/api/user/profile")
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return {
        "success": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.get_display_name(),
            "currency": current_user.default_currency,
            "language": current_user.language,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None
        }
    }

@app.post("/api/auth/logout")
async def logout_user(current_user: User = Depends(get_current_user)):
    """Logout user"""
    # In production, you'd want to blacklist the token
    return {"success": True, "message": "Logged out successfully"}

# Run the server
if __name__ == "__main__":
    uvicorn.run(
        "api_main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )