# api_main.py - FastAPI with Supabase Auth Integration
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from supabase import create_client, Client
from gotrue.errors import AuthApiError
import os
import uvicorn
from dotenv import load_dotenv
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator
from decimal import Decimal

# Load environment variables
load_dotenv()

# Import your modules
from core.database import Database
from core.models import Transaction, Reminder, TransactionType, ReminderType, Priority

# Global instances
database = None
supabase: Client = None
security = HTTPBearer()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")  # sb_publishable_...
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")  # sb_secret_... (for admin operations)
DATABASE_URL = os.getenv("DATABASE_URL")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global database, supabase
    try:
        # Initialize Supabase client
        supabase = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
        print("✅ Supabase client initialized")
        
        # Initialize database
        database = Database(DATABASE_URL)
        await database.connect()
        print("✅ Application database connected")
        
    except Exception as e:
        print(f"❌ Startup error: {e}")
        raise
    
    yield
    
    # Shutdown
    try:
        if database:
            await database.close()
            print("✅ Database disconnected")
    except Exception as e:
        print(f"⚠️ Shutdown error: {e}")

# Create FastAPI app
app = FastAPI(
    title="Okan Personal Assistant API",
    description="Multi-platform personal assistant with Supabase authentication",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:19006",
        "https://your-frontend-domain.com",  # Add your frontend domain
        "*"  # Remove in production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# Authentication dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current authenticated user from Supabase"""
    try:
        # Verify JWT token with Supabase
        user = supabase.auth.get_user(credentials.credentials)
        
        if not user or not user.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        return user.user
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

# Pydantic models for API requests
class TransactionRequest(BaseModel):
    amount: float
    description: str
    transaction_type: str  # 'expense' or 'income'
    category: Optional[str] = None
    merchant: Optional[str] = None
    date: Optional[datetime] = None
    location: Optional[dict] = None
    tags: Optional[list] = None
    
    @field_validator('transaction_type')
    def validate_transaction_type(cls, v):
        if v not in ['expense', 'income']:
            raise ValueError('transaction_type must be either "expense" or "income"')
        return v
    
    @field_validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('amount must be positive')
        return v

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

# Root endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Okan Personal Assistant API v2.0",
        "features": ["Supabase Authentication", "Transaction Tracking", "Smart Reminders"],
        "docs": "/docs",
        "health": "/api/health"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    db_status = "connected" if database and database.pool else "disconnected"
    supabase_status = "connected" if supabase else "disconnected"
    
    return {
        "status": "healthy" if db_status == "connected" and supabase_status == "connected" else "unhealthy",
        "service": "Okan Personal Assistant API",
        "version": "2.0.0",
        "database": db_status,
        "supabase": supabase_status,
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================================
# TRANSACTION ENDPOINTS (Expenses + Income)
# ============================================================================

@app.post("/api/transactions")
async def create_transaction(
    transaction_data: TransactionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new transaction (expense or income)"""
    try:
        # Auto-categorize if not provided
        if not transaction_data.category:
            from core.models import categorize_transaction
            transaction_data.category = categorize_transaction(
                transaction_data.description, 
                transaction_data.transaction_type
            )
        
        # Create transaction object
        transaction = Transaction(
            user_id=current_user.id,
            amount=Decimal(str(transaction_data.amount)),
            description=transaction_data.description,
            category=transaction_data.category,
            transaction_type=transaction_data.transaction_type,
            original_message=f"{transaction_data.description} {transaction_data.amount}",
            source_platform="web_app",
            merchant=transaction_data.merchant,
            date=transaction_data.date or datetime.now(),
            location=transaction_data.location,
            tags=transaction_data.tags or []
        )
        
        # Save to database
        saved_transaction = await database.save_transaction(transaction)
        
        return {
            "success": True,
            "message": f"{'Expense' if transaction.is_expense() else 'Income'} recorded successfully",
            "transaction": saved_transaction.to_dict()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create transaction: {str(e)}"
        )

@app.get("/api/transactions")
async def get_transactions(
    days: int = 30,
    transaction_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get user's transactions"""
    try:
        if transaction_type and transaction_type not in ['expense', 'income']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="transaction_type must be 'expense' or 'income'"
            )
        
        transactions = await database.get_user_transactions(
            current_user.id, days, transaction_type
        )
        
        return {
            "success": True,
            "transactions": [t.to_dict() for t in transactions],
            "count": len(transactions),
            "period_days": days,
            "transaction_type": transaction_type or "all"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transactions: {str(e)}"
        )

@app.get("/api/transactions/summary")
async def get_transaction_summary(
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    """Get transaction summary with expenses and income breakdown"""
    try:
        summary = await database.get_transaction_summary(current_user.id, days)
        
        return {
            "success": True,
            "summary": {
                "total_expenses": float(summary.total_expenses),
                "total_income": float(summary.total_income),
                "net_income": float(summary.net_income),
                "expense_count": summary.expense_count,
                "income_count": summary.income_count,
                "average_expense": float(summary.average_expense),
                "average_income": float(summary.average_income),
                "expense_categories": summary.expense_categories,
                "income_categories": summary.income_categories,
                "period_days": summary.period_days,
                "is_profitable": summary.is_profitable(),
                "top_expense_category": summary.get_top_expense_category(),
                "top_income_category": summary.get_top_income_category()
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transaction summary: {str(e)}"
        )

# ============================================================================
# REMINDER ENDPOINTS
# ============================================================================

@app.post("/api/reminders")
async def create_reminder(
    reminder_data: ReminderRequest,
    current_user: dict = Depends(get_current_user)
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
        
        return {
            "success": True,
            "message": "Reminder created successfully",
            "reminder": saved_reminder.to_dict()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reminder: {str(e)}"
        )

@app.get("/api/reminders")
async def get_reminders(
    include_completed: bool = False,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get user's reminders"""
    try:
        reminders = await database.get_user_reminders(
            current_user.id, include_completed, limit
        )
        
        return {
            "success": True,
            "reminders": [r.to_dict() for r in reminders],
            "count": len(reminders),
            "include_completed": include_completed
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get reminders: {str(e)}"
        )

@app.get("/api/reminders/due")
async def get_due_reminders(
    hours_ahead: int = 24,
    current_user: dict = Depends(get_current_user)
):
    """Get reminders due within specified hours"""
    try:
        due_reminders = await database.get_due_reminders(current_user.id, hours_ahead)
        
        return {
            "success": True,
            "reminders": [r.to_dict() for r in due_reminders],
            "count": len(due_reminders),
            "hours_ahead": hours_ahead
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get due reminders: {str(e)}"
        )

@app.put("/api/reminders/{reminder_id}/complete")
async def complete_reminder(
    reminder_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Mark a reminder as completed"""
    try:
        success = await database.mark_reminder_complete(reminder_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reminder not found or already completed"
            )
        
        return {
            "success": True,
            "message": "Reminder marked as completed",
            "reminder_id": reminder_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete reminder: {str(e)}"
        )

@app.get("/api/reminders/summary")
async def get_reminder_summary(
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    """Get reminder summary"""
    try:
        summary = await database.get_reminder_summary(current_user.id, days)
        
        return {
            "success": True,
            "summary": {
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
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get reminder summary: {str(e)}"
        )

# ============================================================================
# USER ACTIVITY ENDPOINTS
# ============================================================================

@app.get("/api/activity/summary")
async def get_activity_summary(
    days: int = 30,
    current_user: dict = Depends(get_current_user)
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get activity summary: {str(e)}"
        )

# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@app.get("/api/categories")
async def get_categories():
    """Get available transaction categories"""
    from core.models import get_all_categories
    
    return {
        "success": True,
        "categories": {
            "expense": get_all_categories("expense"),
            "income": get_all_categories("income")
        }
    }

@app.get("/api/user/profile")
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

# Run the server
if __name__ == "__main__":
    uvicorn.run(
        "api_main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )