# agents/expense_agent.py
from typing import Dict, Optional, Any
from decimal import Decimal
from datetime import datetime
import json

from .base_intelligent_agent import BaseIntelligentAgent
from ..prompts.expense_prompts import ExpensePrompts, ExpenseFallbacks
from core.models import Expense

class ExpenseAgent(BaseIntelligentAgent):
    """
    Clean ExpenseAgent with separated prompts and minimal token usage
    Handles expense parsing, validation, and storage with intelligent responses
    """
    
    async def process_message(self, message: str, platform_type: str, platform_user_id: str) -> str:
        """
        Process expense message efficiently
        
        Args:
            message: User's expense message (e.g., "Coffee $4.50", "Café €5.00")
            platform_type: Platform origin
            platform_user_id: Platform-specific user identifier
            
        Returns:
            Intelligent response in user's language
        """
        
        # Quick validation
        validation = self.validate_input(message, platform_type, platform_user_id)
        if not validation["valid"]:
            return f"❌ {'; '.join(validation['errors'])}"
        
        # Get user context
        user_context = await self.get_user_context(platform_type, platform_user_id)
        
        # Parse expense using LLM
        parsed_expense = await self._parse_expense_llm(message, user_context)
        
        if not parsed_expense["success"]:
            return await self._generate_error_response(parsed_expense, user_context)
        
        # Save to database
        save_result = await self._save_expense_db(parsed_expense, user_context, message)
        
        if not save_result["success"]:
            return await self._generate_error_response(save_result, user_context)
        
        # Generate success response
        return await self._generate_success_response(parsed_expense, user_context)
    
    async def get_expense_summary(self, platform_type: str, platform_user_id: str, days: int = 30) -> str:
        """Get expense summary efficiently"""
        
        user_context = await self.get_user_context(platform_type, platform_user_id)
        
        if user_context["is_new_user"]:
            return await self._generate_welcome_message(user_context)
        
        try:
            summary = await self.database.get_expense_summary(user_context["user"].id, days)
            return await self._generate_summary_response(summary, user_context, days)
        except Exception as e:
            print(f"❌ Expense summary error: {e}")
            return ExpenseFallbacks.ERROR.get(user_context["language"], ExpenseFallbacks.ERROR["en"])
    
    # ============================================================================
    # LLM PARSING
    # ============================================================================
    
    async def _parse_expense_llm(self, message: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse expense using compact LLM prompt"""
        
        prompt = ExpensePrompts.expense_parsing(user_context)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Parse: {message}"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True, timeout=10)
        if not response:
            return {"success": False, "error": "Service unavailable"}
        
        try:
            json_text = self.extract_json_from_response(response)
            if not json_text:
                return {"success": False, "error": "Invalid format"}
            
            parsed = json.loads(json_text)
            return self._validate_parsed_expense(parsed, user_context)
            
        except (json.JSONDecodeError, Exception) as e:
            return {"success": False, "error": f"Parse error: {str(e)}"}
    
    def _validate_parsed_expense(self, parsed: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Quick expense validation"""
        
        if not parsed.get("success"):
            return parsed
        
        # Validate required fields
        if not parsed.get("amount") or parsed["amount"] <= 0:
            return {"success": False, "error": "Invalid amount"}
        
        if not parsed.get("description") or not parsed["description"].strip():
            return {"success": False, "error": "Missing description"}
        
        # Set defaults and validate
        valid_currencies = ["USD", "EUR", "BRL"]
        if parsed.get("currency") not in valid_currencies:
            parsed["currency"] = user_context["currency"]
        
        valid_categories = [
            "Food & Dining", "Transportation", "Shopping", "Entertainment", 
            "Utilities", "Healthcare", "Travel", "Education", "Other"
        ]
        if parsed.get("category") not in valid_categories:
            parsed["category"] = "Other"
        
        valid_languages = ["en", "es", "pt"]
        if parsed.get("detected_language") not in valid_languages:
            parsed["detected_language"] = user_context["language"]
        
        # Clean and validate
        parsed["confidence"] = max(0.0, min(1.0, parsed.get("confidence", 0.8)))
        parsed["description"] = parsed["description"].strip()
        
        return parsed
    
    # ============================================================================
    # DATABASE OPERATIONS
    # ============================================================================
    
    async def _save_expense_db(self, parsed_expense: Dict[str, Any], user_context: Dict[str, Any], original_message: str) -> Dict[str, Any]:
        """Save expense to database efficiently"""
        
        try:
            expense = Expense(
                user_id=user_context["user"].id,
                amount=Decimal(str(parsed_expense["amount"])),
                description=parsed_expense["description"],
                category=parsed_expense["category"],
                original_message=original_message,
                source_platform=user_context.get("platform", {}).get("platform_type", "unknown"),
                date=datetime.now(),
                confidence_score=parsed_expense.get("confidence", 0.8)
            )
            
            saved_expense = await self.database.save_expense(expense)
            
            print(f"💾 EXPENSE: {parsed_expense['amount']} {parsed_expense['currency']} - {parsed_expense['description']}")
            
            return {"success": True, "expense_id": saved_expense.id, "expense": saved_expense}
            
        except Exception as e:
            print(f"❌ Save expense error: {e}")
            return {"success": False, "error": f"Save failed: {str(e)}"}
    
    # ============================================================================
    # RESPONSE GENERATION
    # ============================================================================
    
    async def _generate_success_response(self, parsed_expense: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate success response efficiently"""
        
        language = parsed_expense.get("detected_language", user_context["language"])
        amount = parsed_expense["amount"]
        currency = parsed_expense["currency"]
        description = parsed_expense["description"]
        category = parsed_expense["category"]
        
        prompt = ExpensePrompts.success_confirmation(language, amount, currency, description, category)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate confirmation"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True, timeout=8)
        
        if response:
            return response
        
        # Fallback response
        return ExpenseFallbacks.format_success(language, amount, currency, description, category)
    
    async def _generate_error_response(self, error_data: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate error response efficiently"""
        
        language = user_context["language"]
        error_message = error_data.get("error", "Unknown error")
        
        prompt = ExpensePrompts.error_response(language, error_message)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate error message"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True, timeout=8)
        
        if response:
            return response
        
        # Fallback error
        return ExpenseFallbacks.ERROR.get(language, ExpenseFallbacks.ERROR["en"])
    
    async def _generate_welcome_message(self, user_context: Dict[str, Any]) -> str:
        """Generate welcome message efficiently"""
        
        language = user_context["language"]
        currency = user_context["currency"]
        
        prompt = ExpensePrompts.welcome_message(language, currency)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate welcome"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True, timeout=8)
        
        if response:
            return response
        
        # Fallback welcome
        return ExpenseFallbacks.format_welcome(language, currency)
    
    async def _generate_summary_response(self, summary, user_context: Dict[str, Any], days: int) -> str:
        """Generate summary response efficiently"""
        
        language = user_context["language"]
        currency = user_context["currency"]
        
        prompt = ExpensePrompts.summary_response(
            language, currency, float(summary.total_amount), 
            summary.total_count, float(summary.average_amount), days
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate summary"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True, timeout=8)
        
        if response:
            return response
        
        # Fallback summary
        return ExpenseFallbacks.format_summary(
            language, currency, float(summary.total_amount), summary.total_count, days
        )
    
    # ============================================================================
    # REQUIRED ABSTRACT METHODS
    # ============================================================================
    
    async def get_user_patterns(self, user_id: str) -> Dict[str, Any]:
        """Get user expense patterns (simplified)"""
        try:
            recent_expenses = await self.database.get_user_expenses(user_id, days=30)
            if not recent_expenses:
                return {}
            
            # Extract simple patterns
            categories = {}
            for expense in recent_expenses[:10]:
                category = expense.category
                categories[category] = categories.get(category, 0) + 1
            
            return {"common_categories": categories}
        except Exception:
            return {}
    
    def _get_response_template(self, template_key: str, context: Dict[str, Any], language: str) -> str:
        """Not used - we use direct LLM calls"""
        return ""