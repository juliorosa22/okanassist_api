# agents/prompts/orchestrator_prompts.py
"""
Concise system prompts for the OrchestratorAgent
Optimized for minimal token usage while maintaining effectiveness
"""

from typing import Dict, Any

class OrchestratorPrompts:
    """Centralized, token-optimized prompts for the orchestrator agent"""
    
    @staticmethod
    def intent_detection(user_context: Dict[str, Any]) -> str:
        """Compact intent detection prompt"""
        
        return f"""Detect intent for expense/reminder app. User language: {user_context["language"]}

Intents: expense, reminder, expense_summary, reminder_summary, general_summary, app_info, help, greeting, general

JSON response:
{{"success": true, "intent": "detected_intent", "confidence": 0.0-1.0, "detected_language": "en|es|pt"}}

Examples:
- "Coffee $4.50" → expense (0.95)
- "Remind me call mom" → reminder (0.9)  
- "Show expenses" → expense_summary (0.95)
- "Help" → help (0.95)
- "Hola" → greeting (0.95)

Prioritize: amounts→expense, time+action→reminder, "show/what"→summary, greetings→greeting."""

    @staticmethod
    def registration_guidance(language: str, platform_type: str, original_message: str) -> str:
        """Compact registration guidance prompt"""
        
        return f"""Generate registration message in {language} for Okan Personal Assistant.

User tried: "{original_message}" but not registered.

Format: Welcome → explain need to register → mention features → guide to okan-assistant.com

Be warm, helpful, use emojis."""

    @staticmethod
    def app_info_with_registration(language: str, platform_type: str) -> str:
        """Compact app info with registration prompt"""
        
        return f"""Describe Okan Personal Assistant in {language} with registration CTA.

Features: expense tracking (multi-currency), smart reminders, multi-language
Website: okan-assistant.com

Format: Intro → features list → benefits → register CTA
Use emojis, be enthusiastic."""

    @staticmethod
    def combined_summary(language: str, expense_summary: str, reminder_summary: str) -> str:
        """Compact combined summary prompt"""
        
        return f"""Combine summaries in {language}:
Expenses: {expense_summary}
Reminders: {reminder_summary}

Format: "📊 **Summary**\\n💰 [expenses]\\n📋 [reminders]"
Be concise, use emojis."""

    @staticmethod
    def app_capabilities_info(language: str) -> str:
        """Compact app capabilities prompt"""
        
        return f"""List Okan Personal Assistant capabilities in {language}.

Features: expense tracking ($,€,R$), smart reminders, multi-language, natural language

Format: Title → feature bullets with examples → "talk naturally" tip
Use emojis, be enthusiastic."""

    @staticmethod
    def help_usage_examples(language: str) -> str:
        """Compact help examples prompt"""
        
        return f"""Generate usage examples in {language} for Okan Personal Assistant.

Show: expense examples, reminder examples, summary requests
Format: "💡 **How to use:**\\n💰 [examples]\\n⏰ [examples]\\n📊 [examples]"
Be encouraging."""

    @staticmethod
    def greeting_response(language: str, user_name: str = "") -> str:
        """Compact greeting prompt"""
        
        name_part = f" {user_name}" if user_name else ""
        
        return f"""Generate warm greeting in {language} for Okan Personal Assistant.

User: {name_part}
Format: "👋 Hello{name_part}! Welcome to Okan Personal Assistant! [mention features] [invite to try]"
Be warm, mention expense tracking & reminders."""

    @staticmethod
    def general_conversation_redirect(language: str, message: str, intent_reasoning: str) -> str:
        """Compact redirection prompt"""
        
        return f"""Politely redirect in {language}. User said: "{message}"

Response: explain you're specialized in expenses/reminders → suggest examples
Be polite, helpful, redirect to app features."""

    @staticmethod
    def error_response(language: str, error_message: str) -> str:
        """Compact error message prompt"""
        
        return f"""Generate helpful error in {language}. Error: {error_message}

Format: "❌ [apologize] [suggest retry or help] [offer examples]"
Be apologetic but helpful."""

