# core/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from decimal import Decimal
from enum import Enum

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

@dataclass
class User:
    """User model"""
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def get_display_name(self) -> str:
        """Get user's display name"""
        if self.first_name:
            return f"{self.first_name} {self.last_name or ''}".strip()
        return self.username or self.telegram_id

@dataclass
class Expense:
    """Expense model - ready for RAG embeddings later"""
    user_telegram_id: str
    amount: Decimal
    description: str
    category: str
    original_message: str  # Store for RAG embeddings later
    merchant: Optional[str] = None
    date: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'id': self.id,
            'user_telegram_id': self.user_telegram_id,
            'amount': float(self.amount),
            'description': self.description,
            'category': self.category,
            'original_message': self.original_message,
            'merchant': self.merchant,
            'date': self.date.isoformat() if self.date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def get_formatted_amount(self) -> str:
        """Get formatted amount string"""
        return f"${self.amount:.2f}"
    
    def is_large_expense(self, threshold: float = 100.0) -> bool:
        """Check if expense is above threshold"""
        return float(self.amount) >= threshold

@dataclass
class Reminder:
    """Reminder model for scheduling and task management"""
    user_telegram_id: str
    title: str
    description: str
    due_datetime: Optional[datetime] = None
    reminder_type: str = ReminderType.GENERAL.value
    priority: str = Priority.MEDIUM.value
    is_completed: bool = False
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None  # For future recurring reminders
    notification_sent: bool = False
    snooze_until: Optional[datetime] = None
    tags: Optional[str] = None  # Comma-separated tags
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'id': self.id,
            'user_telegram_id': self.user_telegram_id,
            'title': self.title,
            'description': self.description,
            'due_datetime': self.due_datetime.isoformat() if self.due_datetime else None,
            'reminder_type': self.reminder_type,
            'priority': self.priority,
            'is_completed': self.is_completed,
            'is_recurring': self.is_recurring,
            'recurrence_pattern': self.recurrence_pattern,
            'notification_sent': self.notification_sent,
            'snooze_until': self.snooze_until.isoformat() if self.snooze_until else None,
            'tags': self.tags,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_overdue(self) -> bool:
        """Check if reminder is overdue"""
        if not self.due_datetime or self.is_completed:
            return False
        return datetime.now() > self.due_datetime
    
    def is_due_soon(self, hours_ahead: int = 24) -> bool:
        """Check if reminder is due within specified hours"""
        if not self.due_datetime or self.is_completed:
            return False
        from datetime import timedelta
        return datetime.now() <= self.due_datetime <= datetime.now() + timedelta(hours=hours_ahead)
    
    def is_snoozed(self) -> bool:
        """Check if reminder is currently snoozed"""
        if not self.snooze_until:
            return False
        return datetime.now() < self.snooze_until
    
    def get_priority_emoji(self) -> str:
        """Get emoji representation of priority"""
        priority_emojis = {
            Priority.URGENT.value: "🚨",
            Priority.HIGH.value: "🔴",
            Priority.MEDIUM.value: "🟡",
            Priority.LOW.value: "🟢"
        }
        return priority_emojis.get(self.priority, "⚪")
    
    def get_type_emoji(self) -> str:
        """Get emoji representation of reminder type"""
        type_emojis = {
            ReminderType.TASK.value: "✅",
            ReminderType.EVENT.value: "📅",
            ReminderType.DEADLINE.value: "⏰",
            ReminderType.HABIT.value: "🔄",
            ReminderType.GENERAL.value: "📝"
        }
        return type_emojis.get(self.reminder_type, "📝")
    
    def get_status_text(self) -> str:
        """Get human-readable status"""
        if self.is_completed:
            return "✅ Completed"
        elif self.is_snoozed():
            return f"😴 Snoozed until {self.snooze_until.strftime('%m/%d %H:%M')}"
        elif self.is_overdue():
            return "⚠️ Overdue"
        elif self.is_due_soon(2):  # Due within 2 hours
            return "🔔 Due soon"
        elif self.due_datetime:
            return f"📅 Due {self.due_datetime.strftime('%m/%d %H:%M')}"
        else:
            return "📝 No due date"
    
    def get_formatted_summary(self) -> str:
        """Get formatted one-line summary"""
        priority_emoji = self.get_priority_emoji()
        type_emoji = self.get_type_emoji()
        status = self.get_status_text()
        
        return f"{priority_emoji}{type_emoji} {self.title} - {status}"
    
    def get_tags_list(self) -> list:
        """Get tags as a list"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the reminder"""
        current_tags = self.get_tags_list()
        if tag not in current_tags:
            current_tags.append(tag)
            self.tags = ', '.join(current_tags)
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the reminder"""
        current_tags = self.get_tags_list()
        if tag in current_tags:
            current_tags.remove(tag)
            self.tags = ', '.join(current_tags) if current_tags else None

@dataclass
class ExpenseSummary:
    """Summary of user expenses"""
    total_amount: Decimal
    total_count: int
    average_amount: Decimal
    categories: list
    period_days: int
    
    def get_formatted_total(self) -> str:
        """Get formatted total amount"""
        return f"${self.total_amount:.2f}"
    
    def get_formatted_average(self) -> str:
        """Get formatted average amount"""
        return f"${self.average_amount:.2f}"
    
    def get_top_category(self) -> Optional[str]:
        """Get the category with highest spending"""
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
        """Get completion rate as percentage"""
        if self.total_count == 0:
            return 0.0
        return (self.completed_count / self.total_count) * 100
    
    def get_formatted_completion_rate(self) -> str:
        """Get formatted completion rate"""
        return f"{self.get_completion_rate():.1f}%"
    
    def has_urgent_items(self) -> bool:
        """Check if there are urgent items"""
        return self.by_priority.get(Priority.URGENT.value, 0) > 0
    
    def get_priority_summary(self) -> str:
        """Get priority breakdown summary"""
        urgent = self.by_priority.get(Priority.URGENT.value, 0)
        high = self.by_priority.get(Priority.HIGH.value, 0)
        medium = self.by_priority.get(Priority.MEDIUM.value, 0)
        low = self.by_priority.get(Priority.LOW.value, 0)
        
        parts = []
        if urgent > 0:
            parts.append(f"🚨 {urgent} urgent")
        if high > 0:
            parts.append(f"🔴 {high} high")
        if medium > 0:
            parts.append(f"🟡 {medium} medium")
        if low > 0:
            parts.append(f"🟢 {low} low")
        
        return ", ".join(parts) if parts else "No priority items"

@dataclass
class UserActivity:
    """Overall user activity summary"""
    user_telegram_id: str
    expense_summary: Optional[ExpenseSummary] = None
    reminder_summary: Optional[ReminderSummary] = None
    last_expense_date: Optional[datetime] = None
    last_reminder_date: Optional[datetime] = None
    total_interactions: int = 0
    
    def is_active_user(self, days: int = 7) -> bool:
        """Check if user has been active recently"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        return (
            (self.last_expense_date and self.last_expense_date > cutoff) or
            (self.last_reminder_date and self.last_reminder_date > cutoff)
        )
    
    def get_activity_score(self) -> float:
        """Get activity score based on usage patterns"""
        score = 0.0
        
        # Points for having data
        if self.expense_summary and self.expense_summary.total_count > 0:
            score += 1.0
        if self.reminder_summary and self.reminder_summary.total_count > 0:
            score += 1.0
        
        # Points for recent activity
        if self.is_active_user(7):
            score += 2.0
        elif self.is_active_user(30):
            score += 1.0
        
        # Points for completion rate
        if self.reminder_summary:
            completion_rate = self.reminder_summary.get_completion_rate()
            score += (completion_rate / 100) * 1.0
        
        return min(score, 5.0)  # Cap at 5.0

