# core/database.py
import asyncpg
import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    User, UserPlatform, Expense, ExpenseSummary, Reminder, ReminderSummary, 
    UserActivity, ReminderType, Priority, PlatformType, SubscriptionStatus
)

class Database:
    """Clean database manager with multi-platform user support"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
    
    async def connect(self):
        """Initialize database connection"""
        self.pool = await asyncpg.create_pool(self.database_url)
        await self._create_tables()
        print("✅ Database connected with multi-platform support")
    
    async def close(self):
        """Close database connection"""
        if self.pool:
            await self.pool.close()
            print("✅ Database disconnected")
    
    async def _create_tables(self):
        """Create all necessary tables with clean multi-platform structure"""
        async with self.pool.acquire() as conn:
            # Main users table (platform agnostic)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE,
                    phone_number TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    country_code TEXT DEFAULT 'US',
                    timezone TEXT DEFAULT 'UTC',
                    language TEXT DEFAULT 'en',
                    subscription_status TEXT DEFAULT 'free' CHECK (subscription_status IN ('free', 'premium', 'enterprise', 'trial', 'suspended')),
                    subscription_expires_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    email_verified BOOLEAN DEFAULT FALSE,
                    phone_verified BOOLEAN DEFAULT FALSE,
                    notification_preferences JSONB DEFAULT '{}',
                    expense_categories_custom JSONB DEFAULT '[]',
                    default_currency TEXT DEFAULT 'USD',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    last_login_at TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone_number);
                CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(subscription_status);
                CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);
            """)
            
            # User platforms table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_platforms (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
                    platform_type TEXT NOT NULL CHECK (platform_type IN ('telegram', 'whatsapp', 'mobile_app', 'web_app')),
                    platform_user_id TEXT NOT NULL,
                    platform_username TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_primary BOOLEAN DEFAULT FALSE,
                    notification_enabled BOOLEAN DEFAULT TRUE,
                    notification_settings JSONB DEFAULT '{}',
                    device_info JSONB DEFAULT '{}',
                    last_activity_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    
                    UNIQUE(platform_type, platform_user_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_platforms_user ON user_platforms(user_id);
                CREATE INDEX IF NOT EXISTS idx_platforms_type ON user_platforms(platform_type);
                CREATE INDEX IF NOT EXISTS idx_platforms_platform_user ON user_platforms(platform_user_id);
                CREATE INDEX IF NOT EXISTS idx_platforms_primary ON user_platforms(is_primary);
            """)
            
            # Expenses table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
                    amount DECIMAL(10,2) NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    original_message TEXT NOT NULL,
                    source_platform TEXT DEFAULT 'telegram' CHECK (source_platform IN ('telegram', 'whatsapp', 'mobile_app', 'web_app')),
                    merchant TEXT,
                    date TIMESTAMP DEFAULT NOW(),
                    receipt_image_url TEXT,
                    location JSONB,
                    is_recurring BOOLEAN DEFAULT FALSE,
                    recurring_pattern TEXT,
                    tags JSONB DEFAULT '[]',
                    confidence_score DECIMAL(3,2),
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_expenses_user ON expenses(user_id);
                CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
                CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
                CREATE INDEX IF NOT EXISTS idx_expenses_platform ON expenses(source_platform);
                CREATE INDEX IF NOT EXISTS idx_expenses_amount ON expenses(amount);
            """)
            
            # Reminders table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    source_platform TEXT DEFAULT 'telegram' CHECK (source_platform IN ('telegram', 'whatsapp', 'mobile_app', 'web_app')),
                    due_datetime TIMESTAMP,
                    reminder_type TEXT DEFAULT 'general' CHECK (reminder_type IN ('task', 'event', 'deadline', 'habit', 'general')),
                    priority TEXT DEFAULT 'medium' CHECK (priority IN ('urgent', 'high', 'medium', 'low')),
                    is_completed BOOLEAN DEFAULT FALSE,
                    is_recurring BOOLEAN DEFAULT FALSE,
                    recurrence_pattern TEXT,
                    notification_sent BOOLEAN DEFAULT FALSE,
                    snooze_until TIMESTAMP,
                    tags TEXT,
                    location_reminder JSONB,
                    attachments JSONB DEFAULT '[]',
                    assigned_to_platforms JSONB DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT NOW(),
                    completed_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id);
                CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(due_datetime);
                CREATE INDEX IF NOT EXISTS idx_reminders_platform ON reminders(source_platform);
                CREATE INDEX IF NOT EXISTS idx_reminders_completed ON reminders(is_completed);
                CREATE INDEX IF NOT EXISTS idx_reminders_priority ON reminders(priority);
                CREATE INDEX IF NOT EXISTS idx_reminders_type ON reminders(reminder_type);
                CREATE INDEX IF NOT EXISTS idx_reminders_notification ON reminders(notification_sent, due_datetime);
            """)
            
            # User activity table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
                    activity_type TEXT NOT NULL CHECK (activity_type IN ('expense_added', 'reminder_added', 'reminder_completed', 'summary_requested', 'query', 'login', 'platform_added', 'registration')),
                    platform_type TEXT,
                    activity_data JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_activity_user ON user_activity(user_id);
                CREATE INDEX IF NOT EXISTS idx_activity_type ON user_activity(activity_type);
                CREATE INDEX IF NOT EXISTS idx_activity_date ON user_activity(created_at);
            """)

    # ============================================================================
    # USER MANAGEMENT OPERATIONS
    # ============================================================================
    
    async def create_user(self, user: User) -> User:
        """Create a new user"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (
                    id, email, phone_number, first_name, last_name, country_code, timezone, language,
                    subscription_status, subscription_expires_at, is_active, email_verified, phone_verified,
                    notification_preferences, expense_categories_custom, default_currency, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    phone_number = EXCLUDED.phone_number,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    country_code = EXCLUDED.country_code,
                    timezone = EXCLUDED.timezone,
                    language = EXCLUDED.language,
                    updated_at = NOW()
            """, 
                user.id, user.email, user.phone_number, user.first_name, user.last_name,
                user.country_code, user.timezone, user.language, user.subscription_status,
                user.subscription_expires_at, user.is_active, user.email_verified, user.phone_verified,
                json.dumps(user.notification_preferences), json.dumps(user.expense_categories_custom),
                user.default_currency
            )
            return user
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
            return self._row_to_user(row) if row else None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
            return self._row_to_user(row) if row else None
    
    async def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        """Get user by phone number"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE phone_number = $1", phone_number)
            return self._row_to_user(row) if row else None
    
    async def update_user(self, user: User) -> User:
        """Update user information"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET
                    email = $2,
                    phone_number = $3,
                    first_name = $4,
                    last_name = $5,
                    country_code = $6,
                    timezone = $7,
                    language = $8,
                    subscription_status = $9,
                    subscription_expires_at = $10,
                    is_active = $11,
                    email_verified = $12,
                    phone_verified = $13,
                    notification_preferences = $14,
                    expense_categories_custom = $15,
                    default_currency = $16,
                    updated_at = NOW()
                WHERE id = $1
            """,
                user.id, user.email, user.phone_number, user.first_name, user.last_name,
                user.country_code, user.timezone, user.language, user.subscription_status,
                user.subscription_expires_at, user.is_active, user.email_verified, user.phone_verified,
                json.dumps(user.notification_preferences), json.dumps(user.expense_categories_custom),
                user.default_currency
            )
            return user
    
    async def update_user_last_login(self, user_id: str) -> None:
        """Update user's last login time"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_login_at = NOW(), updated_at = NOW() WHERE id = $1",
                user_id
            )
    
    async def get_all_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Get all users with pagination"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset
            )
            return [self._row_to_user(row) for row in rows]

    # ============================================================================
    # PLATFORM MANAGEMENT OPERATIONS
    # ============================================================================
    
    async def create_user_platform(self, platform: UserPlatform) -> UserPlatform:
        """Create or update a user platform"""
        async with self.pool.acquire() as conn:
            platform_id = await conn.fetchval("""
                INSERT INTO user_platforms (
                    user_id, platform_type, platform_user_id, platform_username,
                    is_active, is_primary, notification_enabled, notification_settings,
                    device_info, last_activity_at, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())
                ON CONFLICT (platform_type, platform_user_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    platform_username = EXCLUDED.platform_username,
                    is_active = EXCLUDED.is_active,
                    notification_enabled = EXCLUDED.notification_enabled,
                    updated_at = NOW()
                RETURNING id
            """,
                platform.user_id, platform.platform_type, platform.platform_user_id,
                platform.platform_username, platform.is_active, platform.is_primary,
                platform.notification_enabled, json.dumps(platform.notification_settings),
                json.dumps(platform.device_info), platform.last_activity_at
            )
            
            platform.id = platform_id
            return platform
    
    async def get_user_platforms(self, user_id: str) -> List[UserPlatform]:
        """Get all platforms for a user"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM user_platforms WHERE user_id = $1 ORDER BY is_primary DESC, created_at ASC",
                user_id
            )
            return [self._row_to_platform(row) for row in rows]
    
    async def get_user_by_platform(self, platform_type: str, platform_user_id: str) -> Optional[Tuple[User, UserPlatform]]:
        """Get user and platform info by platform credentials"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT u.*, up.* FROM users u
                JOIN user_platforms up ON u.id = up.user_id
                WHERE up.platform_type = $1 AND up.platform_user_id = $2 AND up.is_active = TRUE
            """, platform_type, platform_user_id)
            
            if row:
                user = self._row_to_user(row)
                platform = self._row_to_platform(row)
                return user, platform
            return None
    
    async def update_platform_activity(self, platform_type: str, platform_user_id: str) -> None:
        """Update platform last activity"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE user_platforms 
                SET last_activity_at = NOW(), updated_at = NOW()
                WHERE platform_type = $1 AND platform_user_id = $2
            """, platform_type, platform_user_id)
    
    async def set_primary_platform(self, user_id: str, platform_id: int) -> bool:
        """Set a platform as primary for a user"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Remove primary from all other platforms
                await conn.execute("""
                    UPDATE user_platforms 
                    SET is_primary = FALSE, updated_at = NOW()
                    WHERE user_id = $1
                """, user_id)
                
                # Set the specified platform as primary
                result = await conn.execute("""
                    UPDATE user_platforms 
                    SET is_primary = TRUE, updated_at = NOW()
                    WHERE id = $1 AND user_id = $2
                """, platform_id, user_id)
                
                return result != "UPDATE 0"

    # ============================================================================
    # EXPENSE OPERATIONS
    # ============================================================================
    
    async def save_expense(self, expense: Expense) -> Expense:
        """Save expense to database"""
        async with self.pool.acquire() as conn:
            expense_id = await conn.fetchval("""
                INSERT INTO expenses (
                    user_id, amount, description, category, original_message, source_platform,
                    merchant, date, receipt_image_url, location, is_recurring, recurring_pattern,
                    tags, confidence_score
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING id
            """, 
                expense.user_id, expense.amount, expense.description, expense.category,
                expense.original_message, expense.source_platform, expense.merchant, 
                expense.date or datetime.now(), expense.receipt_image_url,
                json.dumps(expense.location) if expense.location else None,
                expense.is_recurring, expense.recurring_pattern,
                json.dumps(expense.tags), expense.confidence_score
            )
            
            expense.id = expense_id
            
            # Log activity
            await self._log_user_activity(
                expense.user_id, 
                'expense_added', 
                {
                    'expense_id': expense_id, 
                    'amount': float(expense.amount), 
                    'category': expense.category,
                    'platform': expense.source_platform
                }
            )
            
            return expense
    
    async def get_user_expenses(self, user_id: str, days: int = 30) -> List[Expense]:
        """Get user's recent expenses"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM expenses 
                WHERE user_id = $1 
                AND date >= $2
                ORDER BY date DESC
            """, user_id, datetime.now() - timedelta(days=days))
            
            return [self._row_to_expense(row) for row in rows]
    
    async def get_expense_summary(self, user_id: str, days: int = 30) -> ExpenseSummary:
        """Get expense summary for user"""
        async with self.pool.acquire() as conn:
            # Total summary
            total_row = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total,
                    COALESCE(AVG(amount), 0) as average
                FROM expenses 
                WHERE user_id = $1 
                AND date >= $2
            """, user_id, datetime.now() - timedelta(days=days))
            
            # Category breakdown
            category_rows = await conn.fetch("""
                SELECT 
                    category,
                    COUNT(*) as count,
                    SUM(amount) as total
                FROM expenses 
                WHERE user_id = $1 
                AND date >= $2
                GROUP BY category
                ORDER BY total DESC
            """, user_id, datetime.now() - timedelta(days=days))
            
            categories = []
            for row in category_rows:
                categories.append({
                    'category': row['category'],
                    'count': row['count'],
                    'total': float(row['total'])
                })
            
            return ExpenseSummary(
                total_amount=total_row['total'],
                total_count=total_row['count'],
                average_amount=total_row['average'],
                categories=categories,
                period_days=days
            )

    # ============================================================================
    # REMINDER OPERATIONS
    # ============================================================================
    
    async def save_reminder(self, reminder: Reminder) -> Reminder:
        """Save reminder to database"""
        async with self.pool.acquire() as conn:
            reminder_id = await conn.fetchval("""
                INSERT INTO reminders (
                    user_id, title, description, source_platform, due_datetime,
                    reminder_type, priority, is_completed, is_recurring,
                    recurrence_pattern, notification_sent, snooze_until, tags,
                    location_reminder, attachments, assigned_to_platforms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING id
            """, 
                reminder.user_id, reminder.title, reminder.description, reminder.source_platform,
                reminder.due_datetime, reminder.reminder_type, reminder.priority,
                reminder.is_completed, reminder.is_recurring, reminder.recurrence_pattern,
                reminder.notification_sent, reminder.snooze_until, reminder.tags,
                json.dumps(reminder.location_reminder) if reminder.location_reminder else None,
                json.dumps(reminder.attachments), json.dumps(reminder.assigned_to_platforms)
            )
            
            reminder.id = reminder_id
            
            # Log activity
            await self._log_user_activity(
                reminder.user_id,
                'reminder_added',
                {
                    'reminder_id': reminder_id,
                    'title': reminder.title,
                    'due_datetime': reminder.due_datetime.isoformat() if reminder.due_datetime else None,
                    'priority': reminder.priority,
                    'type': reminder.reminder_type,
                    'platform': reminder.source_platform
                }
            )
            
            return reminder
    
    async def get_user_reminders(self, user_id: str, include_completed: bool = False, limit: int = 50) -> List[Reminder]:
        """Get user's reminders"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT * FROM reminders 
                WHERE user_id = $1
            """
            params = [user_id]
            
            if not include_completed:
                query += " AND is_completed = FALSE"
            
            query += " ORDER BY due_datetime ASC NULLS LAST, priority DESC, created_at DESC"
            
            if limit:
                query += f" LIMIT ${len(params) + 1}"
                params.append(limit)
            
            rows = await conn.fetch(query, *params)
            return [self._row_to_reminder(row) for row in rows]
    
    async def get_due_reminders(self, user_id: str, hours_ahead: int = 24) -> List[Reminder]:
        """Get reminders due within specified hours"""
        async with self.pool.acquire() as conn:
            cutoff_time = datetime.now() + timedelta(hours=hours_ahead)
            
            rows = await conn.fetch("""
                SELECT * FROM reminders 
                WHERE user_id = $1 
                AND is_completed = FALSE
                AND due_datetime IS NOT NULL
                AND due_datetime <= $2
                AND (snooze_until IS NULL OR snooze_until <= NOW())
                ORDER BY due_datetime ASC, priority DESC
            """, user_id, cutoff_time)
            
            return [self._row_to_reminder(row) for row in rows]
    
    async def get_overdue_reminders(self, user_id: str) -> List[Reminder]:
        """Get overdue reminders"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM reminders 
                WHERE user_id = $1 
                AND is_completed = FALSE
                AND due_datetime IS NOT NULL
                AND due_datetime < NOW()
                AND (snooze_until IS NULL OR snooze_until <= NOW())
                ORDER BY due_datetime ASC
            """, user_id)
            
            return [self._row_to_reminder(row) for row in rows]
    
    async def mark_reminder_complete(self, reminder_id: int, user_id: str) -> bool:
        """Mark reminder as completed"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE reminders 
                SET is_completed = TRUE, completed_at = NOW(), updated_at = NOW()
                WHERE id = $1 AND user_id = $2 AND is_completed = FALSE
            """, reminder_id, user_id)
            
            success = result != "UPDATE 0"
            
            if success:
                await self._log_user_activity(
                    user_id,
                    'reminder_completed',
                    {'reminder_id': reminder_id}
                )
            
            return success
    
    async def search_reminders(self, user_id: str, query: str, limit: int = 20) -> List[Reminder]:
        """Search reminders by title, description, or tags"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM reminders 
                WHERE user_id = $1 
                AND (
                    title ILIKE $2 OR 
                    description ILIKE $2 OR 
                    tags ILIKE $2
                )
                ORDER BY 
                    CASE WHEN is_completed THEN 1 ELSE 0 END,
                    due_datetime ASC NULLS LAST,
                    created_at DESC
                LIMIT $3
            """, user_id, f"%{query}%", limit)
            
            return [self._row_to_reminder(row) for row in rows]
    
    async def get_reminder_summary(self, user_id: str, days: int = 30) -> ReminderSummary:
        """Get reminder summary for user"""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Total counts
            total_row = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE is_completed) as completed,
                    COUNT(*) FILTER (WHERE NOT is_completed) as pending,
                    COUNT(*) FILTER (WHERE NOT is_completed AND due_datetime < NOW()) as overdue,
                    COUNT(*) FILTER (WHERE NOT is_completed AND due_datetime::date = CURRENT_DATE) as due_today,
                    COUNT(*) FILTER (WHERE NOT is_completed AND due_datetime::date = CURRENT_DATE + 1) as due_tomorrow
                FROM reminders 
                WHERE user_id = $1 AND created_at >= $2
            """, user_id, cutoff_date)
            
            # Priority breakdown
            priority_rows = await conn.fetch("""
                SELECT priority, COUNT(*) as count
                FROM reminders 
                WHERE user_id = $1 AND created_at >= $2 AND NOT is_completed
                GROUP BY priority
            """, user_id, cutoff_date)
            
            by_priority = {row['priority']: row['count'] for row in priority_rows}
            
            # Type breakdown
            type_rows = await conn.fetch("""
                SELECT reminder_type, COUNT(*) as count
                FROM reminders 
                WHERE user_id = $1 AND created_at >= $2 AND NOT is_completed
                GROUP BY reminder_type
            """, user_id, cutoff_date)
            
            by_type = {row['reminder_type']: row['count'] for row in type_rows}
            
            return ReminderSummary(
                total_count=total_row['total'],
                completed_count=total_row['completed'],
                pending_count=total_row['pending'],
                overdue_count=total_row['overdue'],
                due_today_count=total_row['due_today'],
                due_tomorrow_count=total_row['due_tomorrow'],
                by_priority=by_priority,
                by_type=by_type,
                period_days=days
            )
    
    async def mark_notification_sent(self, reminder_id: int) -> bool:
        """Mark notification as sent for a reminder"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE reminders 
                SET notification_sent = TRUE, updated_at = NOW()
                WHERE id = $1
            """, reminder_id)
            
            return result != "UPDATE 0"

    # ============================================================================
    # ACTIVITY TRACKING
    # ============================================================================
    
    async def _log_user_activity(self, user_id: str, activity_type: str, activity_data: Dict[str, Any] = None, platform_type: str = None):
        """Log user activity"""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute("""
                    INSERT INTO user_activity (user_id, activity_type, platform_type, activity_data)
                    VALUES ($1, $2, $3, $4)
                """, user_id, activity_type, platform_type, json.dumps(activity_data) if activity_data else None)
                
            except Exception as e:
                print(f"❌ ACTIVITY LOG ERROR: {e}")

    async def get_user_activity_summary(self, user_id: str, days: int = 30) -> UserActivity:
        """Get user activity summary"""
        async with self.pool.acquire() as conn:
            # Get activity counts
            activity_row = await conn.fetchrow("""
                SELECT COUNT(*) as total_interactions
                FROM user_activity 
                WHERE user_id = $1 
                AND created_at >= $2
            """, user_id, datetime.now() - timedelta(days=days))
            
            # Get active platforms
            platform_rows = await conn.fetch("""
                SELECT DISTINCT platform_type FROM user_platforms 
                WHERE user_id = $1 AND is_active = TRUE
            """, user_id)
            
            active_platforms = [row['platform_type'] for row in platform_rows]
            
            # Get last activity dates
            last_expense = await conn.fetchval("""
                SELECT MAX(created_at) FROM expenses WHERE user_id = $1
            """, user_id)
            
            last_reminder = await conn.fetchval("""
                SELECT MAX(created_at) FROM reminders WHERE user_id = $1
            """, user_id)
            
            # Get summaries
            expense_summary = await self.get_expense_summary(user_id, days)
            reminder_summary = await self.get_reminder_summary(user_id, days)
            
            return UserActivity(
                user_id=user_id,
                expense_summary=expense_summary,
                reminder_summary=reminder_summary,
                last_expense_date=last_expense,
                last_reminder_date=last_reminder,
                total_interactions=activity_row['total_interactions'],
                active_platforms=active_platforms
            )

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    

    
    def _row_to_user(self, row) -> User:
        """Convert database row to User object"""
        return User(
            id=row['id'],
            email=row['email'],
            phone_number=row['phone_number'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            country_code=row['country_code'],
            timezone=row['timezone'],
            language=row['language'],
            subscription_status=row['subscription_status'],
            subscription_expires_at=row['subscription_expires_at'],
            is_active=row['is_active'],
            email_verified=row['email_verified'],
            phone_verified=row['phone_verified'],
            notification_preferences=json.loads(row['notification_preferences'] or '{}'),
            expense_categories_custom=json.loads(row['expense_categories_custom'] or '[]'),
            default_currency=row['default_currency'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            last_login_at=row['last_login_at']
        )
    
    def _row_to_platform(self, row) -> UserPlatform:
        """Convert database row to UserPlatform object"""
        return UserPlatform(
            id=row['id'],
            user_id=row['user_id'],
            platform_type=row['platform_type'],
            platform_user_id=row['platform_user_id'],
            platform_username=row['platform_username'],
            is_active=row['is_active'],
            is_primary=row['is_primary'],
            notification_enabled=row['notification_enabled'],
            notification_settings=json.loads(row['notification_settings'] or '{}'),
            device_info=json.loads(row['device_info'] or '{}'),
            last_activity_at=row['last_activity_at'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def _row_to_expense(self, row) -> Expense:
        """Convert database row to Expense object"""
        return Expense(
            id=row['id'],
            user_id=row['user_id'],
            amount=row['amount'],
            description=row['description'],
            category=row['category'],
            original_message=row['original_message'],
            source_platform=row['source_platform'],
            merchant=row['merchant'],
            date=row['date'],
            receipt_image_url=row['receipt_image_url'],
            location=json.loads(row['location']) if row['location'] else None,
            is_recurring=row['is_recurring'],
            recurring_pattern=row['recurring_pattern'],
            tags=json.loads(row['tags']) if row['tags'] else [],
            confidence_score=row['confidence_score'],
            created_at=row['created_at']
        )
    
    def _row_to_reminder(self, row) -> Reminder:
        """Convert database row to Reminder object"""
        return Reminder(
            id=row['id'],
            user_id=row['user_id'],
            title=row['title'],
            description=row['description'],
            source_platform=row['source_platform'],
            due_datetime=row['due_datetime'],
            reminder_type=row['reminder_type'],
            priority=row['priority'],
            is_completed=row['is_completed'],
            is_recurring=row['is_recurring'],
            recurrence_pattern=row['recurrence_pattern'],
            notification_sent=row['notification_sent'],
            snooze_until=row['snooze_until'],
            tags=row['tags'],
            location_reminder=json.loads(row['location_reminder']) if row['location_reminder'] else None,
            attachments=json.loads(row['attachments']) if row['attachments'] else [],
            assigned_to_platforms=json.loads(row['assigned_to_platforms']) if row['assigned_to_platforms'] else [],
            created_at=row['created_at'],
            completed_at=row['completed_at'],
            updated_at=row['updated_at']
        )