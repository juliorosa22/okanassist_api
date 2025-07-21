# agents/tools/intelligent_expense_tools.py
from typing import Dict, Optional, Any
from decimal import Decimal
from datetime import datetime
from langchain_core.tools import tool

from core.database import Database
from core.models import User, UserPlatform, Expense, PlatformType, create_user_from_platform_data
from utils.categories import categorize_expense, get_all_categories

# Global database instance
db: Optional[Database] = None

def set_database(database: Database):
    """Set the global database instance"""
    global db
    db = database

@tool
async def get_or_create_user_from_platform(platform_type: str, platform_user_id: str, 
                                          user_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Get existing user or create new user from platform credentials
    
    Args:
        platform_type: Platform type (telegram, whatsapp, mobile_app, web_app)
        platform_user_id: Platform-specific user ID
        user_data: Optional user data for creation
        
    Returns:
        User information and context
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        # Try to get existing user
        user_platform_data = await db.get_user_by_platform(platform_type, platform_user_id)
        
        if user_platform_data:
            user, platform = user_platform_data
            
            # Update platform activity
            await db.update_platform_activity(platform_type, platform_user_id)
            
            return {
                "success": True,
                "user": user,
                "platform": platform,
                "is_new_user": False
            }
        else:
            # Create new user
            user_data = user_data or {}
            user, platform = create_user_from_platform_data(platform_type, {
                'platform_user_id': platform_user_id,
                'first_name': user_data.get('first_name'),
                'last_name': user_data.get('last_name'),
                'username': user_data.get('username'),
                'email': user_data.get('email'),
                'phone_number': user_data.get('phone_number')
            })
            
            # Save to database
            await db.create_user(user)
            await db.create_user_platform(platform)
            
            print(f"✅ Created new user: {user.id} on platform {platform_type}")
            
            return {
                "success": True,
                "user": user,
                "platform": platform,
                "is_new_user": True
            }
            
    except Exception as e:
        print(f"❌ Error getting/creating user: {e}")
        return {"success": False, "error": str(e)}

@tool
async def save_intelligent_expense(user_id: str, amount: float, description: str, 
                                 category: str, original_message: str, 
                                 source_platform: str, merchant: str = None,
                                 currency: str = "USD", confidence_score: float = 0.8) -> Dict[str, Any]:
    """
    Save an intelligently parsed expense to the database
    
    Args:
        user_id: User ID from the database
        amount: Expense amount (already converted to user's currency)
        description: Clean expense description
        category: Categorized expense category
        original_message: Original user message
        source_platform: Platform where expense was created
        merchant: Detected merchant (optional)
        currency: Currency code
        confidence_score: LLM parsing confidence
        
    Returns:
        Success status and expense details
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        # Create expense object
        expense = Expense(
            user_id=user_id,
            amount=Decimal(str(amount)),
            description=description,
            category=category,
            original_message=original_message,
            source_platform=source_platform,
            merchant=merchant,
            date=datetime.now(),
            confidence_score=confidence_score
        )
        
        print(f"💾 SAVING INTELLIGENT EXPENSE: ${amount} - {description} - {category} (confidence: {confidence_score})")
        
        # Save to database
        saved_expense = await db.save_expense(expense)
        
        return {
            "success": True,
            "expense_id": saved_expense.id,
            "amount": float(saved_expense.amount),
            "description": saved_expense.description,
            "category": saved_expense.category,
            "merchant": saved_expense.merchant,
            "user_id": saved_expense.user_id,
            "confidence_score": saved_expense.confidence_score
        }
    
    except Exception as e:
        print(f"❌ SAVE INTELLIGENT EXPENSE ERROR: {e}")
        return {"success": False, "error": str(e)}

@tool
async def get_user_expense_context(user_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Get user expense context for intelligent processing
    
    Args:
        user_id: User ID
        days: Number of days to look back
        
    Returns:
        User expense patterns and context
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        # Get recent expenses
        expenses = await db.get_user_expenses(user_id, days)
        
        # Extract patterns
        patterns = {
            "common_categories": {},
            "common_merchants": {},
            "typical_amounts": {},
            "recent_descriptions": []
        }
        
        for expense in expenses:
            # Category frequency
            category = expense.category
            patterns["common_categories"][category] = patterns["common_categories"].get(category, 0) + 1
            
            # Merchant frequency
            if expense.merchant:
                merchant = expense.merchant
                patterns["common_merchants"][merchant] = patterns["common_merchants"].get(merchant, 0) + 1
            
            # Typical amounts by category
            if category not in patterns["typical_amounts"]:
                patterns["typical_amounts"][category] = []
            patterns["typical_amounts"][category].append(float(expense.amount))
            
            # Recent descriptions for context
            if len(patterns["recent_descriptions"]) < 10:
                patterns["recent_descriptions"].append({
                    "description": expense.description,
                    "category": expense.category,
                    "amount": float(expense.amount)
                })
        
        return {
            "success": True,
            "patterns": patterns,
            "total_expenses": len(expenses),
            "period_days": days
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def get_intelligent_expense_summary(user_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Get expense summary with enhanced data for intelligent responses
    
    Args:
        user_id: User ID
        days: Number of days to look back
        
    Returns:
        Enhanced expense summary
    """
    if not db:
        return {"success": False, "error": "Database not available"}
    
    try:
        summary = await db.get_expense_summary(user_id, days)
        
        # Get additional insights
        expenses = await db.get_user_expenses(user_id, days)
        
        # Calculate additional metrics
        daily_average = float(summary.total_amount) / days if days > 0 else 0
        
        # Find largest expense
        largest_expense = None
        if expenses:
            largest_expense = max(expenses, key=lambda x: x.amount)
        
        # Most frequent category
        top_category = summary.get_top_category()
        
        return {
            "success": True,
            "total_amount": float(summary.total_amount),
            "total_count": summary.total_count,
            "average_amount": float(summary.average_amount),
            "daily_average": daily_average,
            "categories": summary.categories,
            "period_days": days,
            "largest_expense": {
                "amount": float(largest_expense.amount),
                "description": largest_expense.description,
                "category": largest_expense.category
            } if largest_expense else None,
            "top_category": top_category
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
async def suggest_expense_category(description: str, user_id: str = None) -> str:
    """
    Suggest category for expense using both rule-based and user pattern analysis
    
    Args:
        description: Expense description
        user_id: User ID for personalized suggestions
        
    Returns:
        Suggested category
    """
    # Use existing categorization as base
    base_category = categorize_expense(description)
    
    if not user_id or not db:
        return base_category
    
    try:
        # Get user patterns to improve suggestion
        context = await get_user_expense_context(user_id, days=90)
        
        if context.get("success") and context["patterns"]["common_categories"]:
            # Check if user has a strong preference for certain categories
            user_categories = context["patterns"]["common_categories"]
            
            # If user frequently uses a specific category, and the description matches patterns,
            # we could adjust the suggestion here
            # For now, return the base category
            return base_category
        
        return base_category
        
    except Exception as e:
        print(f"❌ Error suggesting category: {e}")
        return base_category