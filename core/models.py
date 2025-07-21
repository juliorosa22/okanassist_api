# core/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from decimal import Decimal
from enum import Enum
import uuid

class ReminderType(Enum):
    """Reminder type enumeration"""
    TASK = "task"
    EVENT = "event"
    DEADLINE = "deadline"
    HABIT = "habit"
    GENERAL = "general"

class Priority(Enum):
    """Priority level enumeration"""
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class PlatformType(Enum):
    """Platform type enumeration"""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    MOBILE_APP = "mobile_app"
    WEB_APP = "web_app"

class SubscriptionStatus(Enum):
    """Subscription status enumeration"""
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    TRIAL = "trial"
    SUSPENDED = "suspended"

@dataclass
class User:
    """Main user model - platform agnostic"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    email: Optional[str] = None
    phone_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    country_code: str = "US"  # ISO country code
    timezone: str = "UTC"  # Timezone identifier
    language: str = "en"  # Language preference
    subscription_status: str = SubscriptionStatus.FREE.value
    subscription_expires_at: Optional[datetime] = None
    is_active: bool = True
    email_verified: bool = False
    phone_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    
    # Preferences
    notification_preferences: Dict[str, Any] = field(default_factory=dict)
    expense_categories_custom: List[str] = field(default_factory=list)
    default_currency: str = "USD"
    
    def get_display_name(self) -> str:
        """Get user's display name"""
        if self.first_name:
            return f"{self.first_name} {self.last_name or ''}".strip()
        return self.email or self.id[:8]
    
    def is_premium(self) -> bool:
        """Check if user has premium subscription"""
        return self.subscription_status in [SubscriptionStatus.PREMIUM.value, SubscriptionStatus.ENTERPRISE.value]
    
    def is_subscription_active(self) -> bool:
        """Check if subscription is currently active"""
        if not self.subscription_expires_at:
            return self.subscription_status == SubscriptionStatus.FREE.value
        return datetime.now() < self.subscription_expires_at

@dataclass
class UserPlatform:
    """Links users to specific platforms (Telegram, WhatsApp, App, etc.)"""
    id: Optional[int] = None
    user_id: str = ""  # Foreign key to User.id
    platform_type: str = PlatformType.TELEGRAM.value
    platform_user_id: str = ""  # telegram_id, whatsapp_number, device_id, etc.
    platform_username: Optional[str] = None  # @username for telegram, etc.
    is_active: bool = True
    is_primary: bool = False  # Primary platform for notifications
    
    # Platform-specific settings
    notification_enabled: bool = True
    notification_settings: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    device_info: Optional[Dict[str, str]] = field(default_factory=dict)  # For mobile apps
    last_activity_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'platform_type': self.platform_type,
            'platform_user_id': self.platform_user_id,
            'platform_username': self.platform_username,
            'is_active': self.is_active,
            'is_primary': self.is_primary,
            'notification_enabled': self.notification_enabled,
            'notification_settings': self.notification_settings,
            'device_info': self.device_info,
            'last_activity_at': self.last_activity_at.isoformat() if self.last_activity_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

@dataclass
class Expense:
    """Expense model - now linked to User.id instead of telegram_id"""
    user_id: str  # Foreign key to User.id (changed from user_telegram_id)
    amount: Decimal
    description: str
    category: str
    original_message: str
    source_platform: str = PlatformType.TELEGRAM.value  # Which platform created this
    merchant: Optional[str] = None
    date: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    # Enhanced fields for mobile app integration
    receipt_image_url: Optional[str] = None
    location: Optional[Dict[str, float]] = None  # {'lat': x, 'lng': y}
    is_recurring: bool = False
    recurring_pattern: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    confidence_score: Optional[float] = None  # For ML-parsed expenses
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': float(self.amount),
            'description': self.description,
            'category': self.category,
            'original_message': self.original_message,
            'source_platform': self.source_platform,
            'merchant': self.merchant,
            'date': self.date.isoformat() if self.date else None,
            'receipt_image_url': self.receipt_image_url,
            'location': self.location,
            'is_recurring': self.is_recurring,
            'recurring_pattern': self.recurring_pattern,
            'tags': self.tags,
            'confidence_score': self.confidence_score,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

