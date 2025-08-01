# core/database.py - Supabase integrated version
import asyncpg
import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    Transaction, TransactionSummary, Reminder, ReminderSummary, 
    UserActivity, ReminderType, Priority, TransactionType
)

class Database:
    """Database manager integrated with Supabase Auth"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
    
    async def connect(self):
        """Initialize database connection"""
        self.pool = await asyncpg.create_pool(self.database_url)
        await self._create_tables()
        print("✅ Database connected with Supabase Auth integration")
    
    async def close(self):
        """Close database connection"""
        if self.pool:
            await self.pool.close()
            print("✅ Database disconnected")
    
    async def _create_tables(self):
        """Create application-specific tables (users handled by Supabase)"""
        async with self.pool.acquire() as conn:
            # Transactions table (expenses + income)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL, -- References Supabase auth.users.id
                    amount DECIMAL(12,2) NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('expense', 'income')),
                    original_message TEXT NOT NULL,
                    source_platform TEXT DEFAULT 'web_app' CHECK (source_platform IN ('telegram', 'whatsapp', 'mobile_app', 'web_app')),
                    merchant TEXT,
                    date TIMESTAMP DEFAULT NOW(),
                    receipt_image_url TEXT,
                    location JSONB,
                    is_recurring BOOLEAN DEFAULT FALSE,
                    recurring_pattern TEXT,
                    tags JSONB DEFAULT '[]',
                    confidence_score DECIMAL(3,2),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
                CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
                CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
                CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);
                CREATE INDEX IF NOT EXISTS idx_transactions_platform ON transactions(source_platform);
                CREATE INDEX IF NOT EXISTS idx_transactions_amount ON transactions(amount);
            """)
            
            # Reminders table (updated to use Supabase user_id)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL, -- References Supabase auth.users.id
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    source_platform TEXT DEFAULT 'web_app' CHECK (source_platform IN ('telegram', 'whatsapp', 'mobile_app', 'web_app')),
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
            
            # User activity table (simplified - no user data stored locally)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL, -- References Supabase auth.users.id
                    activity_type TEXT NOT NULL CHECK (activity_type IN ('transaction_added', 'reminder_added', 'reminder_completed', 'summary_requested', 'query', 'login')),
                    platform_type TEXT,
                    activity_data JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_activity_user ON user_activity(user_id);
                CREATE INDEX IF NOT EXISTS idx_activity_type ON user_activity(activity_type);
                CREATE INDEX IF NOT EXISTS idx_activity_date ON user_activity(created_at);
            """)

    # ============================================================================
    # TRANSACTION OPERATIONS (Expenses + Income)
    # ============================================================================
    
    async def save_transaction(self, transaction: Transaction) -> Transaction:
        """Save transaction (expense or income) to database"""
        async with self.pool.acquire() as conn:
            transaction_id = await conn.fetchval("""
                INSERT INTO transactions (
                    user_id, amount, description, category, transaction_type, original_message, 
                    source_platform, merchant, date, receipt_image_url, location, is_recurring, 
                    recurring_pattern, tags, confidence_score
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id
            """, 
                transaction.user_id, transaction.amount, transaction.description, transaction.category,
                transaction.transaction_type, transaction.original_message, transaction.source_platform, 
                transaction.merchant, transaction.date or datetime.now(), transaction.receipt_image_url,
                json.dumps(transaction.location) if transaction.location else None,
                transaction.is_recurring, transaction.recurring_pattern,
                json.dumps(transaction.tags), transaction.confidence_score
            )
            
            transaction.id = transaction_id
            
            # Log activity
            await self._log_user_activity(
                transaction.user_id, 
                'transaction_added', 
                {
                    'transaction_id': transaction_id, 
                    'amount': float(transaction.amount), 
                    'category': transaction.category,
                    'type': transaction.transaction_type,
                    'platform': transaction.source_platform
                }
            )
            
            return transaction
    
    async def get_user_transactions(self, user_id: str, days: int = 30, transaction_type: str = None) -> List[Transaction]:
        """Get user's recent transactions (expenses and/or income)"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT * FROM transactions 
                WHERE user_id = $1 
                AND date >= $2
            """
            params = [user_id, datetime.now() - timedelta(days=days)]
            
            if transaction_type:
                query += " AND transaction_type = $3"
                params.append(transaction_type)
            
            query += " ORDER BY date DESC"
            
            rows = await conn.fetch(query, *params)
            return [self._row_to_transaction(row) for row in rows]
    
    async def get_transaction_summary(self, user_id: str, days: int = 30) -> TransactionSummary:
        """Get comprehensive transaction summary (expenses + income)"""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Overall summary
            total_row = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_count,
                    COUNT(*) FILTER (WHERE transaction_type = 'expense') as expense_count,
                    COUNT(*) FILTER (WHERE transaction_type = 'income') as income_count,
                    COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'expense'), 0) as total_expenses,
                    COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'income'), 0) as total_income,
                    COALESCE(AVG(amount) FILTER (WHERE transaction_type = 'expense'), 0) as avg_expense,
                    COALESCE(AVG(amount) FILTER (WHERE transaction_type = 'income'), 0) as avg_income
                FROM transactions 
                WHERE user_id = $1 AND date >= $2
            """, user_id, cutoff_date)
            
            # Category breakdown by type
            category_rows = await conn.fetch("""
                SELECT 
                    transaction_type,
                    category,
                    COUNT(*) as count,
                    SUM(amount) as total
                FROM transactions 
                WHERE user_id = $1 AND date >= $2
                GROUP BY transaction_type, category
                ORDER BY transaction_type, total DESC
            """, user_id, cutoff_date)
            
            categories_by_type = {"expense": [], "income": []}
            for row in category_rows:
                categories_by_type[row['transaction_type']].append({
                    'category': row['category'],
                    'count': row['count'],
                    'total': float(row['total'])
                })
            
            net_income = total_row['total_income'] - total_row['total_expenses']
            
            return TransactionSummary(
                total_expenses=total_row['total_expenses'],
                total_income=total_row['total_income'],
                net_income=net_income,
                expense_count=total_row['expense_count'],
                income_count=total_row['income_count'],
                average_expense=total_row['avg_expense'],
                average_income=total_row['avg_income'],
                expense_categories=categories_by_type['expense'],
                income_categories=categories_by_type['income'],
                period_days=days
            )

    # ============================================================================
    # REMINDER OPERATIONS (Updated for Supabase)
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
            
            # Get last activity dates
            last_transaction = await conn.fetchval("""
                SELECT MAX(created_at) FROM transactions WHERE user_id = $1
            """, user_id)
            
            last_reminder = await conn.fetchval("""
                SELECT MAX(created_at) FROM reminders WHERE user_id = $1
            """, user_id)
            
            # Get summaries
            transaction_summary = await self.get_transaction_summary(user_id, days)
            reminder_summary = await self.get_reminder_summary(user_id, days)
            
            return UserActivity(
                user_id=user_id,
                transaction_summary=transaction_summary,
                reminder_summary=reminder_summary,
                last_transaction_date=last_transaction,
                last_reminder_date=last_reminder,
                total_interactions=activity_row['total_interactions']
            )

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _row_to_transaction(self, row) -> Transaction:
        """Convert database row to Transaction object"""
        return Transaction(
            id=row['id'],
            user_id=str(row['user_id']),
            amount=row['amount'],
            description=row['description'],
            category=row['category'],
            transaction_type=row['transaction_type'],
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
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def _row_to_reminder(self, row) -> Reminder:
        """Convert database row to Reminder object"""
        return Reminder(
            id=row['id'],
            user_id=str(row['user_id']),
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