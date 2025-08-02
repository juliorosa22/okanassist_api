# api/app/utils.py
from fastapi import APIRouter, Depends
from typing import Optional

from api.core.dependencies import get_current_user, get_database
from core.database import Database
from core.models import get_all_categories

# Router setup
router = APIRouter(prefix="/api", tags=["utilities"])

# ============================================================================
# ACTIVITY ENDPOINTS
# ============================================================================

@router.get("/activity/summary")
async def get_activity_summary(
    days: int = 30,
    current_user: dict = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Get comprehensive user activity summary"""
    try:
        activity = await database.get_user_activity_summary(current_user.id, days)
        
        return {
            "success": True,
            "activity": {
                "user_id": activity.user_id,
                "total_interactions": activity.total_interactions,
                "is_active_user": activity.is_active_user(),
                "last_transaction_date": activity.last_transaction_date.isoformat() if activity.last_transaction_date else None,
                "last_reminder_date": activity.last_reminder_date.isoformat() if activity.last_reminder_date else None,
                "transaction_summary": {
                    "total_expenses": float(activity.transaction_summary.total_expenses),
                    "total_income": float(activity.transaction_summary.total_income),
                    "net_income": float(activity.transaction_summary.net_income),
                    "transaction_count": activity.transaction_summary.expense_count + activity.transaction_summary.income_count
                } if activity.transaction_summary else None,
                "reminder_summary": {
                    "total_count": activity.reminder_summary.total_count,
                    "pending_count": activity.reminder_summary.pending_count,
                    "completion_rate": activity.reminder_summary.get_completion_rate()
                } if activity.reminder_summary else None,
                "period_days": days
            }
        }
        
    except Exception as e:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get activity summary: {str(e)}"
        )

# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/categories")
async def get_categories():
    """Get available transaction categories"""
    return {
        "success": True,
        "categories": {
            "expense": get_all_categories("expense"),
            "income": get_all_categories("income")
        }
    }

@router.get("/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile from Supabase"""
    return {
        "success": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "created_at": current_user.created_at,
            "last_sign_in_at": current_user.last_sign_in_at,
            "user_metadata": current_user.user_metadata
        }
    }

@router.get("/health")
async def health_check(database: Database = Depends(get_database)):
    """Health check endpoint"""
    from datetime import datetime
    
    db_status = "connected" if database and database.pool else "disconnected"
    
    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "service": "Okan Personal Assistant API",
        "version": "2.0.0",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }