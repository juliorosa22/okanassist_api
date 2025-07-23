# agents/expense_agent.py
from typing import Dict, Optional, Any
from decimal import Decimal
from datetime import datetime
import json

from .base_intelligent_agent import BaseIntelligentAgent
from core.models import Expense

class ExpenseAgent(BaseIntelligentAgent):
    """
    ExpenseAgent using BaseIntelligentAgent with LLM providers for:
    1. Intelligent parsing and natural response generation
    2. Parse message (category, description, amount)
    3. Detect currencies (USD, EUR, BRL)
    4. Detect user language and respond accordingly
    5. Save expense to database
    6. Compatible with Expense model
    """
    
    async def process_message(self, message: str, platform_type: str, platform_user_id: str) -> str:
        """
        Process expense message using LLM for intelligent parsing
        
        Args:
            message: User's expense message (e.g., "Coffee $4.50", "Café €5.00")
            platform_type: Platform origin (telegram, whatsapp, mobile_app, web_app)
            platform_user_id: Platform-specific user identifier
            
        Returns:
            Intelligent response in user's language
        """
        
        # Validate inputs using base class
        validation = self.validate_input(message, platform_type, platform_user_id)
        if not validation["valid"]:
            return f"❌ {'; '.join(validation['errors'])}"
        
        # Get user context with caching
        user_context = await self.get_user_context(platform_type, platform_user_id)
        
        # Use LLM for intelligent expense parsing
        parsed_expense = await self._parse_expense_with_llm(message, user_context)
        
        if not parsed_expense["success"]:
            return await self._generate_error_response(parsed_expense, user_context)
        
        # Save expense to database
        save_result = await self._save_expense_to_database(parsed_expense, user_context, message)
        
        if not save_result["success"]:
            return await self._generate_error_response(save_result, user_context)
        
        # Generate success response using LLM
        return await self._generate_success_response(parsed_expense, user_context)
    
    async def get_expense_summary(self, platform_type: str, platform_user_id: str, days: int = 30) -> str:
        """Get user's expense summary with intelligent formatting"""
        user_context = await self.get_user_context(platform_type, platform_user_id)
        
        if user_context["is_new_user"]:
            return await self._generate_welcome_message(user_context)
        
        try:
            summary = await self.database.get_expense_summary(user_context["user"].id, days)
            return await self._generate_summary_response(summary, user_context, days)
        except Exception as e:
            print(f"❌ Error getting expense summary: {e}")
            return await self._generate_error_response(
                {"error": "Could not retrieve expense summary"}, 
                user_context
            )
    
    # ============================================================================
    # INTELLIGENT LLM PARSING
    # ============================================================================
    
    async def _parse_expense_with_llm(self, message: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to intelligently parse expense message
        
        Args:
            message: User's expense message
            user_context: User context for personalized parsing
            
        Returns:
            Parsed expense data: {success, amount, currency, description, category, language, error}
        """
        
        # Build intelligent parsing prompt
        system_prompt = self._build_expense_parsing_prompt(user_context)
        
        # Use safe LLM call from base class with retry logic
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Parse this expense: {message}"}
        ]
        
        response_content = await self.safe_llm_call(messages, max_retries=3, cache=True)
        
        if not response_content:
            return {
                "success": False,
                "error": "Service temporarily unavailable. Please try again.",
                "needs_clarification": ["amount", "description"]
            }
        
        try:
            # Extract JSON from LLM response
            json_text = self.extract_json_from_response(response_content)
            if not json_text:
                return {
                    "success": False,
                    "error": "Could not understand the expense format",
                    "needs_clarification": ["amount", "description"]
                }
            
            parsed = json.loads(json_text)
            
            # Validate the parsing result
            return self._validate_parsed_expense(parsed, user_context)
            
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Invalid response format from service",
                "needs_clarification": ["amount", "description"]
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Parsing failed: {str(e)}",
                "needs_clarification": ["amount", "description"]
            }
    
    def _build_expense_parsing_prompt(self, user_context: Dict[str, Any]) -> str:
        """Build intelligent expense parsing prompt for LLM"""
        
        return f"""You are an intelligent expense tracking assistant. Parse natural language expense messages into structured data.

USER CONTEXT:
- Default Language: {user_context["language"]}
- Default Currency: {user_context["currency"]}
- Country: {user_context["country"]}

TASK:
Parse the user's expense message and extract structured information. Be intelligent about:
1. Currency detection (USD $, EUR €, BRL R$)
2. Amount extraction (handle various formats like 4.50, 4,50, etc.)
3. Category inference from description
4. Language detection
5. Clean description extraction

SUPPORTED CURRENCIES:
- USD: "$4.50", "4.50 dollars", "USD 4.50"
- EUR: "€4.50", "4.50 euros", "EUR 4.50"  
- BRL: "R$ 4.50", "4.50 reais", "BRL 4.50"

AVAILABLE CATEGORIES:
Food & Dining, Transportation, Shopping, Entertainment, Utilities, Healthcare, Travel, Education, Other

RESPONSE FORMAT (JSON only):
{{
    "success": true/false,
    "amount": numeric_amount,
    "currency": "USD|EUR|BRL",
    "description": "clean_description",
    "category": "inferred_category",
    "detected_language": "en|es|pt",
    "confidence": 0.0_to_1.0,
    "error": "error_message_if_failed"
}}

PARSING EXAMPLES:
- "Coffee $4.50" → {{"success": true, "amount": 4.50, "currency": "USD", "description": "Coffee", "category": "Food & Dining", "detected_language": "en", "confidence": 0.9}}
- "Café €5.00" → {{"success": true, "amount": 5.00, "currency": "EUR", "description": "Café", "category": "Food & Dining", "detected_language": "es", "confidence": 0.9}}
- "Gasolina R$ 50" → {{"success": true, "amount": 50.00, "currency": "BRL", "description": "Gasolina", "category": "Transportation", "detected_language": "pt", "confidence": 0.9}}
- "Uber ride 12 euros" → {{"success": true, "amount": 12.00, "currency": "EUR", "description": "Uber ride", "category": "Transportation", "detected_language": "en", "confidence": 0.9}}
- "Compré pan 3€" → {{"success": true, "amount": 3.00, "currency": "EUR", "description": "pan", "category": "Food & Dining", "detected_language": "es", "confidence": 0.8}}

LANGUAGE DETECTION RULES:
- Spanish: "café", "compré", "pagué", "euros", "gastó"
- Portuguese: "café", "comprei", "paguei", "reais", "gastei"
- English: default if no clear indicators

CATEGORY DETECTION RULES:
- Food & Dining: coffee, lunch, dinner, restaurant, café, comida, restaurante, food
- Transportation: uber, taxi, gas, fuel, bus, train, gasolina, transporte
- Shopping: amazon, store, clothes, buy, tienda, compra, ropa
- Entertainment: movie, cinema, netflix, película, cine
- Healthcare: doctor, pharmacy, hospital, médico, farmacia
- Other: default if unclear

If parsing fails or information is missing, set success=false and provide clear error message."""
    
    def _validate_parsed_expense(self, parsed: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and enhance the LLM parsing result
        
        Args:
            parsed: Raw parsing result from LLM
            user_context: User context for validation
            
        Returns:
            Validated parsing result
        """
        if not parsed.get("success"):
            return parsed
        
        # Validate required fields
        if not parsed.get("amount") or parsed["amount"] <= 0:
            return {
                "success": False,
                "error": "Invalid or missing amount"
            }
        
        if not parsed.get("description") or not parsed["description"].strip():
            return {
                "success": False,
                "error": "Missing expense description"
            }
        
        # Validate and set currency
        valid_currencies = ["USD", "EUR", "BRL"]
        if parsed.get("currency") not in valid_currencies:
            parsed["currency"] = user_context["currency"]  # Default to user's currency
        
        # Validate and set category
        valid_categories = [
            "Food & Dining", "Transportation", "Shopping", "Entertainment", 
            "Utilities", "Healthcare", "Travel", "Education", "Other"
        ]
        if parsed.get("category") not in valid_categories:
            parsed["category"] = "Other"
        
        # Validate language
        valid_languages = ["en", "es", "pt"]
        if parsed.get("detected_language") not in valid_languages:
            parsed["detected_language"] = user_context["language"]
        
        # Ensure confidence is between 0 and 1
        parsed["confidence"] = max(0.0, min(1.0, parsed.get("confidence", 0.8)))
        
        # Clean description
        parsed["description"] = parsed["description"].strip()
        
        return parsed
    
    # ============================================================================
    # DATABASE OPERATIONS
    # ============================================================================
    
    async def _save_expense_to_database(self, parsed_expense: Dict[str, Any], user_context: Dict[str, Any], original_message: str) -> Dict[str, Any]:
        """
        Save the parsed expense to database
        
        Args:
            parsed_expense: Validated parsing result
            user_context: User context
            original_message: Original user message
            
        Returns:
            Save result
        """
        try:
            # Create Expense object compatible with models.py
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
            
            # Save to database
            saved_expense = await self.database.save_expense(expense)
            
            print(f"💾 EXPENSE SAVED: {parsed_expense['amount']} {parsed_expense['currency']} - {parsed_expense['description']} ({parsed_expense['category']})")
            
            return {
                "success": True,
                "expense_id": saved_expense.id,
                "expense": saved_expense
            }
            
        except Exception as e:
            print(f"❌ SAVE EXPENSE ERROR: {e}")
            return {
                "success": False,
                "error": f"Failed to save expense: {str(e)}"
            }
    
    # ============================================================================
    # INTELLIGENT RESPONSE GENERATION
    # ============================================================================
    
    async def _generate_success_response(self, parsed_expense: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate success response using LLM in user's language"""
        
        language = parsed_expense.get("detected_language", user_context["language"])
        amount = parsed_expense["amount"]
        currency = parsed_expense["currency"]
        description = parsed_expense["description"]
        category = parsed_expense["category"]
        
        # Build response generation prompt
        system_prompt = f"""Generate a friendly expense confirmation message in {language}.

EXPENSE DETAILS:
- Amount: {amount} {currency}
- Description: {description}
- Category: {category}

INSTRUCTIONS:
1. Respond in {language} language
2. Use appropriate currency symbol ($ for USD, € for EUR, R$ for BRL)
3. Be concise and friendly
4. Include checkmark emoji ✅
5. Format: "✅ [Expense saved/Gasto guardado/Despesa salva]: [amount] for/para [description] ([category])"

EXAMPLES:
- English: "✅ Expense saved: $4.50 for Coffee (Food & Dining)"
- Spanish: "✅ Gasto guardado: €4.50 para Café (Comida y Cenas)"
- Portuguese: "✅ Despesa salva: R$ 4.50 para Café (Alimentação)"

Respond with just the confirmation message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate confirmation message"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback response if LLM fails
        currency_symbol = {"USD": "$", "EUR": "€", "BRL": "R$"}.get(currency, currency)
        
        if language == "es":
            return f"✅ Gasto guardado: {currency_symbol}{amount} para {description} ({category})"
        elif language == "pt":
            return f"✅ Despesa salva: {currency_symbol}{amount} para {description} ({category})"
        else:
            return f"✅ Expense saved: {currency_symbol}{amount} for {description} ({category})"
    
    async def _generate_error_response(self, error_data: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate error response using LLM in user's language"""
        
        language = user_context["language"]
        error_message = error_data.get("error", "Unknown error")
        
        system_prompt = f"""Generate a helpful error message for expense tracking in {language}.

ERROR: {error_message}

INSTRUCTIONS:
1. Respond in {language} language
2. Be apologetic but helpful
3. Give an example of correct format
4. Use appropriate currency symbol for the user's region
5. Include ❌ emoji

EXAMPLES:
- English: "❌ I couldn't find the amount. Please try: 'Coffee $4.50'"
- Spanish: "❌ No pude encontrar el monto. Prueba: 'Café €4.50'"
- Portuguese: "❌ Não consegui encontrar o valor. Tente: 'Café R$ 4.50'"

Respond with just the error message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate error message"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback error responses
        if language == "es":
            return "❌ Error al procesar el gasto. Prueba: 'Café €4.50'"
        elif language == "pt":
            return "❌ Erro ao processar a despesa. Tente: 'Café R$ 4.50'"
        else:
            return "❌ Error processing expense. Try: 'Coffee $4.50'"
    
    async def _generate_welcome_message(self, user_context: Dict[str, Any]) -> str:
        """Generate welcome message for new users"""
        
        language = user_context["language"]
        currency = user_context["currency"]
        
        system_prompt = f"""Generate a welcome message for a new user asking for expense summary in {language}.

USER CONTEXT:
- Language: {language}
- Default Currency: {currency}

INSTRUCTIONS:
1. Respond in {language} language
2. Welcome them warmly
3. Explain they don't have expenses yet
4. Give example with appropriate currency
5. Be encouraging

EXAMPLES:
- English: "👋 Welcome! You don't have any expenses yet. Try: 'Coffee $4.50'"
- Spanish: "👋 ¡Bienvenido! Aún no tienes gastos. Prueba: 'Café €4.50'"
- Portuguese: "👋 Bem-vindo! Você ainda não tem despesas. Tente: 'Café R$ 4.50'"

Respond with just the welcome message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate welcome message"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback welcome messages
        currency_symbol = {"USD": "$", "EUR": "€", "BRL": "R$"}.get(currency, "$")
        
        if language == "es":
            return f"👋 ¡Bienvenido! Aún no tienes gastos. Prueba: 'Café {currency_symbol}4.50'"
        elif language == "pt":
            return f"👋 Bem-vindo! Você ainda não tem despesas. Tente: 'Café {currency_symbol}4.50'"
        else:
            return f"👋 Welcome! You don't have any expenses yet. Try: 'Coffee {currency_symbol}4.50'"
    
    async def _generate_summary_response(self, summary, user_context: Dict[str, Any], days: int) -> str:
        """Generate summary response using LLM"""
        
        language = user_context["language"]
        currency = user_context["currency"]
        
        system_prompt = f"""Generate an expense summary report in {language}.

SUMMARY DATA:
- Total Amount: {summary.total_amount} {currency}
- Total Expenses: {summary.total_count}
- Average Amount: {summary.average_amount} {currency}
- Period: {days} days

INSTRUCTIONS:
1. Respond in {language} language
2. Use 📊 emoji
3. Be concise but informative
4. Use appropriate currency symbol

EXAMPLES:
- English: "📊 Last 30 days: $234.50 total, 15 expenses, avg $15.63"
- Spanish: "📊 Últimos 30 días: €234.50 total, 15 gastos, promedio €15.63"
- Portuguese: "📊 Últimos 30 dias: R$ 234.50 total, 15 despesas, média R$ 15.63"

Respond with just the summary message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate summary message"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback summary
        currency_symbol = {"USD": "$", "EUR": "€", "BRL": "R$"}.get(currency, "$")
        
        if language == "es":
            return f"📊 Últimos {days} días: {currency_symbol}{summary.total_amount} total, {summary.total_count} gastos"
        elif language == "pt":
            return f"📊 Últimos {days} dias: {currency_symbol}{summary.total_amount} total, {summary.total_count} despesas"
        else:
            return f"📊 Last {days} days: {currency_symbol}{summary.total_amount} total, {summary.total_count} expenses"
    
    # ============================================================================
    # REQUIRED ABSTRACT METHODS FROM BASE CLASS
    # ============================================================================
    
    async def get_user_patterns(self, user_id: str) -> Dict[str, Any]:
        """
        Get user expense patterns (simplified for now)
        Could be enhanced to provide user's favorite categories, merchants, etc.
        """
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
        """
        Get response template (not used in this implementation since we use LLM directly)
        Required by base class but not used here
        """
        return ""