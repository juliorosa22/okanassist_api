# core/models.py - Supabase integrated version
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
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

class PlatformType(Enum):
    """Platform type enumeration"""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    MOBILE_APP = "mobile_app"
    WEB_APP = "web_app"

class TransactionType(Enum):
    """Transaction type enumeration"""
    EXPENSE = "expense"
    INCOME = "income"

@dataclass
class Transaction:
    """Transaction model - handles both expenses and income"""
    user_id: str  # Supabase auth.users.id (UUID)
    amount: Decimal
    description: str
    category: str
    transaction_type: str   # 'expense' or 'income'
    original_message: str
    source_platform: str = PlatformType.WEB_APP.value
    merchant: Optional[str] = None
    date: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Enhanced fields
    receipt_image_url: Optional[str] = None
    location: Optional[Dict[str, float]] = None  # {'lat': x, 'lng': y}
    is_recurring: bool = False
    recurring_pattern: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    confidence_score: Optional[float] = None  # For ML-parsed transactions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': float(self.amount),
            'description': self.description,
            'category': self.category,
            'transaction_type': self.transaction_type,
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
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_expense(self) -> bool:
        """Check if this is an expense"""
        return self.transaction_type == TransactionType.EXPENSE.value
    
    def is_income(self) -> bool:
        """Check if this is income"""
        return self.transaction_type == TransactionType.INCOME.value

@dataclass
class Reminder:
    """Reminder model - updated for Supabase"""
    user_id: str  # Supabase auth.users.id (UUID)
    title: str
    description: str
    source_platform: str = PlatformType.WEB_APP.value
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
    
    # Enhanced fields
    location_reminder: Optional[Dict[str, Any]] = None
    attachments: List[str] = field(default_factory=list)
    assigned_to_platforms: List[str] = field(default_factory=list)
    
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

    def is_overdue(self) -> bool:
        """Check if reminder is overdue"""
        if not self.due_datetime or self.is_completed:
            return False
        return datetime.now() > self.due_datetime

    def get_formatted_summary(self) -> str:
        """Get formatted summary for display"""
        status_emoji = "✅" if self.is_completed else ("⚠️" if self.is_overdue() else "⏰")
        priority_indicator = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(self.priority, "🟡")
        
        due_text = ""
        if self.due_datetime:
            due_text = f" (Due: {self.due_datetime.strftime('%m/%d %H:%M')})"
        
        return f"{status_emoji} {priority_indicator} {self.title}{due_text}"

    def get_status_text(self) -> str:
        """Get status text for the reminder"""
        if self.is_completed:
            return "completed"
        elif self.is_overdue():
            return "overdue"
        elif self.due_datetime and self.due_datetime.date() == datetime.now().date():
            return "due_today"
        elif self.due_datetime and self.due_datetime.date() == (datetime.now() + timedelta(days=1)).date():
            return "due_tomorrow"
        else:
            return "pending"

@dataclass
class TransactionSummary:
    """Summary of user transactions (expenses + income)"""
    total_expenses: Decimal
    total_income: Decimal
    net_income: Decimal  # income - expenses
    expense_count: int
    income_count: int
    average_expense: Decimal
    average_income: Decimal
    expense_categories: List[Dict[str, Any]]
    income_categories: List[Dict[str, Any]]
    period_days: int
    
    def get_formatted_net_income(self) -> str:
        """Get formatted net income with appropriate sign"""
        if self.net_income >= 0:
            return f"+${self.net_income:.2f}"
        else:
            return f"-${abs(self.net_income):.2f}"
    
    def get_top_expense_category(self) -> Optional[str]:
        """Get top expense category by amount"""
        if not self.expense_categories:
            return None
        return max(self.expense_categories, key=lambda x: x.get('total', 0))['category']
    
    def get_top_income_category(self) -> Optional[str]:
        """Get top income category by amount"""
        if not self.income_categories:
            return None
        return max(self.income_categories, key=lambda x: x.get('total', 0))['category']
    
    def is_profitable(self) -> bool:
        """Check if user has positive cash flow"""
        return self.net_income > 0

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

    def has_urgent_items(self) -> bool:
        """Check if there are any urgent priority items"""
        return self.by_priority.get('urgent', 0) > 0