@dataclass
class Reminder:
    """Reminder model - now linked to User.id instead of telegram_id"""
    user_id: str  # Foreign key to User.id (changed from user_telegram_id)
    title: str
    description: str
    source_platform: str = PlatformType.TELEGRAM.value  # Which platform created this
    due_datetime: Optional[datetime] = None
    reminder_type: str = ReminderType.GENERAL.value
    priority: str = Priority.MEDIUM.value
    is_completed: bool = False
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None
    notification_sent: bool = False
    snooze_until: Optional[datetime] = None
    tags: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Enhanced fields for mobile app
    location_reminder: Optional[Dict[str, Any]] = None  # Location-based reminders
    attachments: List[str] = field(default_factory=list)  # File URLs
    assigned_to_platforms: List[str] = field(default_factory=list)  # Specific platform notifications
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'source_platform': self.source_platform,
            'due_datetime': self.due_datetime.isoformat() if self.due_datetime else None,
            'reminder_type': self.reminder_type,
            'priority': self.priority,
            'is_completed': self.is_completed,
            'is_recurring': self.is_recurring,
            'recurrence_pattern': self.recurrence_pattern,
            'notification_sent': self.notification_sent,
            'snooze_until': self.snooze_until.isoformat() if self.snooze_until else None,
            'tags': self.tags,
            'location_reminder': self.location_reminder,
            'attachments': self.attachments,
            'assigned_to_platforms': self.assigned_to_platforms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# Keep existing summary models but update references
@dataclass
class ExpenseSummary:
    """Summary of user expenses"""
    total_amount: Decimal
    total_count: int
    average_amount: Decimal
    categories: list
    period_days: int
    
    def get_formatted_total(self) -> str:
        return f"${self.total_amount:.2f}"
    
    def get_formatted_average(self) -> str:
        return f"${self.average_amount:.2f}"
    
    def get_top_category(self) -> Optional[str]:
        if not self.categories:
            return None
        return max(self.categories, key=lambda x: x.get('total', 0))['category']

@dataclass 
class ReminderSummary:
    """Summary of user reminders"""
    total_count: int
    completed_count: int
    pending_count: int
    overdue_count: int
    due_today_count: int
    due_tomorrow_count: int
    by_priority: Dict[str, int]
    by_type: Dict[str, int]
    period_days: int
    
    def get_completion_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return (self.completed_count / self.total_count) * 100

@dataclass
class UserActivity:
    """Overall user activity summary"""
    user_id: str  # Changed from user_telegram_id
    expense_summary: Optional[ExpenseSummary] = None
    reminder_summary: Optional[ReminderSummary] = None
    last_expense_date: Optional[datetime] = None
    last_reminder_date: Optional[datetime] = None
    total_interactions: int = 0
    active_platforms: List[str] = field(default_factory=list)
    
    def is_active_user(self, days: int = 7) -> bool:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        return (
            (self.last_expense_date and self.last_expense_date > cutoff) or
            (self.last_reminder_date and self.last_reminder_date > cutoff)
        )

# Utility functions for model operations
def create_user_from_platform_data(platform_type: str, platform_data: Dict[str, Any]) -> tuple[User, UserPlatform]:
    """Create User and UserPlatform from platform-specific data"""
    user = User(
        first_name=platform_data.get('first_name'),
        last_name=platform_data.get('last_name'),
        email=platform_data.get('email'),
        phone_number=platform_data.get('phone_number'),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    platform = UserPlatform(
        user_id=user.id,
        platform_type=platform_type,
        platform_user_id=str(platform_data.get('platform_user_id', '')),
        platform_username=platform_data.get('username'),
        is_primary=True,  # First platform is primary
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    return user, platform

def validate_user_data(data: Dict[str, Any]) -> bool:
    """Validate user data"""
    if not data.get('email') and not data.get('phone_number'):
        return False  # Must have at least one contact method
    
    return True

def validate_platform_data(data: Dict[str, Any]) -> bool:
    """Validate platform data"""
    required_fields = ['user_id', 'platform_type', 'platform_user_id']
    return all(field in data and data[field] for field in required_fields)