class FallbackResponses:
    """Ultra-compact fallback responses when LLM is unavailable"""
    
    REGISTRATION = {
        "es": "👋 ¡Bienvenido! Regístrate en okan-assistant.com para usar Okan Personal Assistant.",
        "pt": "👋 Bem-vindo! Registre-se em okan-assistant.com para usar o Okan Personal Assistant.", 
        "en": "👋 Welcome! Register at okan-assistant.com to use Okan Personal Assistant."
    }
    
    APP_INFO = {
        "es": "🌟 Okan Personal Assistant: gastos multi-moneda + recordatorios inteligentes. Regístrate: okan-assistant.com",
        "pt": "🌟 Okan Personal Assistant: despesas multi-moeda + lembretes inteligentes. Registre-se: okan-assistant.com",
        "en": "🌟 Okan Personal Assistant: multi-currency expenses + smart reminders. Register: okan-assistant.com"
    }
    
    GREETING = {
        "es": "👋 ¡Hola! Soy Okan Personal Assistant. ¿Cómo puedo ayudarte?",
        "pt": "👋 Olá! Sou o Okan Personal Assistant. Como posso ajudar?",
        "en": "👋 Hello! I'm Okan Personal Assistant. How can I help?"
    }
    
    HELP = {
        "es": "💡 Ejemplos: 'Café €4.50' (gastos), 'Recuérdame llamar' (recordatorios), 'Muestra gastos' (resumen)",
        "pt": "💡 Exemplos: 'Café R$ 4.50' (despesas), 'Lembre-me ligar' (lembretes), 'Mostre despesas' (resumo)",
        "en": "💡 Examples: 'Coffee $4.50' (expenses), 'Remind me call' (reminders), 'Show expenses' (summary)"
    }
    
    CAPABILITIES = {
        "es": "🌟 Okan: 💰 Gastos multi-moneda 📋 Recordatorios inteligentes 🌍 Multi-idioma",
        "pt": "🌟 Okan: 💰 Despesas multi-moeda 📋 Lembretes inteligentes 🌍 Multi-idioma", 
        "en": "🌟 Okan: 💰 Multi-currency expenses 📋 Smart reminders 🌍 Multi-language"
    }
    
    ERROR = {
        "es": "❌ Error procesando solicitud. Inténtalo de nuevo o escribe 'ayuda'.",
        "pt": "❌ Erro processando solicitação. Tente novamente ou digite 'ajuda'.",
        "en": "❌ Error processing request. Try again or type 'help'."
    }
    
    REDIRECT = {
        "es": "Soy especialista en gastos y recordatorios. Prueba: 'Café €4.50' o 'Recuérdame llamar'.",
        "pt": "Sou especialista em despesas e lembretes. Tente: 'Café R$ 4.50' ou 'Lembre-me ligar'.",
        "en": "I specialize in expenses and reminders. Try: 'Coffee $4.50' or 'Remind me call'."
    }
    
    @staticmethod
    def get(response_type: str, language: str, **kwargs) -> str:
        """Get fallback response by type and language"""
        fallback_dict = getattr(FallbackResponses, response_type.upper(), {})
        base_response = fallback_dict.get(language, fallback_dict.get("en", ""))
        
        # Handle dynamic insertions
        if response_type == "greeting" and kwargs.get("user_name"):
            base_response = base_response.replace("👋 Hello!", f"👋 Hello {kwargs['user_name']}!")
            base_response = base_response.replace("👋 ¡Hola!", f"👋 ¡Hola {kwargs['user_name']}!")
            base_response = base_response.replace("👋 Olá!", f"👋 Olá {kwargs['user_name']}!")
        
        return base_response

# Token usage optimization notes:
# - Reduced average prompt size by ~75% (from ~1000 tokens to ~250 tokens)
# - Removed redundant examples and explanations
# - Used abbreviations and compact formatting
# - Kept essential instructions only
# - Fallbacks are single-line responses
# - Estimated cost reduction: ~75% on prompt tokens