@dataclass
class UserActivity:
    """Overall user activity summary (Supabase version)"""
    user_id: str  # Supabase auth.users.id
    transaction_summary: Optional[TransactionSummary] = None
    reminder_summary: Optional[ReminderSummary] = None
    last_transaction_date: Optional[datetime] = None
    last_reminder_date: Optional[datetime] = None
    total_interactions: int = 0
    
    def is_active_user(self, days: int = 7) -> bool:
        cutoff = datetime.now() - timedelta(days=days)
        return (
            (self.last_transaction_date and self.last_transaction_date > cutoff) or
            (self.last_reminder_date and self.last_reminder_date > cutoff)
        )

# Transaction categories for intelligent classification
TRANSACTION_CATEGORIES = {
    # Expense categories
     "expense": {
        "Essentials": [
          "rent", "mortgage", "utility", "electric", "water", "gas", "fuel", "groceries", "grocery", "food", "insurance", "phone", "internet", "healthcare", "doctor", "pharmacy", "medicine", "medical", "dentist"
        ],
        "Food & Dining": ["restaurant", "coffee", "lunch", "dinner", "takeout", "starbucks", "mcdonalds"],
        "Transportation": ["uber", "taxi", "parking", "bus", "train", "flight", "lyft"],
        "Shopping": ["amazon", "store", "clothes", "electronics", "book", "shopping", "mall"],
        "Entertainment": ["movie", "game", "concert", "netflix", "spotify", "streaming", "music"],
        "Utilities": ["utility"],
        "Healthcare": ["doctor", "hospital", "pharmacy", "medicine", "dentist", "medical"],  # Also in Essentials
        "Travel": ["hotel", "airbnb", "vacation", "trip", "booking", "travel"],
        "Education": ["school", "course", "tuition", "book", "education", "training"]
      },
    # Income categories
    "income": {
        "Salary": ["salary", "paycheck", "wage", "income", "pay"],
        "Freelance": ["freelance", "contract", "consulting", "gig", "project"],
        "Business": ["business", "revenue", "sales", "profit", "commission"],
        "Investment": ["dividend", "interest", "stock", "crypto", "investment", "return"],
        "Gift": ["gift", "bonus", "present", "reward", "prize"],
        "Refund": ["refund", "return", "reimbursement", "cashback"],
        "Rental": ["rent", "rental", "lease", "property"],
        "Other": []
    }
}

def categorize_transaction(description: str, transaction_type: str) -> str:
    """
    Categorize transaction based on description keywords and type
    
    Args:
        description: Transaction description text
        transaction_type: 'expense' or 'income'
        
    Returns:
        Category name as string
    """
    if not description or transaction_type not in TRANSACTION_CATEGORIES:
        return "Other"
    
    description_lower = description.lower()
    categories = TRANSACTION_CATEGORIES[transaction_type]
    
    # Score each category based on keyword matches
    category_scores = {}
    for category, keywords in categories.items():
        if keywords:  # Skip empty keyword lists (like "Other")
            score = sum(1 for keyword in keywords if keyword in description_lower)
            if score > 0:
                category_scores[category] = score
    
    # Return category with highest score or "Other" if no matches
    if category_scores:
        return max(category_scores.keys(), key=lambda k: category_scores[k])
    
    return "Other"

def get_all_categories(transaction_type: str) -> List[str]:
    """Get list of all available categories for a transaction type"""
    if transaction_type in TRANSACTION_CATEGORIES:
        return list(TRANSACTION_CATEGORIES[transaction_type].keys())
    return ["Other"]