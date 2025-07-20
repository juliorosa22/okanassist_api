# core/database.py
import asyncpg
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    User, Expense, ExpenseSummary, Reminder, ReminderSummary, 
    UserActivity, ReminderType, Priority,
    create_reminder_from_dict, create_expense_from_dict
)

class Database:
    """Database manager for expenses, reminders, and users"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
    
    async def connect(self):
        """Initialize database connection"""
        self.pool = await asyncpg.create_pool(self.database_url)
        await self._create_tables()
        print("✅ Database connected")
    
    async def close(self):
        """Close database connection"""
        if self.pool:
            await self.pool.close()
            print("✅ Database disconnected")
    
    async def _create_tables(self):
        """Create necessary tables"""
        async with self.pool.acquire() as conn:
            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id TEXT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
            
            # Expenses table (existing - enhanced with indexes)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id SERIAL PRIMARY KEY,
                    user_telegram_id TEXT REFERENCES users(telegram_id) ON DELETE CASCADE,
                    amount DECIMAL(10,2) NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    original_message TEXT NOT NULL,
                    merchant TEXT,
                    date TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_expenses_user 
                ON expenses(user_telegram_id);
                
                CREATE INDEX IF NOT EXISTS idx_expenses_date 
                ON expenses(date);
                
                CREATE INDEX IF NOT EXISTS idx_expenses_category 
                ON expenses(category);
                
                CREATE INDEX IF NOT EXISTS idx_expenses_amount 
                ON expenses(amount);
            """)
            
            # Reminders table (new)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id SERIAL PRIMARY KEY,
                    user_telegram_id TEXT REFERENCES users(telegram_id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    due_datetime TIMESTAMP,
                    reminder_type TEXT DEFAULT 'general' CHECK (reminder_type IN ('task', 'event', 'deadline', 'habit', 'general')),
                    priority TEXT DEFAULT 'medium' CHECK (priority IN ('urgent', 'high', 'medium', 'low')),
                    is_completed BOOLEAN DEFAULT FALSE,
                    is_recurring BOOLEAN DEFAULT FALSE,
                    recurrence_pattern TEXT,
                    notification_sent BOOLEAN DEFAULT FALSE,
                    snooze_until TIMESTAMP,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    completed_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                -- Indexes for reminders
                CREATE INDEX IF NOT EXISTS idx_reminders_user 
                ON reminders(user_telegram_id);
                
                CREATE INDEX IF NOT EXISTS idx_reminders_due 
                ON reminders(due_datetime);
                
                CREATE INDEX IF NOT EXISTS idx_reminders_completed 
                ON reminders(is_completed);
                
                CREATE INDEX IF NOT EXISTS idx_reminders_priority 
                ON reminders(priority);
                
                CREATE INDEX IF NOT EXISTS idx_reminders_type 
                ON reminders(reminder_type);
                
                CREATE INDEX IF NOT EXISTS idx_reminders_notification 
                ON reminders(notification_sent, due_datetime);
            """)
            
            # Future: embeddings table for RAG (enhanced)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id SERIAL PRIMARY KEY,
                    user_telegram_id TEXT REFERENCES users(telegram_id) ON DELETE CASCADE,
                    content_type TEXT NOT NULL CHECK (content_type IN ('expense', 'reminder', 'conversation')),
                    content_id INTEGER,
                    embedding_text TEXT NOT NULL,
                    -- embedding VECTOR(1536),  -- Will add vector extension later for RAG
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_embeddings_user_type 
                ON embeddings(user_telegram_id, content_type);
                
                CREATE INDEX IF NOT EXISTS idx_embeddings_content 
                ON embeddings(content_type, content_id);
            """)

            # User activity tracking table (new)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id SERIAL PRIMARY KEY,
                    user_telegram_id TEXT REFERENCES users(telegram_id) ON DELETE CASCADE,
                    activity_type TEXT NOT NULL CHECK (activity_type IN ('expense_added', 'reminder_added', 'reminder_completed', 'summary_requested', 'query')),
                    activity_data JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_activity_user_type 
                ON user_activity(user_telegram_id, activity_type);
                
                CREATE INDEX IF NOT EXISTS idx_activity_date 
                ON user_activity(created_at);
            """)

    # ============================================================================
    # USER OPERATIONS
    # ============================================================================
    
    async def create_user(self, user: User) -> User:
        """Create or update user"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (telegram_id, username, first_name, last_name, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    updated_at = NOW()
            """, user.telegram_id, user.username, user.first_name, user.last_name)
            
            return user
    
    async def get_user(self, telegram_id: str) -> Optional[User]:
        """Get user by telegram ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1", 
                telegram_id
            )
            
            if row:
                return User(
                    telegram_id=row['telegram_id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    created_at=row['created_at']
                )
            return None
    
    async def get_all_users(self) -> List[User]:
        """Get all users"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM users ORDER BY created_at DESC")
            
            users = []
            for row in rows:
                users.append(User(
                    telegram_id=row['telegram_id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    created_at=row['created_at']
                ))
            
            return users

    # ============================================================================
    # EXPENSE OPERATIONS (existing, enhanced)
    # ============================================================================
    
    async def save_expense(self, expense: Expense) -> Expense:
        """Save expense to database"""
        async with self.pool.acquire() as conn:
            # Add debug logging
            print(f"🔍 DEBUG - About to execute query with parameters:")
            print(f"  $1 user_telegram_id: {type(expense.user_telegram_id)} = {expense.user_telegram_id}")
            print(f"  $2 amount: {type(expense.amount)} = {expense.amount}")
            print(f"  $3 description: {type(expense.description)} = {expense.description}")
            print(f"  $4 category: {type(expense.category)} = {expense.category}")
            print(f"  $5 original_message: {type(expense.original_message)} = {expense.original_message}")
            print(f"  $6 merchant: {type(expense.merchant)} = {expense.merchant}")
            print(f"  $7 date: {type(expense.date)} = {expense.date}")
            
            try:
                expense_id = await conn.fetchval("""
                    INSERT INTO expenses (
                        user_telegram_id, amount, description, category, 
                        original_message, merchant, date
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                """, 
                    expense.user_telegram_id,
                    expense.amount,
                    expense.description,
                    expense.category,
                    expense.original_message,
                    expense.merchant,
                    expense.date or datetime.now()
                )
                
                expense.id = expense_id
                
                # Log activity
                await self._log_user_activity(
                    expense.user_telegram_id, 
                    'expense_added', 
                    {'expense_id': expense_id, 'amount': float(expense.amount), 'category': expense.category}
                )
                
                return expense
                
            except Exception as e:
                print(f"❌ DATABASE ERROR: {e}")
                print(f"🔍 Full exception: {type(e)} - {str(e)}")
                raise  # Re-raise the exception
    
    async def get_user_expenses(self, telegram_id: str, days: int = 30) -> List[Expense]:
        """Get user's recent expenses"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM expenses 
                WHERE user_telegram_id = $1 
                AND date >= $2
                ORDER BY date DESC
            """, telegram_id, datetime.now() - timedelta(days=days))
            
            expenses = []
            for row in rows:
                expenses.append(Expense(
                    id=row['id'],
                    user_telegram_id=row['user_telegram_id'],
                    amount=row['amount'],
                    description=row['description'],
                    category=row['category'],
                    original_message=row['original_message'],
                    merchant=row['merchant'],
                    date=row['date'],
                    created_at=row['created_at']
                ))
            
            return expenses
    
    async def get_expense_summary(self, telegram_id: str, days: int = 30) -> ExpenseSummary:
        """Get expense summary for user"""
        async with self.pool.acquire() as conn:
            # Total summary
            total_row = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total,
                    COALESCE(AVG(amount), 0) as average
                FROM expenses 
                WHERE user_telegram_id = $1 
                AND date >= $2
            """, telegram_id, datetime.now() - timedelta(days=days))
            
            # Category breakdown
            category_rows = await conn.fetch("""
                SELECT 
                    category,
                    COUNT(*) as count,
                    SUM(amount) as total
                FROM expenses 
                WHERE user_telegram_id = $1 
                AND date >= $2
                GROUP BY category
                ORDER BY total DESC
            """, telegram_id, datetime.now() - timedelta(days=days))
            
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
    # REMINDER OPERATIONS (new)
    # ============================================================================
    
    async def save_reminder(self, reminder: Reminder) -> Reminder:
        """Save reminder to database"""
        async with self.pool.acquire() as conn:
            reminder_id = await conn.fetchval("""
                INSERT INTO reminders (
                    user_telegram_id, title, description, due_datetime,
                    reminder_type, priority, is_completed, is_recurring,
                    recurrence_pattern, notification_sent, snooze_until, tags,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
            """, 
                reminder.user_telegram_id,
                reminder.title,
                reminder.description,
                reminder.due_datetime,
                reminder.reminder_type,
                reminder.priority,
                reminder.is_completed,
                reminder.is_recurring,
                reminder.recurrence_pattern,
                reminder.notification_sent,
                reminder.snooze_until,
                reminder.tags
            )
            
            reminder.id = reminder_id
            
            # Log activity
            await self._log_user_activity(
                reminder.user_telegram_id,
                'reminder_added',
                {
                    'reminder_id': reminder_id,
                    'title': reminder.title,
                    'due_datetime': reminder.due_datetime.isoformat() if reminder.due_datetime else None,
                    'priority': reminder.priority,
                    'type': reminder.reminder_type
                }
            )
            
            return reminder
    
    async def get_user_reminders(self, telegram_id: str, include_completed: bool = False, limit: int = 50) -> List[Reminder]:
        """Get user's reminders"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT * FROM reminders 
                WHERE user_telegram_id = $1
            """
            params = [telegram_id]
            
            if not include_completed:
                query += " AND is_completed = FALSE"
            
            query += " ORDER BY due_datetime ASC NULLS LAST, priority DESC, created_at DESC"
            
            if limit:
                query += f" LIMIT ${len(params) + 1}"
                params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            reminders = []
            for row in rows:
                reminders.append(Reminder(
                    id=row['id'],
                    user_telegram_id=row['user_telegram_id'],
                    title=row['title'],
                    description=row['description'],
                    due_datetime=row['due_datetime'],
                    reminder_type=row['reminder_type'],
                    priority=row['priority'],
                    is_completed=row['is_completed'],
                    is_recurring=row['is_recurring'],
                    recurrence_pattern=row['recurrence_pattern'],
                    notification_sent=row['notification_sent'],
                    snooze_until=row['snooze_until'],
                    tags=row['tags'],
                    created_at=row['created_at'],
                    completed_at=row['completed_at'],
                    updated_at=row['updated_at']
                ))
            
            return reminders
    
    async def get_due_reminders(self, telegram_id: str, hours_ahead: int = 24) -> List[Reminder]:
        """Get reminders due within specified hours"""
        async with self.pool.acquire() as conn:
            cutoff_time = datetime.now() + timedelta(hours=hours_ahead)
            
            rows = await conn.fetch("""
                SELECT * FROM reminders 
                WHERE user_telegram_id = $1 
                AND is_completed = FALSE
                AND due_datetime IS NOT NULL
                AND due_datetime <= $2
                AND (snooze_until IS NULL OR snooze_until <= NOW())
                ORDER BY due_datetime ASC, priority DESC
            """, telegram_id, cutoff_time)
            
            reminders = []
            for row in rows:
                reminders.append(Reminder(
                    id=row['id'],
                    user_telegram_id=row['user_telegram_id'],
                    title=row['title'],
                    description=row['description'],
                    due_datetime=row['due_datetime'],
                    reminder_type=row['reminder_type'],
                    priority=row['priority'],
                    is_completed=row['is_completed'],
                    is_recurring=row['is_recurring'],
                    recurrence_pattern=row['recurrence_pattern'],
                    notification_sent=row['notification_sent'],
                    snooze_until=row['snooze_until'],
                    tags=row['tags'],
                    created_at=row['created_at'],
                    completed_at=row['completed_at'],
                    updated_at=row['updated_at']
                ))
            
            return reminders
    
    async def get_overdue_reminders(self, telegram_id: str) -> List[Reminder]:
        """Get overdue reminders"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM reminders 
                WHERE user_telegram_id = $1 
                AND is_completed = FALSE
                AND due_datetime IS NOT NULL
                AND due_datetime < NOW()
                AND (snooze_until IS NULL OR snooze_until <= NOW())
                ORDER BY due_datetime ASC
            """, telegram_id)
            
            return [self._row_to_reminder(row) for row in rows]
    
    async def mark_reminder_complete(self, reminder_id: int, telegram_id: str) -> bool:
        """Mark reminder as completed"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE reminders 
                SET is_completed = TRUE, completed_at = NOW(), updated_at = NOW()
                WHERE id = $1 AND user_telegram_id = $2 AND is_completed = FALSE
            """, reminder_id, telegram_id)
            
            success = result != "UPDATE 0"
            
            if success:
                # Log activity
                await self._log_user_activity(
                    telegram_id,
                    'reminder_completed',
                    {'reminder_id': reminder_id}
                )
            
            return success
    
    async def snooze_reminder(self, reminder_id: int, telegram_id: str, snooze_until: datetime) -> bool:
        """Snooze a reminder until specified time"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE reminders 
                SET snooze_until = $3, updated_at = NOW()
                WHERE id = $1 AND user_telegram_id = $2 AND is_completed = FALSE
            """, reminder_id, telegram_id, snooze_until)
            
            return result != "UPDATE 0"
    
    async def update_reminder(self, reminder_id: int, telegram_id: str, **kwargs) -> Optional[Reminder]:
        """Update reminder fields"""
        async with self.pool.acquire() as conn:
            # Build dynamic update query
            update_fields = []
            params = []
            param_count = 1
            
            allowed_fields = [
                'title', 'description', 'due_datetime', 'reminder_type', 
                'priority', 'is_recurring', 'recurrence_pattern', 'tags'
            ]
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    update_fields.append(f"{field} = ${param_count}")
                    params.append(value)
                    param_count += 1
            
            if not update_fields:
                return None
            
            # Always update updated_at
            update_fields.append(f"updated_at = ${param_count}")
            params.append(datetime.now())
            param_count += 1
            
            params.extend([reminder_id, telegram_id])
            
            query = f"""
                UPDATE reminders 
                SET {', '.join(update_fields)}
                WHERE id = ${param_count - 1} AND user_telegram_id = ${param_count}
                RETURNING *
            """
            
            row = await conn.fetchrow(query, *params)
            
            if row:
                return self._row_to_reminder(row)
            return None
    
    async def delete_reminder(self, reminder_id: int, telegram_id: str) -> bool:
        """Delete a reminder"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM reminders 
                WHERE id = $1 AND user_telegram_id = $2
            """, reminder_id, telegram_id)
            
            return result != "DELETE 0"
    
    async def get_reminder_summary(self, telegram_id: str, days: int = 30) -> ReminderSummary:
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
                WHERE user_telegram_id = $1 AND created_at >= $2
            """, telegram_id, cutoff_date)
            
            # Priority breakdown
            priority_rows = await conn.fetch("""
                SELECT priority, COUNT(*) as count
                FROM reminders 
                WHERE user_telegram_id = $1 AND created_at >= $2 AND NOT is_completed
                GROUP BY priority
            """, telegram_id, cutoff_date)
            
            by_priority = {row['priority']: row['count'] for row in priority_rows}
            
            # Type breakdown
            type_rows = await conn.fetch("""
                SELECT reminder_type, COUNT(*) as count
                FROM reminders 
                WHERE user_telegram_id = $1 AND created_at >= $2 AND NOT is_completed
                GROUP BY reminder_type
            """, telegram_id, cutoff_date)
            
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
    
    async def search_reminders(self, telegram_id: str, query: str, limit: int = 20) -> List[Reminder]:
        """Search reminders by title, description, or tags"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM reminders 
                WHERE user_telegram_id = $1 
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
            """, telegram_id, f"%{query}%", limit)
            
            return [self._row_to_reminder(row) for row in rows]

    # ============================================================================
    # NOTIFICATION OPERATIONS
    # ============================================================================
    
    async def get_reminders_for_notification(self, minutes_ahead: int = 15) -> List[Reminder]:
        """Get reminders that need notifications"""
        async with self.pool.acquire() as conn:
            notification_time = datetime.now() + timedelta(minutes=minutes_ahead)
            
            rows = await conn.fetch("""
                SELECT * FROM reminders 
                WHERE is_completed = FALSE
                AND notification_sent = FALSE
                AND due_datetime IS NOT NULL
                AND due_datetime <= $1
                AND (snooze_until IS NULL OR snooze_until <= NOW())
                ORDER BY due_datetime ASC
            """, notification_time)
            
            return [self._row_to_reminder(row) for row in rows]
    
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
    
    async def _log_user_activity(self, telegram_id: str, activity_type: str, activity_data: Dict[str, Any] = None):
        """Log user activity"""
        async with self.pool.acquire() as conn:
            try:
                import json
                
                # Convert dict to JSON string for JSONB field
                activity_json = json.dumps(activity_data) if activity_data else None
                
                await conn.execute("""
                    INSERT INTO user_activity (user_telegram_id, activity_type, activity_data)
                    VALUES ($1, $2, $3)
                """, telegram_id, activity_type, activity_json)
                
            except Exception as e:
                print(f"❌ ACTIVITY LOG ERROR: {e}")
                # Don't let activity logging failure break the main operation
                pass    

    async def get_user_activity_summary(self, telegram_id: str, days: int = 30) -> UserActivity:
        """Get user activity summary"""
        async with self.pool.acquire() as conn:
            # Get activity counts
            activity_row = await conn.fetchrow("""
                SELECT COUNT(*) as total_interactions
                FROM user_activity 
                WHERE user_telegram_id = $1 
                AND created_at >= $2
            """, telegram_id, datetime.now() - timedelta(days=days))
            
            # Get last activity dates
            last_expense = await conn.fetchval("""
                SELECT MAX(created_at) FROM expenses WHERE user_telegram_id = $1
            """, telegram_id)
            
            last_reminder = await conn.fetchval("""
                SELECT MAX(created_at) FROM reminders WHERE user_telegram_id = $1
            """, telegram_id)
            
            # Get summaries
            expense_summary = await self.get_expense_summary(telegram_id, days)
            reminder_summary = await self.get_reminder_summary(telegram_id, days)
            
            return UserActivity(
                user_telegram_id=telegram_id,
                expense_summary=expense_summary,
                reminder_summary=reminder_summary,
                last_expense_date=last_expense,
                last_reminder_date=last_reminder,
                total_interactions=activity_row['total_interactions']
            )

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _row_to_reminder(self, row) -> Reminder:
        """Convert database row to Reminder object"""
        return Reminder(
            id=row['id'],
            user_telegram_id=row['user_telegram_id'],
            title=row['title'],
            description=row['description'],
            due_datetime=row['due_datetime'],
            reminder_type=row['reminder_type'],
            priority=row['priority'],
            is_completed=row['is_completed'],
            is_recurring=row['is_recurring'],
            recurrence_pattern=row['recurrence_pattern'],
            notification_sent=row['notification_sent'],
            snooze_until=row['snooze_until'],
            tags=row['tags'],
            created_at=row['created_at'],
            completed_at=row['completed_at'],
            updated_at=row['updated_at']
        )
    
    async def get_recent_user_context(self, telegram_id: str, limit: int = 10) -> List[dict]:
        """Get recent expenses and reminders for context (for future RAG)"""
        async with self.pool.acquire() as conn:
            # Get recent expenses
            expense_rows = await conn.fetch("""
                SELECT 'expense' as type, original_message, description, category, amount::text, created_at
                FROM expenses 
                WHERE user_telegram_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2
            """, telegram_id, limit // 2)
            
            # Get recent reminders
            reminder_rows = await conn.fetch("""
                SELECT 'reminder' as type, title as original_message, description, 
                       reminder_type as category, priority as amount, created_at
                FROM reminders 
                WHERE user_telegram_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2
            """, telegram_id, limit // 2)
            
            # Combine and sort by date
            all_context = []
            for row in expense_rows:
                all_context.append(dict(row))
            for row in reminder_rows:
                all_context.append(dict(row))
            
            # Sort by created_at descending
            all_context.sort(key=lambda x: x['created_at'], reverse=True)
            
            return all_context[:limit]