# agents/tools.py
import re
from decimal import Decimal
from datetime import datetime
from typing import Dict, Optional
from langchain_core.tools import tool

from core.database import Database
from core.models import Expense, User
from utils.categories import categorize_expense, get_all_categories

# Global database instance (will be injected)
db: Optional[Database] = None

def set_database(database: Database):
    """Set the global database instance"""
    global db
    db = database

@tool
async def parse_expense_from_message(message: str) -> Dict:
    """
    Extract expense information from user message
    
    Args:
        message: User's expense message
        
    Returns:
        Dictionary with amount, description, and parsing success
    """
    # Patterns to extract money amounts
    amount_patterns = [
        r'\$(\d+(?:\.\d{2})?)',  # $25.50
        r'(\d+(?:\.\d{2})?)\s*(?:dollars?|bucks?|\$)',  # 25.50 dollars
        r'(\d+(?:\.\d{2})?)\s*usd',  # 25.50 USD
    ]
    
    # Try to find amount
    amount = None
    for pattern in amount_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            try:
                amount = Decimal(match.group(1))
                break
            except:
                continue
    
    if not amount:
        return {
            "success": False,
            "error": "Could not find amount in message",
            "message": message
        }
    
    # Extract description (remove amount from message)
    description = message
    for pattern in amount_patterns:
        description = re.sub(pattern, '', description, flags=re.IGNORECASE)
    
    # Clean up description
    description = re.sub(r'\s+', ' ', description).strip()
    description = description.strip('.,!?-')
    
    if not description:
        description = "Expense"
    
    return {
        "success": True,
        "amount": float(amount),
        "description": description,
        "original_message": message
    }

@tool
async def categorize_expense_description(description: str) -> str:
    """
    Categorize an expense based on its description
    
    Args:
        description: Description of the expense
        
    Returns:
        Category name
    """
    category = categorize_expense(description)
    print(f"✅ CATEGORY RESULT: '{category}'")
    return category

@tool
async def save_user_expense(user_telegram_id: str, amount: float, description: str, 
                           category: str, original_message: str, merchant: str = None) -> Dict:
    """
    Save an expense to the database
    
    Args:
        user_telegram_id: User's Telegram ID
        amount: Expense amount
        description: Expense description
        category: Expense category
        original_message: Original user message
        merchant: Merchant name (optional)
        
    Returns:
        Success status and expense details
    """
    print(f"💾 SAVING EXPENSE: ${amount} - {description} - {category}")
    
    
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        # Create expense object

        expense = Expense(
            user_telegram_id=user_telegram_id,
            amount=Decimal(str(amount)),
            description=description,
            category=category,
            original_message=original_message,
            merchant=merchant,
            date=datetime.now()
        )
        print(description)
        # Save to database
        saved_expense = await db.save_expense(expense)
        
        return {
            "success": True,
            "expense_id": saved_expense.id,
            "amount": float(saved_expense.amount),
            "description": saved_expense.description,
            "category": saved_expense.category,
            "merchant": saved_expense.merchant
        }
    
    except Exception as e:
        print(f"❌ SAVE ERROR: {e}")
        return {"success": False, "error": str(e)}

@tool
async def get_user_expense_summary(user_telegram_id: str, days: int = 30) -> Dict:
    """
    Get expense summary for user
    
    Args:
        user_telegram_id: User's Telegram ID
        days: Number of days to look back (default 30)
        
    Returns:
        Expense summary with totals and categories
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        summary = await db.get_expense_summary(user_telegram_id, days)
        
        return {
            "success": True,
            "period_days": days,
            "total_amount": float(summary.total_amount),
            "total_count": summary.total_count,
            "average_amount": float(summary.average_amount),
            "categories": summary.categories
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def create_or_update_user(telegram_id: str, username: str = None, 
                               first_name: str = None, last_name: str = None) -> Dict:
    """
    Create or update user in database
    
    Args:
        telegram_id: User's Telegram ID
        username: Username (optional)
        first_name: First name (optional)
        last_name: Last name (optional)
        
    Returns:
        Success status
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        
        await db.create_user(user)
        
        return {
            "success": True,
            "user_id": telegram_id,
            "message": f"User {first_name or telegram_id} ready to track expenses"
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def get_expense_categories() -> Dict:
    """
    Get all available expense categories
    
    Returns:
        List of available categories
    """
    categories = get_all_categories()
    
    return {
        "success": True,
        "categories": categories,
        "count": len(categories)
    }

@tool
async def detect_merchant_from_description(description: str) -> Optional[str]:
    """
    Try to extract merchant name from expense description
    
    Args:
        description: Expense description
        
    Returns:
        Merchant name if detected, None otherwise
    """
    # Common patterns for merchant detection
    merchant_patterns = [
        r'(?:at|@)\s+([A-Za-z\s&\']+?)(?:\s|$)',  # "at Starbucks"
        r'^([A-Za-z\s&\']+?)(?:\s*-|\s*$)',  # "Starbucks -" or just "Starbucks"
    ]
    
    for pattern in merchant_patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            merchant = match.group(1).strip()
            # Filter out common words that aren't merchant names
            skip_words = ['the', 'a', 'an', 'for', 'with', 'and', 'or', 'in', 'on']
            if len(merchant) > 2 and merchant.lower() not in skip_words:
                return merchant.title()
    
    return None