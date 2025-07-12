# agents/tools/reminder_tools.py
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from langchain_core.tools import tool
from dateutil import parser as date_parser
#from dateutil.relativedelta import relativedelta

from core.database import Database
from core.models import Reminder

# Global database instance
db: Optional[Database] = None

def set_database(database: Database):
    """Set the global database instance"""
    global db
    db = database

@tool
async def parse_reminder_from_message(message: str) -> Dict:
    """
    Extract reminder information from user message
    
    Args:
        message: User's reminder message
        
    Returns:
        Dictionary with title, description, due_date, due_time, type, priority
    """
    print(f"🔍 Parsing reminder: {message}")
    
    # Remove reminder trigger words to get clean description
    clean_message = message
    trigger_words = ['remind me to', 'remind me', 'don\'t forget to', 'don\'t forget', 
                    'remember to', 'set reminder for', 'reminder:', 'remind me about']
    
    for trigger in trigger_words:
        clean_message = re.sub(trigger, '', clean_message, flags=re.IGNORECASE).strip()
    
    # Extract time patterns
    time_patterns = [
        r'(\d{1,2}):(\d{2})\s*(am|pm)',  # 3:30pm
        r'(\d{1,2})\s*(am|pm)',          # 3pm
        r'at\s+(\d{1,2}):(\d{2})',       # at 15:30
        r'at\s+(\d{1,2})\s*(am|pm)',     # at 3pm
    ]
    
    due_time = None
    time_match = None
    
    for pattern in time_patterns:
        match = re.search(pattern, clean_message, re.IGNORECASE)
        if match:
            time_match = match
            if len(match.groups()) == 3:  # Hour:Minute AM/PM
                hour = int(match.group(1))
                minute = int(match.group(2))
                period = match.group(3).lower()
                if period == 'pm' and hour != 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
                due_time = f"{hour:02d}:{minute:02d}"
            elif len(match.groups()) == 2:  # Hour AM/PM
                hour = int(match.group(1))
                period = match.group(2).lower()
                if period == 'pm' and hour != 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
                due_time = f"{hour:02d}:00"
            else:  # 24-hour format
                hour = int(match.group(1))
                minute = int(match.group(2)) if len(match.groups()) > 1 else 0
                due_time = f"{hour:02d}:{minute:02d}"
            break
    
    # Extract date patterns
    date_patterns = [
        (r'today', 0),
        (r'tomorrow', 1),
        (r'day after tomorrow', 2),
        (r'next week', 7),
        (r'in (\d+) days?', None),  # Variable days
        (r'in (\d+) hours?', None),  # Variable hours
        (r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', None),
        (r'(\d{1,2})/(\d{1,2})', None),  # MM/DD
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', None),  # YYYY-MM-DD
    ]
    
    due_date = None
    current_date = datetime.now().date()
    
    for pattern, days_offset in date_patterns:
        match = re.search(pattern, clean_message, re.IGNORECASE)
        if match:
            if days_offset is not None:
                due_date = (current_date + timedelta(days=days_offset)).isoformat()
            elif 'days' in pattern:
                days = int(match.group(1))
                due_date = (current_date + timedelta(days=days)).isoformat()
            elif 'hours' in pattern:
                hours = int(match.group(1))
                target_datetime = datetime.now() + timedelta(hours=hours)
                due_date = target_datetime.date().isoformat()
                if not due_time:
                    due_time = target_datetime.strftime("%H:%M")
            elif any(day in pattern for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
                # Find next occurrence of this weekday
                weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                target_weekday = next(i for i, day in enumerate(weekdays) if day in match.group(0).lower())
                days_ahead = target_weekday - current_date.weekday()
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                due_date = (current_date + timedelta(days=days_ahead)).isoformat()
            break
    
    # Clean the description by removing time and date references
    description = clean_message
    if time_match:
        description = re.sub(time_match.group(0), '', description, flags=re.IGNORECASE)
    
    # Remove common date words
    date_words = ['today', 'tomorrow', 'next week', 'monday', 'tuesday', 'wednesday', 
                 'thursday', 'friday', 'saturday', 'sunday', 'at', 'on']
    for word in date_words:
        description = re.sub(rf'\b{word}\b', '', description, flags=re.IGNORECASE)
    
    description = re.sub(r'\s+', ' ', description).strip()
    description = description.strip('.,!?-')
    
    # Extract title (first few words)
    title = description
    if len(description.split()) > 5:
        title = ' '.join(description.split()[:5])
    
    # Determine reminder type
    reminder_type = _determine_reminder_type(description)
    
    # Determine priority
    priority = _determine_priority(message, description)
    
    if not description:
        return {
            "success": False,
            "error": "Could not extract reminder description",
            "message": message
        }
    
    result = {
        "success": True,
        "title": title,
        "description": description,
        "due_date": due_date,
        "due_time": due_time,
        "reminder_type": reminder_type,
        "priority": priority,
        "original_message": message
    }
    
    print(f"✅ Parsed reminder: {result}")
    return result

def _determine_reminder_type(description: str) -> str:
    """Determine reminder type based on description"""
    description_lower = description.lower()
    
    task_keywords = ['call', 'email', 'buy', 'pick up', 'finish', 'complete', 'do', 'send', 'submit']
    event_keywords = ['meeting', 'dinner', 'lunch', 'appointment', 'party', 'concert', 'game']
    deadline_keywords = ['deadline', 'due', 'payment', 'bill', 'submit', 'file']
    
    if any(keyword in description_lower for keyword in deadline_keywords):
        return 'deadline'
    elif any(keyword in description_lower for keyword in event_keywords):
        return 'event'
    elif any(keyword in description_lower for keyword in task_keywords):
        return 'task'
    else:
        return 'general'

def _determine_priority(message: str, description: str) -> str:
    """Determine priority based on message content"""
    message_lower = message.lower()
    
    urgent_keywords = ['urgent', 'asap', 'immediately', 'important', 'critical']
    high_keywords = ['important', 'soon', 'today', 'deadline']
    low_keywords = ['sometime', 'when you can', 'eventually']
    
    if any(keyword in message_lower for keyword in urgent_keywords):
        return 'urgent'
    elif any(keyword in message_lower for keyword in high_keywords):
        return 'high'
    elif any(keyword in message_lower for keyword in low_keywords):
        return 'low'
    else:
        return 'medium'

@tool
async def save_reminder(user_telegram_id: str, title: str, description: str,
                       due_date: str = None, due_time: str = None, 
                       reminder_type: str = "general", priority: str = "medium") -> Dict:
    """
    Save a reminder to the database
    
    Args:
        user_telegram_id: User's Telegram ID
        title: Reminder title
        description: Reminder description
        due_date: Due date (YYYY-MM-DD format)
        due_time: Due time (HH:MM format)
        reminder_type: Type of reminder
        priority: Priority level
        
    Returns:
        Success status and reminder details
    """
    print(f"💾 SAVING REMINDER: {title} - {due_date} {due_time} - {priority}")
    
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        # Parse due datetime
        due_datetime = None
        if due_date:
            if due_time:
                due_datetime = datetime.fromisoformat(f"{due_date} {due_time}")
            else:
                due_datetime = datetime.fromisoformat(f"{due_date} 09:00")  # Default to 9 AM
        
        # Create reminder object
        reminder = Reminder(
            user_telegram_id=user_telegram_id,
            title=title,
            description=description,
            due_datetime=due_datetime,
            reminder_type=reminder_type,
            priority=priority,
            is_completed=False,
            created_at=datetime.now()
        )
        
        # Save to database
        saved_reminder = await db.save_reminder(reminder)
        
        return {
            "success": True,
            "reminder_id": saved_reminder.id,
            "title": saved_reminder.title,
            "description": saved_reminder.description,
            "due_datetime": saved_reminder.due_datetime.isoformat() if saved_reminder.due_datetime else None,
            "reminder_type": saved_reminder.reminder_type,
            "priority": saved_reminder.priority
        }
    
    except Exception as e:
        print(f"❌ SAVE REMINDER ERROR: {e}")
        return {"success": False, "error": str(e)}

@tool
async def get_user_reminders(user_telegram_id: str, include_completed: bool = False, limit: int = 10) -> Dict:
    """
    Get user's reminders
    
    Args:
        user_telegram_id: User's Telegram ID
        include_completed: Whether to include completed reminders
        limit: Maximum number of reminders to return
        
    Returns:
        List of reminders
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        reminders = await db.get_user_reminders(user_telegram_id, include_completed, limit)
        
        reminder_list = []
        for reminder in reminders:
            reminder_list.append({
                "id": reminder.id,
                "title": reminder.title,
                "description": reminder.description,
                "due_datetime": reminder.due_datetime.isoformat() if reminder.due_datetime else None,
                "reminder_type": reminder.reminder_type,
                "priority": reminder.priority,
                "is_completed": reminder.is_completed,
                "created_at": reminder.created_at.isoformat() if reminder.created_at else None
            })
        
        return {
            "success": True,
            "reminders": reminder_list,
            "count": len(reminder_list)
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def get_due_reminders(user_telegram_id: str, hours_ahead: int = 24) -> Dict:
    """
    Get reminders that are due within specified hours
    
    Args:
        user_telegram_id: User's Telegram ID
        hours_ahead: Hours to look ahead for due reminders
        
    Returns:
        List of due reminders
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        due_reminders = await db.get_due_reminders(user_telegram_id, hours_ahead)
        
        reminder_list = []
        for reminder in due_reminders:
            reminder_list.append({
                "id": reminder.id,
                "title": reminder.title,
                "description": reminder.description,
                "due_datetime": reminder.due_datetime.isoformat() if reminder.due_datetime else None,
                "priority": reminder.priority,
                "reminder_type": reminder.reminder_type
            })
        
        return {
            "success": True,
            "reminders": reminder_list,
            "count": len(reminder_list)
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def mark_reminder_complete(reminder_id: int, user_telegram_id: str) -> Dict:
    """
    Mark a reminder as completed
    
    Args:
        reminder_id: ID of the reminder
        user_telegram_id: User's Telegram ID (for security)
        
    Returns:
        Success status
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        success = await db.mark_reminder_complete(reminder_id, user_telegram_id)
        
        if success:
            return {"success": True, "message": "Reminder marked as complete"}
        else:
            return {"success": False, "error": "Reminder not found or not owned by user"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def update_reminder(reminder_id: int, user_telegram_id: str, **kwargs) -> Dict:
    """
    Update a reminder
    
    Args:
        reminder_id: ID of the reminder
        user_telegram_id: User's Telegram ID
        **kwargs: Fields to update
        
    Returns:
        Success status
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        updated_reminder = await db.update_reminder(reminder_id, user_telegram_id, **kwargs)
        
        if updated_reminder:
            return {
                "success": True,
                "reminder": {
                    "id": updated_reminder.id,
                    "title": updated_reminder.title,
                    "description": updated_reminder.description,
                    "due_datetime": updated_reminder.due_datetime.isoformat() if updated_reminder.due_datetime else None
                }
            }
        else:
            return {"success": False, "error": "Reminder not found or not owned by user"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def delete_reminder(reminder_id: int, user_telegram_id: str) -> Dict:
    """
    Delete a reminder
    
    Args:
        reminder_id: ID of the reminder
        user_telegram_id: User's Telegram ID
        
    Returns:
        Success status
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        success = await db.delete_reminder(reminder_id, user_telegram_id)
        
        if success:
            return {"success": True, "message": "Reminder deleted"}
        else:
            return {"success": False, "error": "Reminder not found or not owned by user"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}