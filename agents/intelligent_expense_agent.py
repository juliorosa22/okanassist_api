# agents/intelligent_expense_agent.py
from typing import Dict, Optional, Any
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import json
import re
from decimal import Decimal

from core.database import Database
from core.models import User, UserPlatform, Expense, PlatformType

class IntelligentExpenseAgent:
    """
    LLM-powered expense agent that understands natural language 
    in multiple languages and currencies
    """
    
    def __init__(self, groq_api_key: str, database: Database):
        self.llm = ChatGroq(
            model="llama3-70b-8192",
            api_key=groq_api_key,
            temperature=0.1
        )
        self.database = database
    
    async def process_expense(self, message: str, platform_type: str, platform_user_id: str) -> str:
        """
        Main method to process expense messages intelligently
        
        Args:
            message: User's natural language expense message
            platform_type: Platform where message originated (telegram, whatsapp, mobile_app, web_app)
            platform_user_id: Platform-specific user identifier
            
        Returns:
            Intelligent response in user's language confirming expense or requesting clarification
        """
        
        # Get user context for intelligent processing
        user_context = await self._get_user_context(platform_type, platform_user_id)
        
        # Parse expense using LLM intelligence
        parsed_expense = await self._intelligent_expense_parsing(message, user_context)
        
        if not parsed_expense.get("success"):
            return await self._generate_clarification_request(
                message, parsed_expense.get("error"), parsed_expense.get("needs_clarification", []), user_context
            )
        
        # Save the intelligently parsed expense
        save_result = await self._save_expense(parsed_expense, user_context, message)
        
        if not save_result.get("success"):
            return await self._generate_error_response(save_result.get("error"), user_context)
        
        # Generate intelligent confirmation response
        return await self._generate_confirmation(save_result, parsed_expense, user_context)
    
    async def _get_user_context(self, platform_type: str, platform_user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive user context for intelligent processing
        """
        try:
            # Try to get existing user
            user_platform_data = await self.database.get_user_by_platform(platform_type, platform_user_id)
            
            if user_platform_data:
                user, platform = user_platform_data
                
                # Get recent expenses for pattern learning
                recent_expenses = await self.database.get_user_expenses(user.id, days=30)
                recent_patterns = self._extract_expense_patterns(recent_expenses[:10])
                
                return {
                    "user": user,
                    "platform": platform,
                    "language": user.language,
                    "currency": user.default_currency,
                    "timezone": user.timezone,
                    "country": user.country_code,
                    "recent_patterns": recent_patterns,
                    "is_new_user": False
                }
            else:
                # New user - create basic context with smart defaults
                detected_language = self._detect_language_from_platform(platform_type)
                detected_currency = self._detect_currency_from_platform(platform_type)
                
                return {
                    "user": None,
                    "platform": None,
                    "language": detected_language,
                    "currency": detected_currency,
                    "timezone": "UTC",
                    "country": "US",
                    "recent_patterns": {},
                    "is_new_user": True
                }
                
        except Exception as e:
            print(f"❌ Error getting user context: {e}")
            return {
                "user": None,
                "platform": None,
                "language": "en",
                "currency": "USD", 
                "timezone": "UTC",
                "country": "US",
                "recent_patterns": {},
                "is_new_user": True
            }
    
    async def _intelligent_expense_parsing(self, message: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to intelligently parse expense from natural language
        """
        
        # Create intelligent parsing prompt
        system_prompt = f"""You are an intelligent expense tracking assistant. Parse natural language expense messages into structured data.

USER CONTEXT:
- Language: {user_context["language"]}
- Default Currency: {user_context["currency"]}
- Country: {user_context["country"]}
- Timezone: {user_context["timezone"]}

RECENT EXPENSE PATTERNS:
{self._format_patterns_for_prompt(user_context["recent_patterns"])}

TASK:
Parse the user's expense message and extract structured information. Be intelligent about:
1. Currency detection (symbols, words, context)
2. Amount extraction (handle various formats)
3. Category inference from description
4. Merchant detection
5. Language understanding
6. Missing information identification

RESPONSE FORMAT (JSON only):
{{
    "success": true/false,
    "amount": numeric_amount,
    "description": "clean_description",
    "currency": "detected_currency_code",
    "category": "inferred_category",
    "merchant": "detected_merchant_or_null",
    "confidence": 0.0_to_1.0,
    "needs_clarification": ["field1", "field2"],
    "detected_language": "language_code",
    "error": "error_message_if_failed"
}}

AVAILABLE CATEGORIES:
Food & Dining, Transportation, Shopping, Entertainment, Utilities, Healthcare, Travel, Education, Other

CURRENCY DETECTION EXAMPLES:
- "$4.50", "4.50 dollars", "USD 4.50" → USD
- "€4.50", "4.50 euros", "EUR 4.50" → EUR  
- "R$ 4.50", "4.50 reais", "BRL 4.50" → BRL
- "¥4.50", "4.50 yen", "JPY 4.50" → JPY

PARSING EXAMPLES:
- "Coffee $4.50" → amount: 4.50, currency: USD, category: Food & Dining, description: Coffee
- "Uber ride 12€" → amount: 12.00, currency: EUR, category: Transportation, description: Uber ride
- "Compré pan por 3 euros" → amount: 3.00, currency: EUR, category: Food & Dining, description: pan
- "Gasolina R$ 50" → amount: 50.00, currency: BRL, category: Transportation, description: Gasolina

Be smart about incomplete information - if amount is missing, set success=false and needs_clarification=["amount"]."""

        try:
            # Get LLM response
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Parse this expense: {message}")
            ])
            
            # Extract JSON from response
            json_text = self._extract_json_from_response(response.content)
            if not json_text:
                return {
                    "success": False,
                    "error": "Could not parse expense information",
                    "needs_clarification": ["amount", "description"]
                }
            
            parsed = json.loads(json_text)
            
            # Validate and enhance parsing
            return await self._validate_parsing(parsed, user_context)
            
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid response format: {str(e)}",
                "needs_clarification": ["amount", "description"]
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Parsing failed: {str(e)}",
                "needs_clarification": ["amount", "description"]
            }
    
    async def _validate_parsing(self, parsed: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and enhance the LLM parsing result
        """
        if not parsed.get("success"):
            return parsed
        
        # Validate required fields
        if not parsed.get("amount") or parsed["amount"] <= 0:
            return {
                "success": False,
                "error": "Invalid or missing amount",
                "needs_clarification": ["amount"]
            }
        
        if not parsed.get("description"):
            return {
                "success": False,
                "error": "Missing expense description", 
                "needs_clarification": ["description"]
            }
        
        # Set defaults
        parsed["currency"] = parsed.get("currency", user_context["currency"])
        parsed["category"] = parsed.get("category", "Other")
        parsed["detected_language"] = parsed.get("detected_language", user_context["language"])
        
        # Convert currency if needed
        if parsed["currency"] != user_context["currency"]:
            converted_amount = await self._convert_currency(
                parsed["amount"], 
                parsed["currency"], 
                user_context["currency"]
            )
            parsed["converted_amount"] = converted_amount
            parsed["original_amount"] = parsed["amount"]
            parsed["original_currency"] = parsed["currency"]
            parsed["amount"] = converted_amount
            parsed["currency"] = user_context["currency"]
        
        return parsed
    
    async def _save_expense(self, parsed_expense: Dict[str, Any], user_context: Dict[str, Any], original_message: str) -> Dict[str, Any]:
        """
        Save the intelligently parsed expense to database
        """
        try:
            
            user_id = user_context["user"].id
            
            # Create expense object
            expense = Expense(
                user_id=user_id,
                amount=Decimal(str(parsed_expense["amount"])),
                description=parsed_expense["description"],
                category=parsed_expense["category"],
                original_message=original_message,
                source_platform=user_context.get("platform", {}).get("platform_type", "unknown"),
                merchant=parsed_expense.get("merchant"),
                date=datetime.now(),
                confidence_score=parsed_expense.get("confidence", 0.8)
            )
            
            # Save to database
            saved_expense = await self.database.save_expense(expense)
            
            return {
                "success": True,
                "expense": saved_expense,
                "parsed_data": parsed_expense
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to save expense: {str(e)}"
            }
    
    async def _generate_confirmation(self, save_result: Dict[str, Any], parsed_expense: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """
        Generate intelligent confirmation message in user's language
        """
        
        confirmation_prompt = f"""Generate a friendly confirmation message for a successfully saved expense.

USER CONTEXT:
- Language: {user_context["language"]}
- Currency: {user_context["currency"]}

EXPENSE DETAILS:
- Amount: {parsed_expense["amount"]} {parsed_expense["currency"]}
- Description: {parsed_expense["description"]}
- Category: {parsed_expense["category"]}
- Merchant: {parsed_expense.get("merchant", "Not specified")}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Use appropriate currency formatting for the locale
3. Be concise and friendly
4. Include key details clearly
5. Use checkmark emoji ✅

EXAMPLES:
- English: "✅ Expense saved: $4.50 for Coffee (Food & Dining)"
- Spanish: "✅ Gasto guardado: €4.50 por Café (Comida)"
- Portuguese: "✅ Despesa salva: R$ 4.50 para Café (Alimentação)"
- French: "✅ Dépense sauvegardée: €4.50 pour Café (Alimentation)"

Respond with just the confirmation message, no additional text."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=confirmation_prompt),
                HumanMessage(content="Generate confirmation message")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            # Fallback confirmation
            amount_str = f"{parsed_expense['amount']} {parsed_expense['currency']}"
            return f"✅ Expense saved: {amount_str} for {parsed_expense['description']} ({parsed_expense['category']})"
    
    async def _generate_clarification_request(self, original_message: str, error: str, needs_clarification: list, user_context: Dict[str, Any]) -> str:
        """
        Generate helpful clarification request in user's language
        """
        
        clarification_prompt = f"""Generate a helpful clarification request for an expense that couldn't be parsed.

USER CONTEXT:
- Language: {user_context["language"]}
- Currency: {user_context["currency"]}

ORIGINAL MESSAGE: "{original_message}"
ERROR: {error}
NEEDS CLARIFICATION: {needs_clarification}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Be specific about what's missing
3. Give examples in user's currency
4. Be helpful and encouraging, not critical
5. Use appropriate currency symbol

EXAMPLES:
- English: "I couldn't find the amount. Please include the price, like 'Coffee $4.50'"
- Spanish: "No pude encontrar el monto. Por favor incluye el precio, como 'Café €4.50'"
- Portuguese: "Não consegui encontrar o valor. Inclua o preço, como 'Café R$ 4.50'"

Respond with just the clarification message."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=clarification_prompt),
                HumanMessage(content="Generate clarification request")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            # Fallback clarification
            currency_symbol = self._get_currency_symbol(user_context["currency"])
            return f"Could you please include the amount? For example: 'Coffee {currency_symbol}4.50'"
    
    async def _generate_error_response(self, error: str, user_context: Dict[str, Any]) -> str:
        """Generate error response in user's language"""
        
        error_prompt = f"""Generate a helpful error message.

USER CONTEXT:
- Language: {user_context["language"]}

ERROR: {error}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Be apologetic but helpful
3. Suggest trying again
4. Keep it brief

EXAMPLES:
- English: "❌ Sorry, there was an error saving your expense. Please try again."
- Spanish: "❌ Lo siento, hubo un error guardando tu gasto. Inténtalo de nuevo."
- Portuguese: "❌ Desculpe, houve um erro ao salvar sua despesa. Tente novamente."

Respond with just the error message."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=error_prompt),
                HumanMessage(content="Generate error message")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            return "❌ Sorry, there was an error processing your expense. Please try again."
    
    # Helper methods
    def _extract_json_from_response(self, response_text: str) -> Optional[str]:
        """Extract JSON from LLM response"""
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        return json_match.group() if json_match else None
    
    def _extract_expense_patterns(self, recent_expenses) -> Dict[str, Any]:
        """Extract patterns from user's recent expenses for learning"""
        if not recent_expenses:
            return {}
        
        patterns = {
            "common_categories": {},
            "common_merchants": {},
            "typical_amounts": {}
        }
        
        for expense in recent_expenses:
            # Track category frequency
            category = expense.category
            patterns["common_categories"][category] = patterns["common_categories"].get(category, 0) + 1
            
            # Track merchant frequency
            if expense.merchant:
                merchant = expense.merchant
                patterns["common_merchants"][merchant] = patterns["common_merchants"].get(merchant, 0) + 1
            
            # Track typical amounts by category
            if category not in patterns["typical_amounts"]:
                patterns["typical_amounts"][category] = []
            patterns["typical_amounts"][category].append(float(expense.amount))
        
        return patterns
    
    def _format_patterns_for_prompt(self, patterns: Dict[str, Any]) -> str:
        """Format patterns for LLM prompt"""
        if not patterns:
            return "No expense history available"
        
        formatted = []
        
        if patterns.get("common_categories"):
            top_categories = sorted(patterns["common_categories"].items(), key=lambda x: x[1], reverse=True)[:3]
            formatted.append(f"Frequent categories: {', '.join([cat for cat, count in top_categories])}")
        
        if patterns.get("common_merchants"):
            top_merchants = sorted(patterns["common_merchants"].items(), key=lambda x: x[1], reverse=True)[:3]
            formatted.append(f"Frequent merchants: {', '.join([merch for merch, count in top_merchants])}")
        
        return " | ".join(formatted) if formatted else "Learning user patterns..."
    
    def _detect_language_from_platform(self, platform_type: str) -> str:
        """Detect language based on platform context"""
        # Could integrate with platform-specific language detection
        # For now, return default
        return "en"
    
    def _detect_currency_from_platform(self, platform_type: str) -> str:
        """Detect currency based on platform/region"""
        # Could use platform location data
        return "USD"
    
    def _get_currency_symbol(self, currency_code: str) -> str:
        """Get currency symbol for display"""
        symbols = {
            "USD": "$",
            "EUR": "€", 
            "BRL": "R$",
            "GBP": "£",
            "JPY": "¥",
            "CNY": "¥"
        }
        return symbols.get(currency_code, currency_code)
    
    async def _convert_currency(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Convert between currencies"""
        # Placeholder - implement with real currency API
        # For now, return same amount
        return amount
    
    async def get_expense_summary(self, platform_type: str, platform_user_id: str, days: int = 30) -> str:
        """Get intelligent expense summary for user"""
        
        user_context = await self._get_user_context(platform_type, platform_user_id)
        
        if user_context["is_new_user"]:
            return await self._generate_new_user_message(user_context)
        
        # Get expense summary
        summary = await self.database.get_expense_summary(user_context["user"].id, days)
        
        # Generate intelligent summary response
        summary_prompt = f"""Generate an intelligent expense summary report.

USER CONTEXT:
- Language: {user_context["language"]}
- Currency: {user_context["currency"]}
- Period: {days} days

SUMMARY DATA:
- Total Amount: {summary.total_amount} {user_context["currency"]}
- Total Expenses: {summary.total_count}
- Average Amount: {summary.average_amount} {user_context["currency"]}
- Categories: {summary.categories}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Use appropriate currency formatting
3. Include key insights and trends
4. Be concise but informative
5. Use emojis for visual appeal

EXAMPLES:
- English: "📊 Last 30 days: $234.50 total, 15 expenses, avg $15.63. Top category: Food & Dining ($120.00)"
- Spanish: "📊 Últimos 30 días: €234.50 total, 15 gastos, promedio €15.63. Categoría principal: Comida (€120.00)"

Respond with just the summary message."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=summary_prompt),
                HumanMessage(content="Generate expense summary")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            # Fallback summary
            return f"📊 Last {days} days: {summary.get_formatted_total()} total, {summary.total_count} expenses"
    
    async def _generate_new_user_message(self, user_context: Dict[str, Any]) -> str:
        """Generate welcome message for new users"""
        
        welcome_prompt = f"""Generate a friendly welcome message for a new user asking for their expense summary.

USER CONTEXT:
- Language: {user_context["language"]}
- Currency: {user_context["currency"]}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Explain they don't have expenses yet
3. Give example of how to add expenses
4. Be encouraging and helpful
5. Use appropriate currency symbol

EXAMPLES:
- English: "👋 Welcome! You don't have any expenses yet. Try saying 'Coffee $4.50' to track your first expense."
- Spanish: "👋 ¡Bienvenido! Aún no tienes gastos. Prueba diciendo 'Café €4.50' para registrar tu primer gasto."

Respond with just the welcome message."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=welcome_prompt),
                HumanMessage(content="Generate welcome message")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            currency_symbol = self._get_currency_symbol(user_context["currency"])
            return f"👋 Welcome! You don't have any expenses yet. Try saying 'Coffee {currency_symbol}4.50' to track your first expense."