# agents/intelligent_orchestrator_agent.py
from typing import Dict, Optional, Any
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
import json
from datetime import datetime

from core.database import Database
from .intelligent_expense_agent import IntelligentExpenseAgent
from .intelligent_reminder_agent import IntelligentReminderAgent

class IntelligentOrchestratorAgent:
    """
    Core orchestrator agent that routes messages to specialized intelligent agents.
    Focuses purely on the AI logic and message processing.
    """
    
    def __init__(self, groq_api_key: str, database: Database):
        self.groq_api_key = groq_api_key
        self.database = database
        
        # Initialize intelligent routing LLM
        self.router_llm = ChatGroq(
            model="llama3-70b-8192",
            api_key=groq_api_key,
            temperature=0.1
        )
        
        # Initialize specialized intelligent agents
        self.expense_agent = IntelligentExpenseAgent(groq_api_key, database)
        self.reminder_agent = IntelligentReminderAgent(groq_api_key, database)
        
        # Track processing metrics
        self.metrics = {
            "total_processed": 0,
            "expense_requests": 0,
            "reminder_requests": 0,
            "summary_requests": 0,
            "general_queries": 0,
            "routing_errors": 0
        }
    
    async def process_message(self, message: str, platform_type: str, platform_user_id: str, user_info: Dict = None) -> str:
        """
        Main entry point - intelligently route and process any user message
        
        Args:
            message: User's natural language message
            platform_type: Platform origin (telegram, whatsapp, mobile_app, web_app)
            platform_user_id: Platform-specific user identifier
            user_info: Optional additional user information
            
        Returns:
            Intelligent response in user's language
        """
        
        self.metrics["total_processed"] += 1
        
        try:
            # Get user context for intelligent routing
            user_context = await self._get_user_context(platform_type, platform_user_id)
            
            # 🔧 NEW: Check if user is registered before routing
            if user_context["is_new_user"]:
                return await self._handle_unregistered_user(message, user_context, platform_type)
            
            # User is registered - proceed with intelligent routing
            routing_result = await self._intelligent_routing(message, user_context)
            
            if not routing_result.get("success"):
                return await self._handle_routing_error(message, routing_result.get("error"), user_context)
            
            intent = routing_result["intent"]
            confidence = routing_result.get("confidence", 0.8)
            
            print(f"🎯 INTELLIGENT ROUTING: {intent} (confidence: {confidence:.2f}) | Platform: {platform_type}")
            
            # Route to appropriate intelligent agent (user is guaranteed to be registered)
            if intent == "expense":
                self.metrics["expense_requests"] += 1
                return await self.expense_agent.process_expense(message, platform_type, platform_user_id)
                
            elif intent == "reminder":
                self.metrics["reminder_requests"] += 1
                return await self.reminder_agent.process_reminder(message, platform_type, platform_user_id)
                
            elif intent == "expense_summary":
                self.metrics["summary_requests"] += 1
                return await self.expense_agent.get_expense_summary(platform_type, platform_user_id)
                
            elif intent == "reminder_summary":
                self.metrics["summary_requests"] += 1
                return await self.reminder_agent.get_user_reminders_summary(platform_type, platform_user_id)
                
            elif intent == "due_reminders":
                self.metrics["summary_requests"] += 1
                return await self.reminder_agent.check_due_reminders(platform_type, platform_user_id)
                
            elif intent == "general_summary":
                self.metrics["summary_requests"] += 1
                return await self._handle_general_summary(platform_type, platform_user_id, user_context)
                
            else:  # general_conversation
                self.metrics["general_queries"] += 1
                return await self._handle_general_conversation(message, user_context, routing_result)
        
        except Exception as e:
            self.metrics["routing_errors"] += 1
            print(f"❌ Orchestrator error: {e}")
            return await self._generate_error_response(str(e), user_context if 'user_context' in locals() else {})
    
    async def _get_user_context(self, platform_type: str, platform_user_id: str) -> Dict[str, Any]:
        """Get user context for intelligent processing"""
        try:
            user_platform_data = await self.database.get_user_by_platform(platform_type, platform_user_id)
            
            if user_platform_data:
                user, platform = user_platform_data
                return {
                    "user": user,
                    "platform": platform,
                    "language": user.language,
                    "currency": user.default_currency,
                    "timezone": user.timezone,
                    "country": user.country_code,
                    "is_new_user": False
                }
            else:
                return {
                    "user": None,
                    "platform": None,
                    "language": "en",
                    "currency": "USD",
                    "timezone": "UTC",
                    "country": "US",
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
                "is_new_user": True
            }
    
    async def _handle_unregistered_user(self, message: str, user_context: Dict[str, Any], platform_type: str) -> str:
        """
        Handle messages from unregistered users with helpful registration guidance
        """
        
        language = user_context.get("language", "en")
        
        # Generate registration prompt in user's language
        registration_prompt = f"""Generate a helpful registration message for a new user.

    USER CONTEXT:
    - Language: {language}
    - Platform: {platform_type}
    - Message: "{message}"

    INSTRUCTIONS:
    1. Respond in {language}
    2. Welcome them warmly
    3. Explain they need to register first
    4. Mention the platform they're using
    5. Provide clear next steps
    6. Be encouraging and helpful

    EXAMPLES:
    - English: "👋 Welcome! I'd love to help you track expenses and reminders, but you'll need to register first. Visit our website to create your account, then come back here to get started!"
    - Spanish: "👋 ¡Bienvenido! Me encantaría ayudarte con gastos y recordatorios, pero primero necesitas registrarte. Visita nuestro sitio web para crear tu cuenta, ¡luego regresa aquí para comenzar!"
    - Portuguese: "👋 Bem-vindo! Adoraria ajudar você com despesas e lembretes, mas primeiro você precisa se registrar. Visite nosso site para criar sua conta, depois volte aqui para começar!"

    Include appropriate emojis and be platform-specific if helpful.
    Respond with just the registration message."""

        try:
            response = await self.router_llm.ainvoke([
                SystemMessage(content=registration_prompt),
                HumanMessage(content="Generate registration message")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            # Fallback registration messages
            if language == "es":
                return "👋 ¡Hola! Necesitas registrarte primero para usar nuestro asistente. Visita nuestro sitio web para crear tu cuenta."
            elif language == "pt":
                return "👋 Olá! Você precisa se registrar primeiro para usar nosso assistente. Visite nosso site para criar sua conta."
            elif language == "fr":
                return "👋 Salut! Vous devez vous inscrire d'abord pour utiliser notre assistant. Visitez notre site web pour créer votre compte."
            else:
                return "👋 Hi! You need to register first to use our assistant. Please visit our website to create your account."

    async def _intelligent_routing(self, message: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to intelligently determine user intent and route to appropriate agent
        """
        
        routing_prompt = f"""You are an intelligent message router for a personal assistant. Analyze the user's message and determine their intent.

USER CONTEXT:
- Language: {user_context["language"]}
- Is New User: {user_context["is_new_user"]}

MESSAGE TO ANALYZE: "{message}"

AVAILABLE INTENTS:
1. "expense" - Recording or tracking money spent (contains amount and description)
2. "reminder" - Setting reminders, scheduling, or time-based tasks
3. "expense_summary" - Asking for expense reports, spending summaries, financial overview
4. "reminder_summary" - Asking for reminder lists, task summaries
5. "due_reminders" - Asking what's due today/soon
6. "general_summary" - Asking for overall/combined summary
7. "general_conversation" - Greetings, help requests, general questions

RESPONSE FORMAT (JSON only):
{{
    "success": true/false,
    "intent": "detected_intent",
    "confidence": 0.0_to_1.0,
    "reasoning": "why_this_intent_was_chosen",
    "extracted_info": {{}},
    "error": "error_if_failed"
}}

INTENT DETECTION EXAMPLES:
- "Coffee $4.50" → expense (amount and item mentioned)
- "Spent 20 euros on lunch" → expense (spending action with amount)
- "Remind me to call mom tomorrow" → reminder (time-based task)
- "Don't forget dinner at 7pm" → reminder (scheduled event)
- "Show my expenses" → expense_summary (requesting expense data)
- "What did I spend this month?" → expense_summary (expense inquiry)
- "What reminders do I have?" → reminder_summary (reminder inquiry)
- "What's due today?" → due_reminders (asking about due items)
- "Show me my summary" → general_summary (overall request)
- "Hello" → general_conversation (greeting)
- "Help me" → general_conversation (assistance request)

MULTI-LANGUAGE EXAMPLES:
- "Café €4.50" → expense
- "Recuérdame llamar a mamá" → reminder  
- "Mostrar mis gastos" → expense_summary
- "Comprei pão R$ 3" → expense
- "Lembrar reunião amanhã" → reminder

Be intelligent about context and language. Prioritize expense/reminder intents when amounts or time expressions are present."""

        try:
            response = await self.router_llm.ainvoke([
                SystemMessage(content=routing_prompt),
                HumanMessage(content="Analyze and route this message")
            ])
            
            # Extract JSON from response
            json_text = self._extract_json_from_response(response.content)
            if not json_text:
                return {
                    "success": False,
                    "error": "Could not parse routing response"
                }
            
            routing_result = json.loads(json_text)
            
            # Validate intent
            valid_intents = [
                "expense", "reminder", "expense_summary", "reminder_summary", 
                "due_reminders", "general_summary", "general_conversation"
            ]
            
            if routing_result.get("intent") not in valid_intents:
                routing_result["intent"] = "general_conversation"
                routing_result["confidence"] = 0.3
            
            return routing_result
            
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid routing response format: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Routing failed: {str(e)}"
            }
    
    async def _handle_general_summary(self, platform_type: str, platform_user_id: str, user_context: Dict[str, Any]) -> str:
        """Handle requests for general/combined summaries"""
        
        if user_context["is_new_user"]:
            return await self._generate_new_user_welcome(user_context)
        
        try:
            # Get both expense and reminder summaries
            expense_summary = await self.expense_agent.get_expense_summary(platform_type, platform_user_id, days=30)
            reminder_summary = await self.reminder_agent.get_user_reminders_summary(platform_type, platform_user_id)
            
            # Generate combined intelligent summary
            combined_prompt = f"""Generate a combined summary report for expenses and reminders.

USER CONTEXT:
- Language: {user_context["language"]}

EXPENSE SUMMARY: {expense_summary}
REMINDER SUMMARY: {reminder_summary}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Combine both summaries intelligently
3. Highlight key insights and priorities
4. Be concise but comprehensive
5. Use emojis for visual appeal

EXAMPLES:
- English: "📊 **Summary** | 💰 Expenses: $234.50 (15 items) | 📋 Reminders: 5 pending, 2 due today"
- Spanish: "📊 **Resumen** | 💰 Gastos: €234.50 (15 elementos) | 📋 Recordatorios: 5 pendientes, 2 para hoy"

Respond with just the combined summary."""

            response = await self.router_llm.ainvoke([
                SystemMessage(content=combined_prompt),
                HumanMessage(content="Generate combined summary")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            return f"📊 Summary: {expense_summary}\n📋 Reminders: {reminder_summary}"
    
    async def _handle_general_conversation(self, message: str, user_context: Dict[str, Any], routing_result: Dict[str, Any]) -> str:
        """Handle general conversation, help requests, greetings"""
        
        conversation_prompt = f"""You are a helpful personal assistant. Respond to the user's general message appropriately.

USER CONTEXT:
- Language: {user_context["language"]}
- Is New User: {user_context["is_new_user"]}

USER MESSAGE: "{message}"
ROUTING INFO: {routing_result.get("reasoning", "")}

CAPABILITIES:
- Track expenses: "Coffee $4.50", "Lunch €12"
- Set reminders: "Remind me to call mom tomorrow", "Meeting at 3pm"
- Show summaries: "Show my expenses", "What reminders do I have?"

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Be helpful and friendly
3. For greetings, welcome and explain capabilities
4. For help requests, give examples
5. For unclear messages, suggest what they can do
6. Keep responses concise but informative

EXAMPLES:
- English: "👋 Hi! I can help you track expenses and set reminders. Try 'Coffee $4.50' or 'Remind me to call mom tomorrow'."
- Spanish: "👋 ¡Hola! Puedo ayudarte a rastrear gastos y crear recordatorios. Prueba 'Café €4.50' o 'Recuérdame llamar a mamá mañana'."
- Portuguese: "👋 Olá! Posso ajudar a rastrear despesas e criar lembretes. Tente 'Café R$ 4.50' ou 'Lembrar de ligar para mamãe amanhã'."

Respond with just the helpful message."""

        try:
            response = await self.router_llm.ainvoke([
                SystemMessage(content=conversation_prompt),
                HumanMessage(content="Generate helpful response")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            # Fallback responses based on language
            currency_symbol = self._get_currency_symbol(user_context["currency"])
            
            if user_context["language"] == "es":
                return f"👋 ¡Hola! Puedo ayudarte a rastrear gastos y crear recordatorios. Prueba 'Café {currency_symbol}4.50' o 'Recuérdame llamar a mamá mañana'."
            elif user_context["language"] == "pt":
                return f"👋 Olá! Posso ajudar a rastrear despesas e criar lembretes. Tente 'Café {currency_symbol}4.50' ou 'Lembrar de ligar para mamãe amanhã'."
            elif user_context["language"] == "fr":
                return f"👋 Salut! Je peux vous aider à suivre les dépenses et créer des rappels. Essayez 'Café {currency_symbol}4.50' ou 'Rappelle-moi d'appeler maman demain'."
            else:
                return f"👋 Hi! I can help you track expenses and set reminders. Try 'Coffee {currency_symbol}4.50' or 'Remind me to call mom tomorrow'."
    
    async def _handle_routing_error(self, message: str, error: str, user_context: Dict[str, Any]) -> str:
        """Handle routing errors gracefully"""
        
        error_prompt = f"""Generate a helpful response when message routing fails.

USER CONTEXT:
- Language: {user_context["language"]}

ORIGINAL MESSAGE: "{message}"
ERROR: {error}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Apologize briefly
3. Give examples of what they can do
4. Be encouraging

EXAMPLES:
- English: "I'm not sure what you need. Try 'Coffee $4.50' for expenses or 'Remind me to call mom' for reminders."
- Spanish: "No estoy seguro de lo que necesitas. Prueba 'Café €4.50' para gastos o 'Recuérdame llamar a mamá' para recordatorios."

Respond with just the helpful message."""

        try:
            response = await self.router_llm.ainvoke([
                SystemMessage(content=error_prompt),
                HumanMessage(content="Generate routing error response")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            return "I'm not sure what you need. Try 'Coffee $4.50' for expenses or 'Remind me to call mom' for reminders."
    
    async def _generate_new_user_welcome(self, user_context: Dict[str, Any]) -> str:
        """Generate welcome message for new users asking for summary"""
        
        welcome_prompt = f"""Generate a welcome message for a new user asking for a summary.

USER CONTEXT:
- Language: {user_context["language"]}
- Currency: {user_context["currency"]}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Welcome them warmly
3. Explain they don't have data yet
4. Give examples of how to get started
5. Be encouraging

EXAMPLES:
- English: "👋 Welcome! You don't have any expenses or reminders yet. Try 'Coffee $4.50' or 'Remind me to call mom tomorrow' to get started!"
- Spanish: "👋 ¡Bienvenido! Aún no tienes gastos o recordatorios. Prueba 'Café €4.50' o 'Recuérdame llamar a mamá mañana' para empezar!"

Respond with just the welcome message."""

        try:
            response = await self.router_llm.ainvoke([
                SystemMessage(content=welcome_prompt),
                HumanMessage(content="Generate new user welcome")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            currency_symbol = self._get_currency_symbol(user_context["currency"])
            return f"👋 Welcome! You don't have any expenses or reminders yet. Try 'Coffee {currency_symbol}4.50' or 'Remind me to call mom tomorrow' to get started!"
    
    async def _generate_error_response(self, error: str, user_context: Dict[str, Any]) -> str:
        """Generate error response in user's language"""
        
        language = user_context.get("language", "en")
        
        if language == "es":
            return "❌ Lo siento, hubo un error procesando tu mensaje. Inténtalo de nuevo."
        elif language == "pt":
            return "❌ Desculpe, houve um erro processando sua mensagem. Tente novamente."
        else:
            return "❌ Sorry, there was an error processing your message. Please try again."
    
    # Utility methods
    def _extract_json_from_response(self, response_text: str) -> Optional[str]:
        """Extract JSON from LLM response"""
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        return json_match.group() if json_match else None
    
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
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get processing metrics for monitoring"""
        total = self.metrics["total_processed"]
        if total == 0:
            return self.metrics
        
        return {
            **self.metrics,
            "expense_rate": self.metrics["expense_requests"] / total,
            "reminder_rate": self.metrics["reminder_requests"] / total,
            "summary_rate": self.metrics["summary_requests"] / total,
            "general_rate": self.metrics["general_queries"] / total,
            "error_rate": self.metrics["routing_errors"] / total
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the orchestrator"""
        try:
            # Test database connection
            db_ok = await self._test_database_connection()
            
            # Test LLM connection
            llm_ok = await self._test_llm_connection()
            
            return {
                "status": "healthy" if db_ok and llm_ok else "unhealthy",
                "database": "ok" if db_ok else "error",
                "llm": "ok" if llm_ok else "error",
                "metrics": self.get_metrics(),
                "timestamp": str(datetime.now())
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": str(datetime.now())
            }
    
    async def _test_database_connection(self) -> bool:
        """Test database connectivity"""
        try:
            if self.database.pool:
                async with self.database.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                return True
            return False
        except Exception:
            return False
    
    async def _test_llm_connection(self) -> bool:
        """Test LLM connectivity"""
        try:
            response = await self.router_llm.ainvoke([
                HumanMessage(content="Test")
            ])
            return bool(response.content)
        except Exception:
            return False