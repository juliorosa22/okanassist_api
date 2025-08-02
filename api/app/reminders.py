# api/app/reminders.py
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

from api.core.dependencies import get_current_user, get_database
from core.database import Database
from core.models import Reminder, ReminderType, Priority

# Reminder-specific Pydantic models
class ReminderRequest(BaseModel):
    title: str
    description: str
    due_datetime: Optional[datetime] = None
    reminder_type: str = "general"
    priority: str = "medium"
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None
    tags: Optional[str] = None
    
    @field_validator('reminder_type')
    def validate_reminder_type(cls, v):
        valid_types = [t.value for t in ReminderType]
        if v not in valid_types:
            raise ValueError(f'reminder_type must be one of: {valid_types}')
        return v
    
    @field_validator('priority')
    def validate_priority(cls, v):
        valid_priorities = [p.value for p in Priority]
        if v not in valid_priorities:
            raise ValueError(f'priority must be one of: {valid_priorities}')
        return v

class ReminderResponse(BaseModel):
    success: bool
    message: str
    reminder: Optional[dict] = None

class ReminderListResponse(BaseModel):
    success: bool
    reminders: list
    count: int
    include_completed: bool

class ReminderDueResponse(BaseModel):
    success: bool
    reminders: list
    count: int
    hours_ahead: int

class ReminderCompleteResponse(BaseModel):
    success: bool
    message: str
    reminder_id: int

class ReminderSummaryResponse(BaseModel):
    success: bool
    summary: dict

# Router setup
router = APIRouter(prefix="/api/reminders", tags=["reminders"])

@router.post("/", response_model=ReminderResponse)
async def create_reminder(
    reminder_data: ReminderRequest,
    current_user: dict = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Create a new reminder"""
    try:
        reminder = Reminder(
            user_id=current_user.id,
            title=reminder_data.title,
            description=reminder_data.description,
            source_platform="web_app",
            due_datetime=reminder_data.due_datetime,
            reminder_type=reminder_data.reminder_type,
            priority=reminder_data.priority,
            is_recurring=reminder_data.is_recurring,
            recurrence_pattern=reminder_data.recurrence_pattern,
            tags=reminder_data.tags
        )
        
        saved_reminder = await database.save_reminder(reminder)
        
        return ReminderResponse(
            success=True,
            message="Reminder created successfully",
            reminder=saved_reminder.to_dict()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reminder: {str(e)}"
        )

@router.get("/", response_model=ReminderListResponse)
async def get_reminders(
    include_completed: bool = False,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Get user's reminders"""
    try:
        reminders = await database.get_user_reminders(
            current_user.id, include_completed, limit
        )
        
        return ReminderListResponse(
            success=True,
            reminders=[r.to_dict() for r in reminders],
            count=len(reminders),
            include_completed=include_completed
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get reminders: {str(e)}"
        )

@router.get("/due", response_model=ReminderDueResponse)
async def get_due_reminders(
    hours_ahead: int = 24,
    current_user: dict = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Get reminders due within specified hours"""
    try:
        due_reminders = await database.get_due_reminders(current_user.id, hours_ahead)
        
        return ReminderDueResponse(
            success=True,
            reminders=[r.to_dict() for r in due_reminders],
            count=len(due_reminders),
            hours_ahead=hours_ahead
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get due reminders: {str(e)}"
        )

@router.put("/{reminder_id}/complete", response_model=ReminderCompleteResponse)
async def complete_reminder(
    reminder_id: int,
    current_user: dict = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Mark a reminder as completed"""
    try:
        success = await database.mark_reminder_complete(reminder_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reminder not found or already completed"
            )
        
        return ReminderCompleteResponse(
            success=True,
            message="Reminder marked as completed",
            reminder_id=reminder_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete reminder: {str(e)}"
        )

@router.get("/summary", response_model=ReminderSummaryResponse)
async def get_reminder_summary(
    days: int = 30,
    current_user: dict = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Get reminder summary"""
    try:
        summary = await database.get_reminder_summary(current_user.id, days)
        
        return ReminderSummaryResponse(
            success=True,
            summary={
                "total_count": summary.total_count,
                "completed_count": summary.completed_count,
                "pending_count": summary.pending_count,
                "overdue_count": summary.overdue_count,
                "due_today_count": summary.due_today_count,
                "due_tomorrow_count": summary.due_tomorrow_count,
                "completion_rate": summary.get_completion_rate(),
                "has_urgent_items": summary.has_urgent_items(),
                "by_priority": summary.by_priority,
                "by_type": summary.by_type,
                "period_days": summary.period_days
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get reminder summary: {str(e)}"
        )