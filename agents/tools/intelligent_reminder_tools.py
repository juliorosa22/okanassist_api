# agents/tools/intelligent_reminder_tools.py
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from langchain_core.tools import tool

from core.database import Database
from core.models import User, UserPlatform, Reminder, ReminderType, Priority

# Global database instance
db: Optional[Database] = None

def set_database(database: Database):
    """Set the global database instance"""
    global db
    db = database

@tool
async def save_intelligent_reminder(user_id: str, title: str, description: str,
                                  source_platform: str, due_datetime: datetime = None,
                                  reminder_type: str = "general", priority: str = "medium",
                                  confidence_score: float = 0.8) -> Dict[str, Any]:
    """
    Save an intelligently parsed reminder to the database
    
    Args:
        user_id: User ID from the database
        title: Reminder title
        description: Reminder description
        source_platform: Platform where reminder was created
        due_datetime: When the reminder is due
        reminder_type: Type of reminder (task, event, deadline, habit, general)
        priority: Priority level (urgent, high, medium, low)
        confidence_score: LLM parsing confidence
        
    Returns:
        Success status and reminder details
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        # Validate reminder type and priority
        valid_types = [t.value for t in ReminderType]
        valid_priorities = [p.value for p in Priority]
        
        if reminder_type not in valid_types:
            reminder_type = ReminderType.GENERAL.value
        
        if priority not in valid_priorities:
            priority = Priority.MEDIUM.value
        
        # Create reminder object
        reminder = Reminder(
            user_id=user_id,
            title=title,
            description=description,
            source_platform=source_platform,
            due_datetime=due_datetime,
            reminder_type=reminder_type,
            priority=priority,
            is_completed=False,
            created_at=datetime.now()
        )
        
        print(f"💾 SAVING INTELLIGENT REMINDER: {title} - {due_datetime} - {priority} (confidence: {confidence_score})")
        
        # Save to database
        saved_reminder = await db.save_reminder(reminder)
        
        return {
            "success": True,
            "reminder_id": saved_reminder.id,
            "title": saved_reminder.title,
            "description": saved_reminder.description,
            "due_datetime": saved_reminder.due_datetime.isoformat() if saved_reminder.due_datetime else None,
            "reminder_type": saved_reminder.reminder_type,
            "priority": saved_reminder.priority,
            "user_id": saved_reminder.user_id
        }
    
    except Exception as e:
        print(f"❌ SAVE INTELLIGENT REMINDER ERROR: {e}")
        return {"success": False, "error": str(e)}

@tool
async def get_user_reminder_context(user_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Get user reminder context for intelligent processing
    
    Args:
        user_id: User ID
        days: Number of days to look back
        
    Returns:
        User reminder patterns and context
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        # Get recent reminders
        reminders = await db.get_user_reminders(user_id, include_completed=True, limit=50)
        
        # Extract patterns
        patterns = {
            "common_types": {},
            "common_priorities": {},
            "typical_times": {},
            "frequent_keywords": {},
            "completion_rate": 0
        }
        
        completed_count = 0
        total_count = len(reminders)
        
        for reminder in reminders:
            # Type frequency
            r_type = reminder.reminder_type
            patterns["common_types"][r_type] = patterns["common_types"].get(r_type, 0) + 1
            
            # Priority frequency
            priority = reminder.priority
            patterns["common_priorities"][priority] = patterns["common_priorities"].get(priority, 0) + 1
            
            # Completion tracking
            if reminder.is_completed:
                completed_count += 1
            
            # Time patterns
            if reminder.due_datetime:
                hour = reminder.due_datetime.hour
                patterns["typical_times"][hour] = patterns["typical_times"].get(hour, 0) + 1
            
            # Extract keywords from titles and descriptions
            text = f"{reminder.title} {reminder.description}".lower()
            words = text.split()
            for word in words:
                if len(word) > 3:  # Skip short words
                    patterns["frequent_keywords"][word] = patterns["frequent_keywords"].get(word, 0) + 1
        
        # Calculate completion rate
        if total_count > 0:
            patterns["completion_rate"] = completed_count / total_count
        
        return {
            "success": True,
            "patterns": patterns,
            "total_reminders": total_count,
            "period_days": days
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def get_intelligent_reminder_summary(user_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Get reminder summary with enhanced data for intelligent responses
    
    Args:
        user_id: User ID
        days: Number of days to look back
        
    Returns:
        Enhanced reminder summary
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        summary = await db.get_reminder_summary(user_id, days)
        
        # Get due reminders for additional context
        due_soon = await db.get_due_reminders(user_id, hours_ahead=24)
        overdue = await db.get_overdue_reminders(user_id)
        
        # Get recent completed reminders for motivation
        recent_reminders = await db.get_user_reminders(user_id, include_completed=True, limit=10)
        recently_completed = [r for r in recent_reminders if r.is_completed and r.completed_at]
        
        return {
            "success": True,
            "total_count": summary.total_count,
            "completed_count": summary.completed_count,
            "pending_count": summary.pending_count,
            "overdue_count": summary.overdue_count,
            "due_today_count": summary.due_today_count,
            "due_tomorrow_count": summary.due_tomorrow_count,
            "completion_rate": summary.get_completion_rate(),
            "by_priority": summary.by_priority,
            "by_type": summary.by_type,
            "period_days": days,
            "due_soon": len(due_soon),
            "recently_completed": len(recently_completed),
            "has_urgent": summary.has_urgent_items()
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def get_due_reminders_details(user_id: str, hours_ahead: int = 24) -> Dict[str, Any]:
    """
    Get detailed information about due reminders
    
    Args:
        user_id: User ID
        hours_ahead: Hours to look ahead
        
    Returns:
        Detailed due reminders information
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        due_reminders = await db.get_due_reminders(user_id, hours_ahead)
        
        reminder_details = []
        for reminder in due_reminders:
            reminder_details.append({
                "id": reminder.id,
                "title": reminder.title,
                "description": reminder.description,
                "due_datetime": reminder.due_datetime.isoformat() if reminder.due_datetime else None,
                "priority": reminder.priority,
                "reminder_type": reminder.reminder_type,
                "is_overdue": reminder.is_overdue(),
                "formatted_summary": reminder.get_formatted_summary()
            })
        
        return {
            "success": True,
            "reminders": reminder_details,
            "count": len(reminder_details),
            "hours_ahead": hours_ahead
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def mark_reminder_completed(user_id: str, reminder_id: int) -> Dict[str, Any]:
    """
    Mark a reminder as completed
    
    Args:
        user_id: User ID for security
        reminder_id: ID of the reminder to complete
        
    Returns:
        Success status
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        success = await db.mark_reminder_complete(reminder_id, user_id)
        
        if success:
            return {
                "success": True,
                "message": "Reminder marked as completed",
                "reminder_id": reminder_id
            }
        else:
            return {
                "success": False,
                "error": "Reminder not found or already completed"
            }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def search_user_reminders(user_id: str, query: str, limit: int = 10) -> Dict[str, Any]:
    """
    Search user's reminders by text
    
    Args:
        user_id: User ID
        query: Search query
        limit: Maximum results
        
    Returns:
        Matching reminders
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        reminders = await db.search_reminders(user_id, query, limit)
        
        reminder_results = []
        for reminder in reminders:
            reminder_results.append({
                "id": reminder.id,
                "title": reminder.title,
                "description": reminder.description,
                "due_datetime": reminder.due_datetime.isoformat() if reminder.due_datetime else None,
                "priority": reminder.priority,
                "reminder_type": reminder.reminder_type,
                "is_completed": reminder.is_completed,
                "status": reminder.get_status_text()
            })
        
        return {
            "success": True,
            "reminders": reminder_results,
            "count": len(reminder_results),
            "query": query
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def get_reminder_notifications(user_id: str, minutes_ahead: int = 15) -> Dict[str, Any]:
    """
    Get reminders that need notifications
    
    Args:
        user_id: User ID
        minutes_ahead: Minutes to look ahead for notifications
        
    Returns:
        Reminders needing notifications
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        # Get reminders due within the specified time
        due_reminders = await db.get_due_reminders(user_id, hours_ahead=minutes_ahead/60)
        
        # Filter for those that haven't been notified yet
        notification_reminders = []
        for reminder in due_reminders:
            if not reminder.notification_sent and reminder.due_datetime:
                time_until_due = reminder.due_datetime - datetime.now()
                if time_until_due.total_seconds() <= (minutes_ahead * 60):
                    notification_reminders.append({
                        "id": reminder.id,
                        "title": reminder.title,
                        "description": reminder.description,
                        "due_datetime": reminder.due_datetime.isoformat(),
                        "priority": reminder.priority,
                        "minutes_until_due": int(time_until_due.total_seconds() / 60)
                    })
        
        return {
            "success": True,
            "reminders": notification_reminders,
            "count": len(notification_reminders)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def update_reminder_notification_sent(reminder_id: int) -> Dict[str, Any]:
    """
    Mark reminder notification as sent
    
    Args:
        reminder_id: ID of the reminder
        
    Returns:
        Success status
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        success = await db.mark_notification_sent(reminder_id)
        
        return {
            "success": success,
            "reminder_id": reminder_id
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}