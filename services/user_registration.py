# services/user_registration.py
from typing import Dict, Optional, Any, Tuple, List
from datetime import datetime, timedelta
import uuid
import re
import secrets
import bcrypt
import hashlib
from dataclasses import dataclass

from core.database import Database
from core.models import User, UserPlatform, PlatformType, SubscriptionStatus, create_user_from_platform_data

@dataclass
class RegistrationRequest:
    """User registration request data"""
    email: Optional[str] = None
    phone_number: Optional[str] = None
    password: Optional[str] = None  # ADD PASSWORD FIELD
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    platform_type: str = "web_app"
    platform_user_id: Optional[str] = None
    platform_username: Optional[str] = None
    country_code: str = "US"
    timezone: str = "UTC"
    language: str = "en"
    default_currency: str = "USD"
    device_info: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.device_info is None:
            self.device_info = {}

@dataclass
class RegistrationResult:
    """Registration result data"""
    success: bool
    user: Optional[User] = None
    platform: Optional[UserPlatform] = None
    verification_token: Optional[str] = None
    message: str = ""
    error: Optional[str] = None
    requires_verification: bool = False

class UserRegistrationService:
    """
    Handles user registration, verification, and platform management
    """
    
    def __init__(self, database: Database):
        self.database = database
        self.verification_tokens = {}  # In production, use Redis or database
        # Security settings
        self.min_password_length = 6
        self.max_password_length = 128
        self.require_password_complexity = True
    
    def _validate_password(self, password: str) -> Dict[str, Any]:
        """Validate password strength"""
        if not password:
            return {"valid": False, "error": "Password is required"}
        
        if len(password) < self.min_password_length:
            return {"valid": False, "error": f"Password must be at least {self.min_password_length} characters"}
        
        if len(password) > self.max_password_length:
            return {"valid": False, "error": f"Password must be less than {self.max_password_length} characters"}
        
        if self.require_password_complexity:
            if not re.search(r'[A-Za-z]', password):
                return {"valid": False, "error": "Password must contain at least one letter"}
            
            if not re.search(r'\d', password):
                return {"valid": False, "error": "Password must contain at least one number"}
        
        return {"valid": True}
    

    def _validate_password(self, password: str) -> Dict[str, Any]:
        """Validate password strength"""
        if not password:
            return {"valid": False, "error": "Password is required"}
        
        if len(password) < self.min_password_length:
            return {"valid": False, "error": f"Password must be at least {self.min_password_length} characters"}
        
        if len(password) > self.max_password_length:
            return {"valid": False, "error": f"Password must be less than {self.max_password_length} characters"}
        
        if self.require_password_complexity:
            if not re.search(r'[A-Za-z]', password):
                return {"valid": False, "error": "Password must contain at least one letter"}
            
            if not re.search(r'\d', password):
                return {"valid": False, "error": "Password must contain at least one number"}
        
        return {"valid": True}
    
    def _validate_registration_request(self, request: RegistrationRequest) -> Dict[str, Any]:
        """Enhanced validation with password checking"""
        
        # Must have either email or phone number
        if not request.email and not request.phone_number:
            return {
                "valid": False,
                "error": "Either email or phone number is required"
            }
        
        # Validate email format
        if request.email and not self._is_valid_email(request.email):
            return {
                "valid": False,
                "error": "Invalid email format"
            }
        
        # Validate phone number format
        if request.phone_number and not self._is_valid_phone(request.phone_number):
            return {
                "valid": False,
                "error": "Invalid phone number format"
            }
        
        # Validate password (if provided)
        if request.password:
            password_validation = self._validate_password(request.password)
            if not password_validation["valid"]:
                return password_validation
        
        # Validate platform type
        valid_platforms = [p.value for p in PlatformType]
        if request.platform_type not in valid_platforms:
            return {
                "valid": False,
                "error": f"Invalid platform type. Must be one of: {valid_platforms}"
            }
        
        return {"valid": True}
    
    async def _create_new_user(self, request: RegistrationRequest) -> Tuple[User, UserPlatform]:
        """Create new user with password handling"""
        
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email=request.email,
            phone_number=request.phone_number,
            first_name=request.first_name,
            last_name=request.last_name,
            country_code=request.country_code,
            timezone=request.timezone,
            language=request.language,
            default_currency=request.default_currency,
            subscription_status=SubscriptionStatus.FREE.value,
            is_active=True,
            email_verified=False,
            phone_verified=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Set password if provided
        if request.password:
            user.set_password(request.password)
        
        # Create platform
        platform = UserPlatform(
            user_id=user.id,
            platform_type=request.platform_type,
            platform_user_id=request.platform_user_id or str(uuid.uuid4()),
            platform_username=request.platform_username,
            is_active=True,
            is_primary=True,
            notification_enabled=True,
            device_info=request.device_info,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Save to database
        saved_user = await self.database.create_user(user)
        saved_platform = await self.database.create_user_platform(platform)
        
        return saved_user, saved_platform
    
    async def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user with email and password"""
        try:
            # Get user by email
            user = await self.database.get_user_by_email(email)
            
            if not user:
                return {
                    "success": False,
                    "error": "Invalid email or password",
                    "user": None
                }
            
            # Check if account is locked
            if user.is_account_locked():
                return {
                    "success": False,
                    "error": "Account temporarily locked due to failed login attempts",
                    "user": None
                }
            
            # Check password
            if not user.check_password(password):
                # Increment failed login attempts
                user.increment_failed_login()
                await self.database.update_user(user)
                
                return {
                    "success": False,
                    "error": "Invalid email or password",
                    "user": None
                }
            
            # Successful login - reset failed attempts
            user.reset_failed_login()
            user.last_login_at = datetime.now()
            await self.database.update_user(user)
            
            return {
                "success": True,
                "message": "Authentication successful",
                "user": user
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": "Authentication failed",
                "user": None
            }

    async def register_user(self, request: RegistrationRequest) -> RegistrationResult:
        """
        Register a new user with comprehensive validation and setup
        
        Args:
            request: Registration request data
            
        Returns:
            Registration result with user and platform information
        """
        
        # Validate registration request
        validation_result = self._validate_registration_request(request)
        if not validation_result["valid"]:
            return RegistrationResult(
                success=False,
                error=validation_result["error"],
                message="Registration validation failed"
            )
        
        try:
            # Check if user already exists
            existing_user = await self._check_existing_user(request)
            if existing_user:
                return await self._handle_existing_user(existing_user, request)
            
            # Create new user
            user, platform = await self._create_new_user(request)
            
            # Setup verification if needed
            verification_token = None
            requires_verification = False
            
            if request.email and not user.email_verified:
                verification_token = await self._create_verification_token(user.id, "email", request.email)
                requires_verification = True
            
            if request.phone_number and not user.phone_verified:
                if not verification_token:  # Only create one token per registration
                    verification_token = await self._create_verification_token(user.id, "phone", request.phone_number)
                requires_verification = True
            
            # Log registration activity
            await self.database._log_user_activity(
                user.id,
                "registration",
                {
                    "platform_type": platform.platform_type,
                    "has_email": bool(request.email),
                    "has_phone": bool(request.phone_number),
                    "country": request.country_code,
                    "language": request.language
                },
                platform.platform_type
            )
            
            return RegistrationResult(
                success=True,
                user=user,
                platform=platform,
                verification_token=verification_token,
                requires_verification=requires_verification,
                message=f"User registered successfully. Welcome, {user.get_display_name()}!"
            )
            
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return RegistrationResult(
                success=False,
                error=str(e),
                message="Registration failed due to system error"
            )
    
    async def quick_platform_registration(self, platform_type: str, platform_user_id: str, 
                                        platform_data: Dict[str, Any] = None) -> RegistrationResult:
        """
        Quick registration for platform users (Telegram, WhatsApp)
        
        Args:
            platform_type: Platform type (telegram, whatsapp, etc.)
            platform_user_id: Platform-specific user ID
            platform_data: Additional platform data
            
        Returns:
            Registration result
        """
        
        platform_data = platform_data or {}
        
        # Check if user already exists on this platform
        existing = await self.database.get_user_by_platform(platform_type, platform_user_id)
        if existing:
            user, platform = existing
            await self.database.update_platform_activity(platform_type, platform_user_id)
            return RegistrationResult(
                success=True,
                user=user,
                platform=platform,
                message=f"Welcome back, {user.get_display_name()}!"
            )
        
        # Create registration request from platform data
        request = RegistrationRequest(
            first_name=platform_data.get("first_name"),
            last_name=platform_data.get("last_name"),
            platform_type=platform_type,
            platform_user_id=platform_user_id,
            platform_username=platform_data.get("username"),
            language=self._detect_language_from_platform(platform_type, platform_data),
            country_code=self._detect_country_from_platform(platform_type, platform_data),
            default_currency=self._detect_currency_from_country(platform_data.get("country_code", "US")),
            timezone=self._detect_timezone_from_platform(platform_type, platform_data)
        )
        
        return await self.register_user(request)
    
    async def add_platform_to_user(self, user_id: str, platform_type: str, 
                                 platform_user_id: str, platform_data: Dict[str, Any] = None) -> RegistrationResult:
        """
        Add a new platform to an existing user
        
        Args:
            user_id: Existing user ID
            platform_type: New platform type
            platform_user_id: Platform-specific user ID
            platform_data: Additional platform data
            
        Returns:
            Result of platform addition
        """
        
        try:
            # Get existing user
            user = await self.database.get_user(user_id)
            if not user:
                return RegistrationResult(
                    success=False,
                    error="User not found",
                    message="Cannot add platform to non-existent user"
                )
            
            # Check if platform already exists
            existing_platform = await self.database.get_user_by_platform(platform_type, platform_user_id)
            if existing_platform:
                return RegistrationResult(
                    success=False,
                    error="Platform already linked to another user",
                    message="This platform account is already linked"
                )
            
            # Create new platform
            platform_data = platform_data or {}
            platform = UserPlatform(
                user_id=user_id,
                platform_type=platform_type,
                platform_user_id=platform_user_id,
                platform_username=platform_data.get("username"),
                is_active=True,
                is_primary=False,  # Don't make it primary automatically
                notification_enabled=True,
                device_info=platform_data.get("device_info", {}),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Save platform
            saved_platform = await self.database.create_user_platform(platform)
            
            # Log activity
            await self.database._log_user_activity(
                user_id,
                "platform_added",
                {
                    "platform_type": platform_type,
                    "platform_user_id": platform_user_id
                },
                platform_type
            )
            
            return RegistrationResult(
                success=True,
                user=user,
                platform=saved_platform,
                message=f"Platform {platform_type} added successfully"
            )
            
        except Exception as e:
            print(f"❌ Add platform error: {e}")
            return RegistrationResult(
                success=False,
                error=str(e),
                message="Failed to add platform"
            )
    
    async def verify_user(self, verification_token: str, verification_code: str = None) -> Dict[str, Any]:
        """
        Verify user email or phone number
        
        Args:
            verification_token: Token from registration
            verification_code: Optional verification code (for SMS)
            
        Returns:
            Verification result
        """
        
        try:
            # Get token data
            token_data = self.verification_tokens.get(verification_token)
            if not token_data:
                return {
                    "success": False,
                    "error": "Invalid or expired verification token"
                }
            
            # Check expiration
            if datetime.now() > token_data["expires_at"]:
                del self.verification_tokens[verification_token]
                return {
                    "success": False,
                    "error": "Verification token has expired"
                }
            
            # For email verification, no code needed
            # For phone verification, code would be validated here
            if token_data["type"] == "phone" and verification_code:
                # In production, validate SMS code
                pass
            
            # Update user verification status
            user = await self.database.get_user(token_data["user_id"])
            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }
            
            if token_data["type"] == "email":
                user.email_verified = True
            elif token_data["type"] == "phone":
                user.phone_verified = True
            
            user.updated_at = datetime.now()
            await self.database.update_user(user)
            
            # Remove token
            del self.verification_tokens[verification_token]
            
            # Log verification
            await self.database._log_user_activity(
                user.id,
                "verification_completed",
                {
                    "type": token_data["type"],
                    "value": token_data["value"]
                }
            )
            
            return {
                "success": True,
                "message": f"{token_data['type'].title()} verified successfully",
                "user": user
            }
            
        except Exception as e:
            print(f"❌ Verification error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive user profile with platforms
        
        Args:
            user_id: User ID
            
        Returns:
            User profile data
        """
        
        try:
            user = await self.database.get_user(user_id)
            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }
            
            # Get user platforms
            platforms = await self.database.get_user_platforms(user_id)
            
            # Get activity summary
            activity = await self.database.get_user_activity_summary(user_id)
            
            return {
                "success": True,
                "user": user.to_dict() if hasattr(user, 'to_dict') else user.__dict__,
                "platforms": [p.to_dict() if hasattr(p, 'to_dict') else p.__dict__ for p in platforms],
                "activity_summary": {
                    "total_interactions": activity.total_interactions,
                    "active_platforms": activity.active_platforms,
                    "last_expense_date": activity.last_expense_date.isoformat() if activity.last_expense_date else None,
                    "last_reminder_date": activity.last_reminder_date.isoformat() if activity.last_reminder_date else None,
                    "is_active_user": activity.is_active_user()
                },
                "subscription": {
                    "status": user.subscription_status,
                    "is_premium": user.is_premium(),
                    "expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None
                }
            }
            
        except Exception as e:
            print(f"❌ Get profile error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user profile information
        
        Args:
            user_id: User ID
            updates: Dictionary of fields to update
            
        Returns:
            Update result
        """
        
        try:
            user = await self.database.get_user(user_id)
            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }
            
            # Update allowed fields
            allowed_fields = [
                'first_name', 'last_name', 'email', 'phone_number',
                'country_code', 'timezone', 'language', 'default_currency',
                'notification_preferences', 'expense_categories_custom'
            ]
            
            updated_fields = []
            for field, value in updates.items():
                if field in allowed_fields and hasattr(user, field):
                    setattr(user, field, value)
                    updated_fields.append(field)
            
            if updated_fields:
                user.updated_at = datetime.now()
                await self.database.update_user(user)
                
                # Log update
                await self.database._log_user_activity(
                    user_id,
                    "profile_updated",
                    {"updated_fields": updated_fields}
                )
            
            return {
                "success": True,
                "message": f"Profile updated: {', '.join(updated_fields)}",
                "updated_fields": updated_fields,
                "user": user
            }
            
        except Exception as e:
            print(f"❌ Update profile error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ============================================================================
    # PRIVATE HELPER METHODS
    # ============================================================================
    
    
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _is_valid_phone(self, phone: str) -> bool:
        """Validate phone number format"""
        # Simple validation - in production use a proper library
        pattern = r'^\+?[\d\s\-\(\)]{10,}$'
        return re.match(pattern, phone) is not None
    
    async def _check_existing_user(self, request: RegistrationRequest) -> Optional[User]:
        """Check if user already exists"""
        
        if request.email:
            user = await self.database.get_user_by_email(request.email)
            if user:
                return user
        
        if request.phone_number:
            user = await self.database.get_user_by_phone(request.phone_number)
            if user:
                return user
        
        # Check platform-specific user
        if request.platform_user_id:
            existing = await self.database.get_user_by_platform(
                request.platform_type, 
                request.platform_user_id
            )
            if existing:
                return existing[0]  # Return user from tuple
        
        return None
    
    async def _handle_existing_user(self, existing_user: User, request: RegistrationRequest) -> RegistrationResult:
        """Handle registration when user already exists"""
        
        # If it's a new platform for existing user
        if request.platform_user_id:
            result = await self.add_platform_to_user(
                existing_user.id,
                request.platform_type,
                request.platform_user_id,
                {"username": request.platform_username}
            )
            if result.success:
                return RegistrationResult(
                    success=True,
                    user=existing_user,
                    platform=result.platform,
                    message=f"Platform {request.platform_type} linked to existing account"
                )
        
        return RegistrationResult(
            success=False,
            error="User already exists",
            message="An account with this email/phone already exists"
        )
    
    
    
    async def _create_verification_token(self, user_id: str, verification_type: str, value: str) -> str:
        """Create verification token"""
        
        token = secrets.token_urlsafe(32)
        
        self.verification_tokens[token] = {
            "user_id": user_id,
            "type": verification_type,
            "value": value,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=24)
        }
        
        # In production, send verification email/SMS here
        print(f"🔐 Verification token created: {token} for {verification_type}: {value}")
        
        return token
    
    def _detect_language_from_platform(self, platform_type: str, platform_data: Dict[str, Any]) -> str:
        """Detect language from platform data"""
        # Could use platform-specific language detection
        return platform_data.get("language_code", "en")
    
    def _detect_country_from_platform(self, platform_type: str, platform_data: Dict[str, Any]) -> str:
        """Detect country from platform data"""
        # Could use platform location or locale data
        return platform_data.get("country_code", "US")
    
    def _detect_currency_from_country(self, country_code: str) -> str:
        """Detect currency from country code"""
        currency_map = {
            "US": "USD",
            "GB": "GBP", 
            "EU": "EUR",
            "BR": "BRL",
            "CA": "CAD",
            "AU": "AUD",
            "JP": "JPY",
            "CN": "CNY"
        }
        return currency_map.get(country_code, "USD")
    
    def _detect_timezone_from_platform(self, platform_type: str, platform_data: Dict[str, Any]) -> str:
        """Detect timezone from platform data"""
        # Could use platform location data
        return platform_data.get("timezone", "UTC")

# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def register_telegram_user(database: Database, telegram_id: str, user_data: Dict[str, Any]) -> RegistrationResult:
    """Convenience function for Telegram user registration"""
    service = UserRegistrationService(database)
    return await service.quick_platform_registration("telegram", telegram_id, user_data)

async def register_whatsapp_user(database: Database, whatsapp_id: str, user_data: Dict[str, Any]) -> RegistrationResult:
    """Convenience function for WhatsApp user registration"""
    service = UserRegistrationService(database)
    return await service.quick_platform_registration("whatsapp", whatsapp_id, user_data)

async def register_mobile_user(database: Database, device_id: str, user_data: Dict[str, Any]) -> RegistrationResult:
    """Convenience function for mobile app user registration"""
    service = UserRegistrationService(database)
    return await service.quick_platform_registration("mobile_app", device_id, user_data)

async def register_web_user(database: Database, registration_data: Dict[str, Any]) -> RegistrationResult:
    """Convenience function for web app user registration"""
    service = UserRegistrationService(database)
    request = RegistrationRequest(**registration_data)
    return await service.register_user(request)