# Utility functions for model operations
def create_reminder_from_dict(data: Dict[str, Any]) -> Reminder:
    """Create Reminder object from dictionary"""
    return Reminder(
        id=data.get('id'),
        user_telegram_id=data['user_telegram_id'],
        title=data['title'],
        description=data['description'],
        due_datetime=datetime.fromisoformat(data['due_datetime']) if data.get('due_datetime') else None,
        reminder_type=data.get('reminder_type', ReminderType.GENERAL.value),
        priority=data.get('priority', Priority.MEDIUM.value),
        is_completed=data.get('is_completed', False),
        is_recurring=data.get('is_recurring', False),
        recurrence_pattern=data.get('recurrence_pattern'),
        notification_sent=data.get('notification_sent', False),
        snooze_until=datetime.fromisoformat(data['snooze_until']) if data.get('snooze_until') else None,
        tags=data.get('tags'),
        created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
        completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
        updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
    )

def create_expense_from_dict(data: Dict[str, Any]) -> Expense:
    """Create Expense object from dictionary"""
    return Expense(
        id=data.get('id'),
        user_telegram_id=data['user_telegram_id'],
        amount=Decimal(str(data['amount'])),
        description=data['description'],
        category=data['category'],
        original_message=data['original_message'],
        merchant=data.get('merchant'),
        date=datetime.fromisoformat(data['date']) if data.get('date') else None,
        created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
    )

# Validation functions
def validate_reminder_data(data: Dict[str, Any]) -> bool:
    """Validate reminder data"""
    required_fields = ['user_telegram_id', 'title', 'description']
    
    # Check required fields
    for field in required_fields:
        if field not in data or not data[field]:
            return False
    
    # Validate enums
    if 'reminder_type' in data and data['reminder_type'] not in [t.value for t in ReminderType]:
        return False
    
    if 'priority' in data and data['priority'] not in [p.value for p in Priority]:
        return False
    
    return True

def validate_expense_data(data: Dict[str, Any]) -> bool:
    """Validate expense data"""
    required_fields = ['user_telegram_id', 'amount', 'description', 'category']
    
    # Check required fields
    for field in required_fields:
        if field not in data or not data[field]:
            return False
    
    # Validate amount
    try:
        amount = float(data['amount'])
        if amount <= 0:
            return False
    except (ValueError, TypeError):
        return False
    
    return True