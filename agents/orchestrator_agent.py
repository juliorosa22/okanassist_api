# agents/orchestrator_agent.py
from typing import Dict, Optional, Any
from datetime import datetime
import json

from .base_intelligent_agent import BaseIntelligentAgent
from .expense_agent import ExpenseAgent
from .reminder_agent import ReminderAgent

class OrchestratorAgent(BaseIntelligentAgent):
    """
    OrchestratorAgent using BaseIntelligentAgent with LLM providers for:
    1. Intelligent intent detection and message routing
    2. Parse user intent (expense, reminder, summary, general)
    3. User registration checking and assistance
    4. App capabilities and information promotion
    5. Multi-language support (English, Spanish, Portuguese)
    """
    
    def __init__(self, llm_config: Dict[str, Any], database):
        """
        Initialize orchestrator with specialized agents
        
        Args:
            llm_config: LLM configuration for BaseIntelligentAgent
            database: Database instance
        """
        super().__init__(llm_config, database)
        
        # Initialize specialized agents with same LLM config
        self.expense_agent = ExpenseAgent(llm_config, database)
        self.reminder_agent = ReminderAgent(llm_config, database)
        
        # Track processing metrics
        self.metrics = {
            "total_processed": 0,
            "expense_requests": 0,
            "reminder_requests": 0,
            "summary_requests": 0,
            "general_queries": 0,
            "registration_prompts": 0,
            "routing_errors": 0
        }
        
        # App information
        self.app_info = {
            "name": "Okan Personal Assistant",
            "description": "Your intelligent assistant for expense tracking and reminders",
            "features": [
                "Smart expense tracking with multi-currency support",
                "Intelligent reminder system with notifications",
                "Multi-language support (English, Spanish, Portuguese)",
                "Natural language processing for easy interaction"
            ],
            "website_url": "https://okan-assistant.com",  # Placeholder
            "app_download": {
                "ios": "https://apps.apple.com/okan-assistant",  # Placeholder
                "android": "https://play.google.com/okan-assistant"  # Placeholder
            }
        }
    
    async def process_message(self, message: str, platform_type: str, platform_user_id: str) -> str:
        """
        Main orchestrator entry point - intelligently route messages
        
        Args:
            message: User's natural language message
            platform_type: Platform origin (telegram, whatsapp, mobile_app, web_app)
            platform_user_id: Platform-specific user identifier
            
        Returns:
            Intelligent response in user's language
        """
        
        self.metrics["total_processed"] += 1
        
        # Validate inputs using base class
        validation = self.validate_input(message, platform_type, platform_user_id)
        if not validation["valid"]:
            return f"❌ {'; '.join(validation['errors'])}"
        
        # Get user context with caching
        user_context = await self.get_user_context(platform_type, platform_user_id)
        
        # Check if user is registered - if not, handle registration
        if user_context["is_new_user"]:
            self.metrics["registration_prompts"] += 1
            return await self._handle_unregistered_user(message, user_context, platform_type)
        
        # User is registered - detect intent and route to appropriate agent
        intent_result = await self._detect_user_intent(message, user_context)
        
        if not intent_result["success"]:
            self.metrics["routing_errors"] += 1
            return await self._generate_error_response(intent_result, user_context)
        
        # Route to appropriate handler based on intent
        return await self._route_to_handler(intent_result, message, platform_type, platform_user_id, user_context)
    
    # ============================================================================
    # INTELLIGENT INTENT DETECTION
    # ============================================================================
    
    async def _detect_user_intent(self, message: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to intelligently detect user intent
        
        Args:
            message: User's message
            user_context: User context for personalized detection
            
        Returns:
            Intent detection result: {success, intent, confidence, details}
        """
        
        # Build intelligent intent detection prompt
        system_prompt = self._build_intent_detection_prompt(user_context)
        
        # Use safe LLM call from base class
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate help examples"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback help examples
        if language == "es":
            return "💡 **Ayuda - Okan Personal Assistant:**\\n\\n💰 Gastos: 'Café €4.50'\\n⏰ Recordatorios: 'Recuérdame llamar a mamá'\\n📊 Resúmenes: 'Muestra mis gastos'"
        elif language == "pt":
            return "💡 **Ajuda - Okan Personal Assistant:**\\n\\n💰 Despesas: 'Café R$ 4.50'\\n⏰ Lembretes: 'Lembre-me de ligar'\\n📊 Resumos: 'Mostre minhas despesas'"
        else:
            return "💡 **Help - Okan Personal Assistant:**\\n\\n💰 Expenses: 'Coffee $4.50'\\n⏰ Reminders: 'Remind me to call mom'\\n📊 Summaries: 'Show my expenses'"
    
    async def _handle_greeting(self, language: str, user_context: Dict[str, Any]) -> str:
        """Handle greeting messages with warm welcome"""
        
        user_name = user_context.get("user", {}).get("first_name", "")
        name_part = f" {user_name}" if user_name else ""
        
        system_prompt = f"""Generate a warm greeting response for "Okan Personal Assistant" in {language}.

USER INFO:
- Name: {name_part}
- Language: {language}

INSTRUCTIONS:
1. Respond in {language} language
2. Be warm and welcoming
3. Include the app name "Okan Personal Assistant"
4. Briefly mention main capabilities
5. Invite them to try features
6. Use appropriate emojis

EXAMPLES:
- English: "👋 Hello{name_part}! Welcome to Okan Personal Assistant! I'm here to help you track expenses and manage reminders. Try saying 'Coffee $4.50' or 'Remind me to call mom tomorrow'!"
- Spanish: "👋 ¡Hola{name_part}! ¡Bienvenido a Okan Personal Assistant! Estoy aquí para ayudarte con gastos y recordatorios. Prueba diciendo 'Café €4.50' o 'Recuérdame llamar a mamá mañana'!"
- Portuguese: "👋 Olá{name_part}! Bem-vindo ao Okan Personal Assistant! Estou aqui para ajudar com despesas e lembretes. Tente dizer 'Café R$ 4.50' ou 'Lembre-me de ligar para mamãe amanhã'!"

Respond with just the greeting message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate greeting response"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback greetings
        if language == "es":
            return f"👋 ¡Hola{name_part}! Bienvenido a Okan Personal Assistant. ¿Cómo puedo ayudarte hoy?"
        elif language == "pt":
            return f"👋 Olá{name_part}! Bem-vindo ao Okan Personal Assistant. Como posso ajudar hoje?"
        else:
            return f"👋 Hello{name_part}! Welcome to Okan Personal Assistant. How can I help you today?"
    
    async def _handle_general_conversation(self, message: str, language: str, intent_result: Dict[str, Any]) -> str:
        """Handle general conversation that's not app-specific"""
        
        system_prompt = f"""Generate a polite response for general conversation in {language} that redirects to app features.

USER MESSAGE: "{message}"
INTENT ANALYSIS: {intent_result.get('reasoning', 'General conversation')}

APP NAME: Okan Personal Assistant
MAIN FEATURES: Expense tracking, Reminder system

INSTRUCTIONS:
1. Respond in {language} language
2. Be polite about not handling general topics
3. Gently redirect to app capabilities
4. Suggest specific examples they can try
5. Be helpful and encouraging

EXAMPLES:
- English: "I'm Okan Personal Assistant, specialized in helping with expenses and reminders. While I can't help with general topics, I'd love to help you track expenses like 'Coffee $4.50' or set reminders like 'Call mom tomorrow'!"
- Spanish: "Soy Okan Personal Assistant, especializado en gastos y recordatorios. Aunque no puedo ayudar con temas generales, me encantaría ayudarte a rastrear gastos como 'Café €4.50' o crear recordatorios como 'Llamar a mamá mañana'!"
- Portuguese: "Sou o Okan Personal Assistant, especializado em despesas e lembretes. Embora eu não possa ajudar com tópicos gerais, adoraria ajudar você a rastrear despesas como 'Café R$ 4.50' ou criar lembretes como 'Ligar para mamãe amanhã'!"

Respond with just the redirection message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate polite redirection"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback redirection
        if language == "es":
            return "Soy Okan Personal Assistant, especializado en gastos y recordatorios. ¿Puedo ayudarte con alguna de estas funciones?"
        elif language == "pt":
            return "Sou o Okan Personal Assistant, especializado em despesas e lembretes. Posso ajudar você com alguma dessas funções?"
        else:
            return "I'm Okan Personal Assistant, specialized in expenses and reminders. Can I help you with one of these features?"
    
    # ============================================================================
    # ERROR HANDLING
    # ============================================================================
    
    async def _generate_error_response(self, error_data: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate error response using LLM in user's language"""
        
        language = user_context.get("language", "en")
        error_message = error_data.get("error", "Unknown error")
        
        system_prompt = f"""Generate a helpful error message for "Okan Personal Assistant" in {language}.

ERROR: {error_message}

INSTRUCTIONS:
1. Respond in {language} language
2. Be apologetic but helpful
3. Suggest trying again or using help
4. Include ❌ emoji
5. Offer specific examples

EXAMPLES:
- English: "❌ I encountered an issue processing your request. Please try again or type 'help' for usage examples!"
- Spanish: "❌ Tuve un problema procesando tu solicitud. ¡Inténtalo de nuevo o escribe 'ayuda' para ver ejemplos!"
- Portuguese: "❌ Tive um problema processando sua solicitação. Tente novamente ou digite 'ajuda' para ver exemplos!"

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
            return "❌ Hubo un error. Inténtalo de nuevo o escribe 'ayuda'."
        elif language == "pt":
            return "❌ Houve um erro. Tente novamente ou digite 'ajuda'."
        else:
            return "❌ There was an error. Please try again or type 'help'."
    
    # ============================================================================
    # METRICS AND MONITORING
    # ============================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestrator processing metrics"""
        total = self.metrics["total_processed"]
        if total == 0:
            return self.metrics
        
        return {
            **self.metrics,
            "expense_rate": self.metrics["expense_requests"] / total,
            "reminder_rate": self.metrics["reminder_requests"] / total,
            "summary_rate": self.metrics["summary_requests"] / total,
            "general_rate": self.metrics["general_queries"] / total,
            "registration_rate": self.metrics["registration_prompts"] / total,
            "error_rate": self.metrics["routing_errors"] / total
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the orchestrator and all agents"""
        try:
            # Test orchestrator LLM
            orchestrator_llm_ok = await self.llm_health_check()
            
            # Test database connection
            db_ok = await self._test_database_connection()
            
            # Test sub-agents
            expense_agent_ok = await self.expense_agent.llm_health_check()
            reminder_agent_ok = await self.reminder_agent.llm_health_check()
            
            overall_status = "healthy" if all([orchestrator_llm_ok, db_ok, expense_agent_ok, reminder_agent_ok]) else "unhealthy"
            
            return {
                "status": overall_status,
                "orchestrator_llm": "ok" if orchestrator_llm_ok else "error",
                "database": "ok" if db_ok else "error",
                "expense_agent": "ok" if expense_agent_ok else "error",
                "reminder_agent": "ok" if reminder_agent_ok else "error",
                "metrics": self.get_metrics(),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _test_database_connection(self) -> bool:
        """Test database connectivity"""
        try:
            if self.database and self.database.pool:
                async with self.database.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                return True
            return False
        except Exception:
            return False
    
    # ============================================================================
    # REQUIRED ABSTRACT METHODS FROM BASE CLASS
    # ============================================================================
    
    async def get_user_patterns(self, user_id: str) -> Dict[str, Any]:
        """
        Get user patterns from both expense and reminder agents
        """
        try:
            expense_patterns = await self.expense_agent.get_user_patterns(user_id)
            reminder_patterns = await self.reminder_agent.get_user_patterns(user_id)
            
            return {
                "expense_patterns": expense_patterns,
                "reminder_patterns": reminder_patterns
            }
        except Exception:
            return {}
    
    def _get_response_template(self, template_key: str, context: Dict[str, Any], language: str) -> str:
        """
        Get response template (not used in this implementation since we use LLM directly)
        Required by base class but not used here
        """
        return ""
            {"role": "user", "content": f"Analyze this message intent: {message}"}
        ]
        
        response_content = await self.safe_llm_call(messages, max_retries=3, cache=True)
        
        if not response_content:
            return {
                "success": False,
                "error": "Intent detection service temporarily unavailable"
            }
        
        try:
            # Extract JSON from LLM response
            json_text = self.extract_json_from_response(response_content)
            if not json_text:
                return {
                    "success": False,
                    "error": "Could not understand message intent"
                }
            
            intent_data = json.loads(json_text)
            
            # Validate the intent result
            return self._validate_intent_detection(intent_data, user_context)
            
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Invalid intent detection response"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Intent detection failed: {str(e)}"
            }
    
    def _build_intent_detection_prompt(self, user_context: Dict[str, Any]) -> str:
        """Build intelligent intent detection prompt for LLM"""
        
        return f"""You are an intelligent intent detection system for "Okan Personal Assistant" - an expense tracking and reminder app.

USER CONTEXT:
- Language: {user_context["language"]}
- Platform: {user_context.get("platform", {}).get("platform_type", "unknown")}

APP CAPABILITIES:
- Expense tracking with multi-currency support (USD $, EUR €, BRL R$)
- Reminder system with smart scheduling
- Expense and reminder summaries
- Multi-language support (English, Spanish, Portuguese)

TASK:
Analyze the user's message and detect their intent. Be intelligent about:
1. Expense recording intents (contains amounts and descriptions)
2. Reminder creation intents (contains time expressions and tasks)
3. Summary requests (asking for reports or overviews)
4. General conversation (greetings, help, app info requests)
5. Language detection from the message

AVAILABLE INTENTS:
- "expense" - Recording money spent (contains amount + description)
- "reminder" - Setting reminders or tasks (contains time + action)
- "expense_summary" - Requesting expense reports/summaries
- "reminder_summary" - Requesting reminder lists/summaries
- "general_summary" - Requesting combined overview
- "app_info" - Asking about app features/capabilities
- "help" - Requesting help or guidance
- "greeting" - Hello, hi, good morning, etc.
- "general" - General conversation not handled by app

RESPONSE FORMAT (JSON only):
{{
    "success": true/false,
    "intent": "detected_intent",
    "confidence": 0.0_to_1.0,
    "detected_language": "en|es|pt",
    "details": {{
        "has_amount": true/false,
        "has_time_expression": true/false,
        "has_summary_request": true/false,
        "keywords_found": ["list", "of", "relevant", "keywords"]
    }},
    "reasoning": "why_this_intent_was_chosen",
    "error": "error_message_if_failed"
}}

INTENT DETECTION EXAMPLES:

EXPENSE EXAMPLES:
- "Coffee $4.50" → {{"success": true, "intent": "expense", "confidence": 0.95, "detected_language": "en", "details": {{"has_amount": true}}}}
- "Café €5.00" → {{"success": true, "intent": "expense", "confidence": 0.95, "detected_language": "es", "details": {{"has_amount": true}}}}
- "Gasolina R$ 50" → {{"success": true, "intent": "expense", "confidence": 0.95, "detected_language": "pt", "details": {{"has_amount": true}}}}
- "Spent 20 dollars on lunch" → {{"success": true, "intent": "expense", "confidence": 0.9, "detected_language": "en", "details": {{"has_amount": true}}}}
- "Compré pan por 3 euros" → {{"success": true, "intent": "expense", "confidence": 0.9, "detected_language": "es", "details": {{"has_amount": true}}}}

REMINDER EXAMPLES:
- "Remind me to call mom tomorrow at 3pm" → {{"success": true, "intent": "reminder", "confidence": 0.95, "detected_language": "en", "details": {{"has_time_expression": true}}}}
- "Recuérdame llamar a mamá mañana" → {{"success": true, "intent": "reminder", "confidence": 0.9, "detected_language": "es", "details": {{"has_time_expression": true}}}}
- "Lembre-me da reunião na sexta" → {{"success": true, "intent": "reminder", "confidence": 0.9, "detected_language": "pt", "details": {{"has_time_expression": true}}}}
- "Don't forget dinner at 7pm" → {{"success": true, "intent": "reminder", "confidence": 0.85, "detected_language": "en", "details": {{"has_time_expression": true}}}}

SUMMARY EXAMPLES:
- "Show my expenses" → {{"success": true, "intent": "expense_summary", "confidence": 0.95, "detected_language": "en", "details": {{"has_summary_request": true}}}}
- "What reminders do I have?" → {{"success": true, "intent": "reminder_summary", "confidence": 0.95, "detected_language": "en", "details": {{"has_summary_request": true}}}}
- "Show me my summary" → {{"success": true, "intent": "general_summary", "confidence": 0.9, "detected_language": "en", "details": {{"has_summary_request": true}}}}
- "Muestra mis gastos" → {{"success": true, "intent": "expense_summary", "confidence": 0.95, "detected_language": "es", "details": {{"has_summary_request": true}}}}
- "Quais lembretes eu tenho?" → {{"success": true, "intent": "reminder_summary", "confidence": 0.95, "detected_language": "pt", "details": {{"has_summary_request": true}}}}

APP INFO EXAMPLES:
- "What can you do?" → {{"success": true, "intent": "app_info", "confidence": 0.9, "detected_language": "en"}}
- "Tell me about this app" → {{"success": true, "intent": "app_info", "confidence": 0.9, "detected_language": "en"}}
- "¿Qué puedes hacer?" → {{"success": true, "intent": "app_info", "confidence": 0.9, "detected_language": "es"}}
- "O que este app pode fazer?" → {{"success": true, "intent": "app_info", "confidence": 0.9, "detected_language": "pt"}}

HELP EXAMPLES:
- "Help" → {{"success": true, "intent": "help", "confidence": 0.95, "detected_language": "en"}}
- "How do I use this?" → {{"success": true, "intent": "help", "confidence": 0.9, "detected_language": "en"}}
- "Ayuda" → {{"success": true, "intent": "help", "confidence": 0.95, "detected_language": "es"}}
- "Como usar?" → {{"success": true, "intent": "help", "confidence": 0.9, "detected_language": "pt"}}

GREETING EXAMPLES:
- "Hello" → {{"success": true, "intent": "greeting", "confidence": 0.95, "detected_language": "en"}}
- "Hi there" → {{"success": true, "intent": "greeting", "confidence": 0.9, "detected_language": "en"}}
- "Hola" → {{"success": true, "intent": "greeting", "confidence": 0.95, "detected_language": "es"}}
- "Olá" → {{"success": true, "intent": "greeting", "confidence": 0.95, "detected_language": "pt"}}

GENERAL EXAMPLES:
- "How's the weather?" → {{"success": true, "intent": "general", "confidence": 0.8, "detected_language": "en"}}
- "Tell me a joke" → {{"success": true, "intent": "general", "confidence": 0.8, "detected_language": "en"}}

LANGUAGE DETECTION RULES:
- Spanish keywords: "café", "compré", "pagué", "recuérdame", "gastos", "recordatorios", "ayuda", "hola"
- Portuguese keywords: "café", "comprei", "paguei", "lembre-me", "despesas", "lembretes", "ajuda", "olá"
- English: default if no clear Spanish/Portuguese indicators

PRIORITIZATION:
1. Expense intent: If amount/currency found → expense (high confidence)
2. Reminder intent: If time expression + action → reminder (high confidence)
3. Summary intent: If asking for reports/lists → appropriate summary
4. App/Help intent: If asking about capabilities → app_info or help
5. Greeting intent: If greeting words → greeting
6. General intent: Everything else not handled by app

Be very confident (0.9+) when clear indicators are present (amounts, time expressions, summary requests).
Use medium confidence (0.7-0.8) for ambiguous cases.
If truly unclear, set success=false with clear error message."""
    
    def _validate_intent_detection(self, intent_data: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and enhance the intent detection result
        
        Args:
            intent_data: Raw intent detection from LLM
            user_context: User context for validation
            
        Returns:
            Validated intent result
        """
        if not intent_data.get("success"):
            return intent_data
        
        # Validate intent
        valid_intents = [
            "expense", "reminder", "expense_summary", "reminder_summary", 
            "general_summary", "app_info", "help", "greeting", "general"
        ]
        
        if intent_data.get("intent") not in valid_intents:
            intent_data["intent"] = "general"
            intent_data["confidence"] = 0.3
        
        # Validate language
        valid_languages = ["en", "es", "pt"]
        if intent_data.get("detected_language") not in valid_languages:
            intent_data["detected_language"] = user_context["language"]
        
        # Ensure confidence is between 0 and 1
        intent_data["confidence"] = max(0.0, min(1.0, intent_data.get("confidence", 0.5)))
        
        # Ensure details exist
        if "details" not in intent_data:
            intent_data["details"] = {}
        
        return intent_data
    
    # ============================================================================
    # MESSAGE ROUTING
    # ============================================================================
    
    async def _route_to_handler(self, intent_result: Dict[str, Any], message: str, 
                               platform_type: str, platform_user_id: str, user_context: Dict[str, Any]) -> str:
        """
        Route message to appropriate handler based on detected intent
        
        Args:
            intent_result: Intent detection result
            message: Original message
            platform_type: Platform type
            platform_user_id: Platform user ID
            user_context: User context
            
        Returns:
            Response from appropriate handler
        """
        
        intent = intent_result["intent"]
        confidence = intent_result["confidence"]
        language = intent_result.get("detected_language", user_context["language"])
        
        print(f"🎯 ROUTING: {intent} (confidence: {confidence:.2f}) | Language: {language} | Platform: {platform_type}")
        
        try:
            if intent == "expense":
                self.metrics["expense_requests"] += 1
                return await self.expense_agent.process_message(message, platform_type, platform_user_id)
            
            elif intent == "reminder":
                self.metrics["reminder_requests"] += 1
                return await self.reminder_agent.process_message(message, platform_type, platform_user_id)
            
            elif intent == "expense_summary":
                self.metrics["summary_requests"] += 1
                return await self.expense_agent.get_expense_summary(platform_type, platform_user_id)
            
            elif intent == "reminder_summary":
                self.metrics["summary_requests"] += 1
                return await self.reminder_agent.get_user_reminders_summary(platform_type, platform_user_id)
            
            elif intent == "general_summary":
                self.metrics["summary_requests"] += 1
                return await self._handle_general_summary(platform_type, platform_user_id, user_context)
            
            elif intent == "app_info":
                self.metrics["general_queries"] += 1
                return await self._handle_app_info_request(language, platform_type)
            
            elif intent == "help":
                self.metrics["general_queries"] += 1
                return await self._handle_help_request(language, platform_type)
            
            elif intent == "greeting":
                self.metrics["general_queries"] += 1
                return await self._handle_greeting(language, user_context)
            
            else:  # general
                self.metrics["general_queries"] += 1
                return await self._handle_general_conversation(message, language, intent_result)
        
        except Exception as e:
            print(f"❌ Routing error: {e}")
            return await self._generate_error_response(
                {"error": f"Handler error: {str(e)}"}, 
                user_context
            )
    
    # ============================================================================
    # UNREGISTERED USER HANDLING
    # ============================================================================
    
    async def _handle_unregistered_user(self, message: str, user_context: Dict[str, Any], platform_type: str) -> str:
        """
        Handle messages from unregistered users with registration assistance
        
        Args:
            message: User's message
            user_context: User context
            platform_type: Platform type
            
        Returns:
            Registration assistance message
        """
        
        language = user_context.get("language", "en")
        
        # Detect if user is asking about the app or just trying to use it
        if any(word in message.lower() for word in ["what", "info", "help", "qué", "info", "ajuda", "o que"]):
            # User is asking for information - provide app info + registration
            return await self._generate_app_info_with_registration(language, platform_type)
        else:
            # User is trying to use features - guide them to register
            return await self._generate_registration_guidance(language, platform_type, message)
    
    async def _generate_registration_guidance(self, language: str, platform_type: str, original_message: str) -> str:
        """Generate registration guidance message using LLM"""
        
        system_prompt = f"""Generate a helpful registration guidance message for "Okan Personal Assistant" in {language}.

APP INFO:
- Name: Okan Personal Assistant
- Features: Expense tracking, Reminder system, Multi-language support
- Platform: {platform_type}

USER SITUATION:
- User tried to use app features but is not registered
- Original message: "{original_message}"

INSTRUCTIONS:
1. Respond in {language} language
2. Welcome them warmly to Okan Personal Assistant
3. Explain they need to register first
4. Mention the app's main features (expense tracking & reminders)
5. Guide them to register on website or download app
6. Be encouraging and helpful
7. Use appropriate emojis

EXAMPLES:
- English: "👋 Welcome to Okan Personal Assistant! I'd love to help you track expenses and set reminders, but you'll need to register first. Visit our website at okan-assistant.com or download our app to get started!"
- Spanish: "👋 ¡Bienvenido a Okan Personal Assistant! Me encantaría ayudarte con gastos y recordatorios, pero primero necesitas registrarte. Visita nuestro sitio web en okan-assistant.com o descarga nuestra app para comenzar!"
- Portuguese: "👋 Bem-vindo ao Okan Personal Assistant! Adoraria ajudar você com despesas e lembretes, mas primeiro você precisa se registrar. Visite nosso site em okan-assistant.com ou baixe nosso app para começar!"

Respond with just the guidance message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate registration guidance"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback registration guidance
        if language == "es":
            return "👋 ¡Bienvenido a Okan Personal Assistant! Necesitas registrarte primero. Visita okan-assistant.com para comenzar."
        elif language == "pt":
            return "👋 Bem-vindo ao Okan Personal Assistant! Você precisa se registrar primeiro. Visite okan-assistant.com para começar."
        else:
            return "👋 Welcome to Okan Personal Assistant! You need to register first. Visit okan-assistant.com to get started."
    
    async def _generate_app_info_with_registration(self, language: str, platform_type: str) -> str:
        """Generate app information with registration call-to-action"""
        
        system_prompt = f"""Generate an informative message about "Okan Personal Assistant" with registration guidance in {language}.

APP INFORMATION:
- Name: Okan Personal Assistant
- Main Features:
  * Smart expense tracking with multi-currency support (USD, EUR, BRL)
  * Intelligent reminder system with notifications
  * Multi-language support (English, Spanish, Portuguese)
  * Natural language processing for easy interaction
- Platform: {platform_type}
- Website: okan-assistant.com

INSTRUCTIONS:
1. Respond in {language} language
2. Introduce Okan Personal Assistant enthusiastically
3. List the main features clearly
4. Explain the benefits
5. Include clear registration call-to-action
6. Use emojis for visual appeal

EXAMPLES:
- English: "🌟 Okan Personal Assistant is your intelligent companion for managing expenses and reminders! \\n\\n📊 Features:\\n• Smart expense tracking (USD, EUR, BRL)\\n• Intelligent reminders with notifications\\n• Multi-language support\\n• Natural language interaction\\n\\n🚀 Register at okan-assistant.com to start managing your finances and tasks effortlessly!"
- Spanish: "🌟 ¡Okan Personal Assistant es tu compañero inteligente para gestionar gastos y recordatorios!\\n\\n📊 Características:\\n• Seguimiento inteligente de gastos (USD, EUR, BRL)\\n• Recordatorios inteligentes con notificaciones\\n• Soporte multiidioma\\n• Interacción en lenguaje natural\\n\\n🚀 ¡Regístrate en okan-assistant.com para comenzar a gestionar tus finanzas y tareas sin esfuerzo!"

Respond with just the informative message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate app info with registration"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback app info
        features = "• Smart expense tracking\\n• Intelligent reminders\\n• Multi-language support"
        
        if language == "es":
            return f"🌟 Okan Personal Assistant - tu asistente inteligente!\\n\\n📊 Características:\\n{features}\\n\\n🚀 Regístrate en okan-assistant.com"
        elif language == "pt":
            return f"🌟 Okan Personal Assistant - seu assistente inteligente!\\n\\n📊 Recursos:\\n{features}\\n\\n🚀 Registre-se em okan-assistant.com"
        else:
            return f"🌟 Okan Personal Assistant - your intelligent assistant!\\n\\n📊 Features:\\n{features}\\n\\n🚀 Register at okan-assistant.com"
    
    # ============================================================================
    # SPECIALIZED HANDLERS
    # ============================================================================
    
    async def _handle_general_summary(self, platform_type: str, platform_user_id: str, user_context: Dict[str, Any]) -> str:
        """Handle requests for combined expense and reminder summary"""
        
        try:
            # Get both summaries
            expense_summary = await self.expense_agent.get_expense_summary(platform_type, platform_user_id, days=30)
            reminder_summary = await self.reminder_agent.get_user_reminders_summary(platform_type, platform_user_id)
            
            # Generate combined response using LLM
            language = user_context["language"]
            
            system_prompt = f"""Generate a combined summary report for expenses and reminders in {language}.

EXPENSE SUMMARY: {expense_summary}
REMINDER SUMMARY: {reminder_summary}

INSTRUCTIONS:
1. Respond in {language} language
2. Combine both summaries intelligently
3. Use clear section headers
4. Be concise but comprehensive
5. Use emojis for visual appeal

EXAMPLES:
- English: "📊 **Your Summary**\\n\\n💰 Expenses: Last 30 days summary here\\n📋 Reminders: Current reminders status here"
- Spanish: "📊 **Tu Resumen**\\n\\n💰 Gastos: Resumen últimos 30 días aquí\\n📋 Recordatorios: Estado actual de recordatorios aquí"

Respond with just the combined summary."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Generate combined summary"}
            ]
            
            response = await self.safe_llm_call(messages, cache=True)
            
            if response:
                return response
            
            # Fallback combined summary
            return f"📊 **Summary**\\n\\n💰 {expense_summary}\\n\\n📋 {reminder_summary}"
            
        except Exception as e:
            print(f"❌ Error generating general summary: {e}")
            return await self._generate_error_response(
                {"error": "Could not generate summary"}, 
                user_context
            )
    
    async def _handle_app_info_request(self, language: str, platform_type: str) -> str:
        """Handle requests for app information and capabilities"""
        
        system_prompt = f"""Generate detailed information about "Okan Personal Assistant" capabilities in {language}.

APP INFORMATION:
- Name: Okan Personal Assistant
- Description: Intelligent assistant for expense tracking and reminders
- Features:
  * Smart expense tracking with multi-currency support (USD $, EUR €, BRL R$)
  * Intelligent reminder system with smart scheduling
  * Multi-language support (English, Spanish, Portuguese)
  * Natural language processing for easy interaction
  * Cross-platform availability (Telegram, WhatsApp, Mobile App, Web)

INSTRUCTIONS:
1. Respond in {language} language
2. Be enthusiastic about the app's capabilities
3. Provide clear examples of how to use each feature
4. Use emojis and formatting for visual appeal
5. Include example commands

EXAMPLES:
- English: "🌟 **Okan Personal Assistant** - Your intelligent companion!\\n\\n💰 **Expense Tracking:**\\n• Just say 'Coffee $4.50' to track expenses\\n• Multi-currency support: $, €, R$\\n\\n⏰ **Smart Reminders:**\\n• 'Remind me to call mom tomorrow at 3pm'\\n• Intelligent scheduling and notifications\\n\\n🌍 **Multi-language:** English, Spanish, Portuguese\\n\\n✨ Just talk naturally - I understand!"

Respond with detailed app information."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate app capabilities information"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback app info
        if language == "es":
            return "🌟 **Okan Personal Assistant**\\n\\n💰 Seguimiento de gastos: 'Café €4.50'\\n⏰ Recordatorios: 'Recuérdame llamar a mamá'\\n🌍 Multiidioma"
        elif language == "pt":
            return "🌟 **Okan Personal Assistant**\\n\\n💰 Rastreamento de despesas: 'Café R$ 4.50'\\n⏰ Lembretes: 'Lembre-me de ligar para mamãe'\\n🌍 Multi-idioma"
        else:
            return "🌟 **Okan Personal Assistant**\\n\\n💰 Expense tracking: 'Coffee $4.50'\\n⏰ Reminders: 'Remind me to call mom'\\n🌍 Multi-language"
    
    async def _handle_help_request(self, language: str, platform_type: str) -> str:
        """Handle help requests with usage examples"""
        
        system_prompt = f"""Generate helpful usage examples for "Okan Personal Assistant" in {language}.

INSTRUCTIONS:
1. Respond in {language} language
2. Provide clear examples for each main feature
3. Include tips for better interaction
4. Use emojis and clear formatting
5. Be encouraging and supportive

FEATURES TO EXPLAIN:
- Expense tracking with examples
- Reminder setting with examples
- Summary requests
- Natural language tips

EXAMPLES:
- English: "💡 **How to use Okan Personal Assistant:**\\n\\n💰 **Track Expenses:**\\n• 'Coffee $4.50'\\n• 'Lunch at restaurant €15'\\n• 'Gas for car R$ 60'\\n\\n⏰ **Set Reminders:**\\n• 'Remind me to call mom tomorrow at 3pm'\\n• 'Don't forget meeting Friday 2pm'\\n\\n📊 **Get Summaries:**\\n• 'Show my expenses'\\n• 'What reminders do I have?'\\n\\n✨ **Tip:** Just talk naturally - I understand multiple languages!"

Respond with helpful usage examples."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate usage examples for help"},
                 