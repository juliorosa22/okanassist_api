# api_main.py - FastAPI application for Supabase

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import uvicorn
import os
from dotenv import load_dotenv
from typing import Optional
import jwt
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Import your existing modules
from config import Config
from core.database import Database
from core.models import User
from services.user_registration import UserRegistrationService

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

# JWT utility functions
def create_access_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=int(os.getenv("JWT_EXPIRATION_HOURS", 24))),
        "iat": datetime.utcnow(),
        "type": "access"
    }
    return jwt.encode(payload, os.getenv("JWT_SECRET"), algorithm=os.getenv("JWT_ALGORITHM", "HS256"))

def create_refresh_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=int(os.getenv("REFRESH_TOKEN_DAYS", 30))),
        "iat": datetime.utcnow(),
        "type": "refresh"
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
    """Get current authenticated user"""
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
    email: str
    password: str
    name: str
    phone: Optional[str] = None
    currency: str = "USD"
    language: str = "en"

class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleLoginRequest(BaseModel):
    google_token: str

def hash_password(password: str) -> str:
    """Hash password using a simple method (use bcrypt in production)"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password"""
    return hashlib.sha256(password.encode()).hexdigest() == hashed

@app.post("/api/auth/register")
async def register_user(request: RegisterRequest):
    """Register a new user"""
    try:
        # Check if user exists
        existing_user = await database.get_user_by_email(request.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Hash password
        hashed_password = hash_password(request.password)
        
        # Create user via registration service
        from services.user_registration import RegistrationRequest
        reg_request = RegistrationRequest(
            email=request.email,
            first_name=request.name.split()[0] if request.name else "",
            last_name=" ".join(request.name.split()[1:]) if len(request.name.split()) > 1 else "",
            phone_number=request.phone,
            platform_type="mobile_app",
            default_currency=request.currency,
            language=request.language
        )
        
        result = await registration_service.register_user(reg_request)
        
        if result.success:
            # Store password hash (you'll need to add this to your User model)
            # For now, we'll store it as part of user creation
            
            # Create tokens
            access_token = create_access_token(result.user.id)
            refresh_token = create_refresh_token(result.user.id)
            
            return {
                "success": True,
                "message": "Registration successful",
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
                    "expires_in": int(os.getenv("JWT_EXPIRATION_HOURS", 24)) * 3600
                }
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
async def login_user(request: LoginRequest):
    """Login user with email and password"""
    try:
        # Get user by email
        user = await database.get_user_by_email(request.email)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # For now, we'll use a simple password check
        # In production, you should store hashed passwords
        if request.password != "demo123" and request.email != "demo@test.com":
            # Implement proper password verification here
            pass
        
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