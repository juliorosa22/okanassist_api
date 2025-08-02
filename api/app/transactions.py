# api/app/transactions.py
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from decimal import Decimal

from api.core.dependencies import get_current_user, get_database
from core.database import Database
from core.models import Transaction, categorize_transaction

# Transaction-specific Pydantic models
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

class TransactionResponse(BaseModel):
    success: bool
    message: str
    transaction: Optional[dict] = None

class TransactionListResponse(BaseModel):
    success: bool
    transactions: list
    count: int
    period_days: int
    transaction_type: str

class TransactionSummaryResponse(BaseModel):
    success: bool
    summary: dict

# Router setup
router = APIRouter(prefix="/api/transactions", tags=["transactions"])

@router.post("/", response_model=TransactionResponse)
async def create_transaction(
    transaction_data: TransactionRequest,
    current_user: dict = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Create a new transaction (expense or income)"""
    try:
        # Auto-categorize if not provided
        if not transaction_data.category:
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
        
        return TransactionResponse(
            success=True,
            message=f"{'Expense' if transaction.is_expense() else 'Income'} recorded successfully",
            transaction=saved_transaction.to_dict()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create transaction: {str(e)}"
        )

@router.get("/", response_model=TransactionListResponse)
async def get_transactions(
    days: int = 30,
    transaction_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    database: Database = Depends(get_database)
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
        
        return TransactionListResponse(
            success=True,
            transactions=[t.to_dict() for t in transactions],
            count=len(transactions),
            period_days=days,
            transaction_type=transaction_type or "all"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transactions: {str(e)}"
        )

@router.get("/summary", response_model=TransactionSummaryResponse)
async def get_transaction_summary(
    days: int = 30,
    current_user: dict = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Get transaction summary with expenses and income breakdown"""
    try:
        summary = await database.get_transaction_summary(current_user.id, days)
        
        return TransactionSummaryResponse(
            success=True,
            summary={
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
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transaction summary: {str(e)}"
        )