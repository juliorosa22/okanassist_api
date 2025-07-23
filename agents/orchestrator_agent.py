# agents/orchestrator_agent.py
from typing import Dict, Optional, Any
from datetime import datetime
import json

from .base_intelligent_agent import BaseIntelligentAgent
from .expense_agent import ExpenseAgent
from .reminder_agent import ReminderAgent
from ..prompts.orchestrator_prompts import OrchestratorPrompts, FallbackResponses

class OrchestratorAgent(BaseIntelligentAgent):
    """
    Clean orchestrator with minimal token usage and separated prompts
    """
    
    def __init__(self, llm_config: Dict[str, Any], database):
        super().__init__(llm_config, database)
        
        # Initialize specialized agents
        self.expense_agent = ExpenseAgent(llm_config, database)
        self.reminder_agent = ReminderAgent(llm_config, database)
        
        # Compact metrics tracking
        self.metrics = {
            "total": 0, "expense": 0, "reminder": 0, "summary": 0, 
            "general": 0, "registration": 0, "errors": 0
        }
    
    async def process_message(self, message: str, platform_type: str, platform_user_id: str) -> str:
        """Main orchestrator entry point"""
        
        self.metrics["total"] += 1
        
        # Quick validation
        if not message or not message.strip():
            return FallbackResponses.get("error", "en")
        
        # Get user context
        user_context = await self.get_user_context(platform_type, platform_user_id)
        
        # Handle unregistered users
        if user_context["is_new_user"]:
            self.metrics["registration"] += 1
            return await self._handle_unregistered_user(message, user_context, platform_type)
        
        # Detect intent and route
        intent_result = await self._detect_intent(message, user_context)
        if not intent_result["success"]:
            self.metrics["errors"] += 1
            return await self._generate_llm_response(
                OrchestratorPrompts.error_response(user_context["language"], intent_result.get("error", "")),
                FallbackResponses.get("error", user_context["language"])
            )
        
        # Route to handler
        return await self._route_message(intent_result, message, platform_type, platform_user_id, user_context)
    
    async def _detect_intent(self, message: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Compact intent detection"""
        
        prompt = OrchestratorPrompts.intent_detection(user_context)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Message: {message}"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        if not response:
            return {"success": False, "error": "Service unavailable"}
        
        try:
            json_text = self.extract_json_from_response(response)
            if not json_text:
                return {"success": False, "error": "Invalid response"}
            
            intent_data = json.loads(json_text)
            return self._validate_intent(intent_data, user_context)
            
        except (json.JSONDecodeError, Exception) as e:
            return {"success": False, "error": f"Parse error: {str(e)}"}
    
    def _validate_intent(self, data: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Quick intent validation"""
        
        valid_intents = {
            "expense", "reminder", "expense_summary", "reminder_summary", 
            "general_summary", "app_info", "help", "greeting", "general"
        }
        
        if data.get("intent") not in valid_intents:
            data["intent"] = "general"
            data["confidence"] = 0.3
        
        data["confidence"] = max(0.0, min(1.0, data.get("confidence", 0.5)))
        data["detected_language"] = data.get("detected_language", user_context["language"])
        
        return data
    
    async def _route_message(self, intent_result: Dict[str, Any], message: str, 
                           platform_type: str, platform_user_id: str, user_context: Dict[str, Any]) -> str:
        """Compact message routing"""
        
        intent = intent_result["intent"]
        language = intent_result.get("detected_language", user_context["language"])
        
        try:
            # Route to appropriate handler
            if intent == "expense":
                self.metrics["expense"] += 1
                return await self.expense_agent.process_message(message, platform_type, platform_user_id)
            
            elif intent == "reminder":
                self.metrics["reminder"] += 1
                return await self.reminder_agent.process_message(message, platform_type, platform_user_id)
            
            elif intent == "expense_summary":
                self.metrics["summary"] += 1
                return await self.expense_agent.get_expense_summary(platform_type, platform_user_id)
            
            elif intent == "reminder_summary":
                self.metrics["summary"] += 1
                return await self.reminder_agent.get_user_reminders_summary(platform_type, platform_user_id)
            
            elif intent == "general_summary":
                self.metrics["summary"] += 1
                return await self._handle_general_summary(platform_type, platform_user_id, language)
            
            elif intent == "app_info":
                self.metrics["general"] += 1
                return await self._generate_llm_response(
                    OrchestratorPrompts.app_capabilities_info(language),
                    FallbackResponses.get("capabilities", language)
                )
            
            elif intent == "help":
                self.metrics["general"] += 1
                return await self._generate_llm_response(
                    OrchestratorPrompts.help_usage_examples(language),
                    FallbackResponses.get("help", language)
                )
            
            elif intent == "greeting":
                self.metrics["general"] += 1
                user_name = user_context.get("user", {}).get("first_name", "")
                return await self._generate_llm_response(
                    OrchestratorPrompts.greeting_response(language, user_name),
                    FallbackResponses.get("greeting", language, user_name=user_name)
                )
            
            else:  # general
                self.metrics["general"] += 1
                return await self._generate_llm_response(
                    OrchestratorPrompts.general_conversation_redirect(language, message, intent_result.get("reasoning", "")),
                    FallbackResponses.get("redirect", language)
                )
        
        except Exception as e:
            self.metrics["errors"] += 1
            return FallbackResponses.get("error", language)
    
    async def _handle_unregistered_user(self, message: str, user_context: Dict[str, Any], platform_type: str) -> str:
        """Handle unregistered users efficiently"""
        
        language = user_context.get("language", "en")
        
        # Check if asking for info
        info_keywords = ["what", "info", "help", "qué", "info", "ajuda", "o que"]
        if any(word in message.lower() for word in info_keywords):
            prompt = OrchestratorPrompts.app_info_with_registration(language, platform_type)
            fallback = FallbackResponses.get("app_info", language)
        else:
            prompt = OrchestratorPrompts.registration_guidance(language, platform_type, message)
            fallback = FallbackResponses.get("registration", language)
        
        return await self._generate_llm_response(prompt, fallback)
    
    async def _handle_general_summary(self, platform_type: str, platform_user_id: str, language: str) -> str:
        """Handle combined summary efficiently"""
        
        try:
            expense_summary = await self.expense_agent.get_expense_summary(platform_type, platform_user_id, days=30)
            reminder_summary = await self.reminder_agent.get_user_reminders_summary(platform_type, platform_user_id)
            
            prompt = OrchestratorPrompts.combined_summary(language, expense_summary, reminder_summary)
            fallback = f"📊 Summary\\n💰 {expense_summary}\\n📋 {reminder_summary}"
            
            return await self._generate_llm_response(prompt, fallback)
            
        except Exception:
            return FallbackResponses.get("error", language)
    
    async def _generate_llm_response(self, prompt: str, fallback: str) -> str:
        """Generate LLM response with fallback"""
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate response"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True, timeout=10)
        return response if response else fallback
    
    # ============================================================================
    # MONITORING & HEALTH
    # ============================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get compact metrics"""
        total = self.metrics["total"]
        if total == 0:
            return self.metrics
        
        return {
            **self.metrics,
            "rates": {
                "expense": self.metrics["expense"] / total,
                "reminder": self.metrics["reminder"] / total,
                "summary": self.metrics["summary"] / total,
                "error": self.metrics["errors"] / total
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Compact health check"""
        try:
            llm_ok = await self.llm_health_check()
            db_ok = bool(self.database and self.database.pool)
            
            return {
                "status": "healthy" if llm_ok and db_ok else "degraded",
                "llm": llm_ok,
                "database": db_ok,
                "metrics": self.get_metrics(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    # ============================================================================
    # REQUIRED ABSTRACT METHODS
    # ============================================================================
    
    async def get_user_patterns(self, user_id: str) -> Dict[str, Any]:
        """Get combined user patterns"""
        try:
            expense_patterns = await self.expense_agent.get_user_patterns(user_id)
            reminder_patterns = await self.reminder_agent.get_user_patterns(user_id)
            return {"expense": expense_patterns, "reminder": reminder_patterns}
        except Exception:
            return {}
    
    def _get_response_template(self, template_key: str, context: Dict[str, Any], language: str) -> str:
        """Not used - we use direct LLM calls"""
        return ""