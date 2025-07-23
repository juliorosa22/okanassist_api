# agents/reminder_agent.py
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import json

from .base_intelligent_agent import BaseIntelligentAgent
from core.models import Reminder, ReminderType, Priority

class ReminderAgent(BaseIntelligentAgent):
    """
    ReminderAgent using BaseIntelligentAgent with LLM providers for:
    1. Intelligent parsing and natural response generation
    2. Parse message (due date, description, priority, frequency, etc.)
    3. Handle multiple languages (English, Spanish, Portuguese)
    4. Respond in user's language
    5. Save reminder for future notifications
    6. Compatible with Reminder model
    """
    
    async def process_message(self, message: str, platform_type: str, platform_user_id: str) -> str:
        """
        Process reminder message using LLM for intelligent parsing
        
        Args:
            message: User's reminder message (e.g., "Remind me to call mom tomorrow at 3pm")
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
        
        # Use LLM for intelligent reminder parsing
        parsed_reminder = await self._parse_reminder_with_llm(message, user_context)
        
        if not parsed_reminder["success"]:
            return await self._generate_error_response(parsed_reminder, user_context)
        
        # Save reminder to database
        save_result = await self._save_reminder_to_database(parsed_reminder, user_context, message)
        
        if not save_result["success"]:
            return await self._generate_error_response(save_result, user_context)
        
        # Generate success response using LLM
        return await self._generate_success_response(parsed_reminder, user_context)
    
    async def get_user_reminders_summary(self, platform_type: str, platform_user_id: str) -> str:
        """Get user's reminder summary with intelligent formatting"""
        user_context = await self.get_user_context(platform_type, platform_user_id)
        
        if user_context["is_new_user"]:
            return await self._generate_welcome_message(user_context)
        
        try:
            summary = await self.database.get_reminder_summary(user_context["user"].id, days=30)
            return await self._generate_summary_response(summary, user_context)
        except Exception as e:
            print(f"❌ Error getting reminder summary: {e}")
            return await self._generate_error_response(
                {"error": "Could not retrieve reminder summary"}, 
                user_context
            )
    
    async def check_due_reminders(self, platform_type: str, platform_user_id: str) -> str:
        """Check for due reminders and return intelligent notification"""
        user_context = await self.get_user_context(platform_type, platform_user_id)
        
        if user_context["is_new_user"]:
            return "✅ No reminders due right now"
        
        try:
            due_reminders = await self.database.get_due_reminders(user_context["user"].id, hours_ahead=2)
            
            if not due_reminders:
                return "✅ No reminders due right now"
            
            return await self._generate_due_reminders_response(due_reminders, user_context)
            
        except Exception as e:
            print(f"❌ Error checking due reminders: {e}")
            return "✅ No reminders due right now"
    
    # ============================================================================
    # INTELLIGENT LLM PARSING
    # ============================================================================
    
    async def _parse_reminder_with_llm(self, message: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to intelligently parse reminder message
        
        Args:
            message: User's reminder message
            user_context: User context for personalized parsing
            
        Returns:
            Parsed reminder data: {success, title, description, due_datetime, priority, reminder_type, etc.}
        """
        
        # Build intelligent parsing prompt
        system_prompt = self._build_reminder_parsing_prompt(user_context)
        
        # Use safe LLM call from base class with retry logic
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Parse this reminder: {message}"}
        ]
        
        response_content = await self.safe_llm_call(messages, max_retries=3, cache=True)
        
        if not response_content:
            return {
                "success": False,
                "error": "Service temporarily unavailable. Please try again.",
                "needs_clarification": ["description"]
            }
        
        try:
            # Extract JSON from LLM response
            json_text = self.extract_json_from_response(response_content)
            if not json_text:
                return {
                    "success": False,
                    "error": "Could not understand the reminder format",
                    "needs_clarification": ["description"]
                }
            
            parsed = json.loads(json_text)
            
            # Validate the parsing result
            return self._validate_parsed_reminder(parsed, user_context)
            
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Invalid response format from service",
                "needs_clarification": ["description"]
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Parsing failed: {str(e)}",
                "needs_clarification": ["description"]
            }
    
    def _build_reminder_parsing_prompt(self, user_context: Dict[str, Any]) -> str:
        """Build intelligent reminder parsing prompt for LLM"""
        
        current_time = user_context["current_time"]
        
        return f"""You are an intelligent reminder assistant. Parse natural language reminder messages into structured data.

USER CONTEXT:
- Default Language: {user_context["language"]}
- Timezone: {user_context["timezone"]}
- Current DateTime: {current_time.strftime('%Y-%m-%d %H:%M')} ({user_context["timezone"]})
- Day of Week: {current_time.strftime('%A')}

TASK:
Parse the reminder message and extract ALL fields compatible with the Reminder model:
1. Title and description
2. Due date/time (relative and absolute)
3. Priority level
4. Reminder type
5. Language detection
6. Recurrence/frequency if mentioned

SUPPORTED LANGUAGES:
- English: "remind me", "don't forget", "tomorrow", "at 3pm"
- Spanish: "recuérdame", "no olvides", "mañana", "a las 3pm"
- Portuguese: "lembre-me", "não esquecer", "amanhã", "às 3h"

RESPONSE FORMAT (JSON only):
{{
    "success": true/false,
    "title": "concise_reminder_title",
    "description": "detailed_description",
    "due_datetime": "YYYY-MM-DD HH:MM" or null,
    "reminder_type": "task|event|deadline|habit|general",
    "priority": "urgent|high|medium|low",
    "is_recurring": true/false,
    "recurrence_pattern": "daily|weekly|monthly" or null,
    "detected_language": "en|es|pt",
    "confidence": 0.0_to_1.0,
    "error": "error_message_if_failed"
}}

TIME PARSING RULES (current time: {current_time.strftime('%Y-%m-%d %H:%M')}):
- "tomorrow at 3pm" → {(current_time + timedelta(days=1)).strftime('%Y-%m-%d')} 15:00
- "mañana a las 3pm" → {(current_time + timedelta(days=1)).strftime('%Y-%m-%d')} 15:00
- "amanhã às 15h" → {(current_time + timedelta(days=1)).strftime('%Y-%m-%d')} 15:00
- "in 2 hours" → {(current_time + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M')}
- "en 2 horas" → {(current_time + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M')}
- "em 2 horas" → {(current_time + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M')}
- "today at 5pm" → {current_time.strftime('%Y-%m-%d')} 17:00
- "Friday morning" → next Friday at 09:00
- "viernes por la mañana" → next Friday at 09:00
- "sexta de manhã" → next Friday at 09:00

PRIORITY INFERENCE:
- urgent: "immediately", "asap", "right away", "critical", "emergency", "inmediatamente", "urgente", "crítico", "imediatamente", "emergência"
- high: "important", "must", "deadline", "importante", "debe", "plazo", "importante", "prazo"
- medium: "should", "need to", "this week", "debería", "necesito", "esta semana", "deveria", "preciso", "esta semana"
- low: "maybe", "sometime", "when possible", "quizás", "tal vez", "cuando sea posible", "talvez", "quando possível"

TYPE INFERENCE:
- task: "call", "buy", "do", "finish", "send", "complete", "pick up", "llamar", "comprar", "hacer", "terminar", "ligar", "comprar", "fazer"
- event: "meeting", "dinner", "appointment", "party", "lunch", "visit", "reunión", "cena", "cita", "fiesta", "reunião", "jantar", "encontro"
- deadline: "deadline", "due", "payment", "submit", "file", "pay bill", "plazo", "vencimiento", "pago", "prazo", "pagamento"
- habit: "daily", "every day", "weekly", "routine", "diario", "todos los días", "semanal", "diário", "todos os dias", "rotina"
- general: default for unclear types

RECURRENCE DETECTION:
- "every day", "daily", "todos los días", "diario", "todos os dias", "diário" → daily
- "every week", "weekly", "todas las semanas", "semanal", "toda semana", "semanal" → weekly
- "every month", "monthly", "todos los meses", "mensual", "todo mês", "mensal" → monthly

PARSING EXAMPLES:
- "Remind me to call mom tomorrow at 3pm" → {{"success": true, "title": "Call mom", "description": "Call mom", "due_datetime": "{(current_time + timedelta(days=1)).strftime('%Y-%m-%d')} 15:00", "reminder_type": "task", "priority": "medium", "is_recurring": false, "detected_language": "en", "confidence": 0.9}}
- "Recuérdame llamar a mamá mañana a las 3pm" → {{"success": true, "title": "Llamar a mamá", "description": "Llamar a mamá", "due_datetime": "{(current_time + timedelta(days=1)).strftime('%Y-%m-%d')} 15:00", "reminder_type": "task", "priority": "medium", "is_recurring": false, "detected_language": "es", "confidence": 0.9}}
- "Meeting with John Friday 2pm" → {{"success": true, "title": "Meeting with John", "description": "Meeting with John", "due_datetime": "next-friday 14:00", "reminder_type": "event", "priority": "high", "is_recurring": false, "detected_language": "en", "confidence": 0.9}}
- "Take medicine every day at 8am" → {{"success": true, "title": "Take medicine", "description": "Take medicine", "due_datetime": "{(current_time + timedelta(days=1)).strftime('%Y-%m-%d')} 08:00", "reminder_type": "habit", "priority": "high", "is_recurring": true, "recurrence_pattern": "daily", "detected_language": "en", "confidence": 0.9}}

If parsing fails or critical information is missing, set success=false and provide clear error message."""
    
    def _validate_parsed_reminder(self, parsed: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
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
        if not parsed.get("title") and not parsed.get("description"):
            return {
                "success": False,
                "error": "Missing reminder title or description"
            }
        
        # Set defaults for title and description
        if not parsed.get("title"):
            parsed["title"] = parsed.get("description", "Reminder")[:50]
        if not parsed.get("description"):
            parsed["description"] = parsed.get("title", "Reminder")
        
        # Validate and set reminder type
        valid_types = [t.value for t in ReminderType]
        if parsed.get("reminder_type") not in valid_types:
            parsed["reminder_type"] = ReminderType.GENERAL.value
        
        # Validate and set priority
        valid_priorities = [p.value for p in Priority]
        if parsed.get("priority") not in valid_priorities:
            parsed["priority"] = Priority.MEDIUM.value
        
        # Validate language
        valid_languages = ["en", "es", "pt"]
        if parsed.get("detected_language") not in valid_languages:
            parsed["detected_language"] = user_context["language"]
        
        # Validate due_datetime format and convert to datetime object
        if parsed.get("due_datetime"):
            try:
                # Handle the LLM response format
                due_str = parsed["due_datetime"]
                if "next-friday" in due_str:
                    # Calculate next Friday
                    current_time = user_context["current_time"]
                    days_ahead = 4 - current_time.weekday()  # Friday is 4
                    if days_ahead <= 0:  # If today is Friday or later
                        days_ahead += 7
                    next_friday = current_time + timedelta(days=days_ahead)
                    time_part = due_str.split(" ")[1] if " " in due_str else "14:00"
                    hour, minute = time_part.split(":")
                    parsed["due_datetime_obj"] = next_friday.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
                else:
                    # Parse standard datetime format
                    parsed["due_datetime_obj"] = datetime.strptime(due_str, "%Y-%m-%d %H:%M")
                
                # Ensure it's not in the past (unless it's within next hour for immediate reminders)
                if parsed["due_datetime_obj"] < user_context["current_time"] - timedelta(hours=1):
                    # Adjust to next day/week if it seems to be in the past
                    if parsed["due_datetime_obj"].date() < user_context["current_time"].date():
                        parsed["due_datetime_obj"] = parsed["due_datetime_obj"] + timedelta(days=1)
                
            except (ValueError, AttributeError):
                # If datetime parsing fails, set to 1 hour from now
                parsed["due_datetime_obj"] = user_context["current_time"] + timedelta(hours=1)
        else:
            # No specific time, set to 1 hour from now
            parsed["due_datetime_obj"] = user_context["current_time"] + timedelta(hours=1)
        
        # Validate recurrence settings
        if parsed.get("is_recurring"):
            valid_patterns = ["daily", "weekly", "monthly"]
            if parsed.get("recurrence_pattern") not in valid_patterns:
                parsed["recurrence_pattern"] = "weekly"  # Default
        else:
            parsed["is_recurring"] = False
            parsed["recurrence_pattern"] = None
        
        # Ensure confidence is between 0 and 1
        parsed["confidence"] = max(0.0, min(1.0, parsed.get("confidence", 0.8)))
        
        # Clean title and description
        parsed["title"] = parsed["title"].strip()
        parsed["description"] = parsed["description"].strip()
        
        return parsed
    
    # ============================================================================
    # DATABASE OPERATIONS
    # ============================================================================
    
    async def _save_reminder_to_database(self, parsed_reminder: Dict[str, Any], user_context: Dict[str, Any], original_message: str) -> Dict[str, Any]:
        """
        Save the parsed reminder to database
        
        Args:
            parsed_reminder: Validated parsing result
            user_context: User context
            original_message: Original user message
            
        Returns:
            Save result
        """
        try:
            # Create Reminder object compatible with models.py
            reminder = Reminder(
                user_id=user_context["user"].id,
                title=parsed_reminder["title"],
                description=parsed_reminder["description"],
                source_platform=user_context.get("platform", {}).get("platform_type", "unknown"),
                due_datetime=parsed_reminder.get("due_datetime_obj"),
                reminder_type=parsed_reminder["reminder_type"],
                priority=parsed_reminder["priority"],
                is_completed=False,
                is_recurring=parsed_reminder.get("is_recurring", False),
                recurrence_pattern=parsed_reminder.get("recurrence_pattern"),
                notification_sent=False,
                created_at=datetime.now()
            )
            
            # Save to database
            saved_reminder = await self.database.save_reminder(reminder)
            
            print(f"💾 REMINDER SAVED: {parsed_reminder['title']} - {parsed_reminder.get('due_datetime_obj')} ({parsed_reminder['priority']})")
            
            return {
                "success": True,
                "reminder_id": saved_reminder.id,
                "reminder": saved_reminder
            }
            
        except Exception as e:
            print(f"❌ SAVE REMINDER ERROR: {e}")
            return {
                "success": False,
                "error": f"Failed to save reminder: {str(e)}"
            }
    
    # ============================================================================
    # INTELLIGENT RESPONSE GENERATION
    # ============================================================================
    
    async def _generate_success_response(self, parsed_reminder: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate success response using LLM in user's language"""
        
        language = parsed_reminder.get("detected_language", user_context["language"])
        title = parsed_reminder["title"]
        due_datetime = parsed_reminder.get("due_datetime_obj")
        priority = parsed_reminder["priority"]
        reminder_type = parsed_reminder["reminder_type"]
        is_recurring = parsed_reminder.get("is_recurring", False)
        
        due_str = due_datetime.strftime("%Y-%m-%d %H:%M") if due_datetime else "no specific time"
        recurring_str = f" (recurring {parsed_reminder.get('recurrence_pattern', '')})" if is_recurring else ""
        
        # Build response generation prompt
        system_prompt = f"""Generate a friendly reminder confirmation message in {language}.

REMINDER DETAILS:
- Title: {title}
- Due: {due_str}
- Priority: {priority}
- Type: {reminder_type}
- Recurring: {recurring_str}

INSTRUCTIONS:
1. Respond in {language} language
2. Be concise and friendly
3. Include checkmark emoji ✅
4. Format due time in user-friendly way
5. Mention if it's recurring

EXAMPLES:
- English: "✅ Reminder set: Call mom on 2025-07-22 at 15:00"
- Spanish: "✅ Recordatorio creado: Llamar a mamá el 22/07/2025 a las 15:00"
- Portuguese: "✅ Lembrete criado: Ligar para mamãe em 22/07/2025 às 15:00"

Respond with just the confirmation message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate confirmation message"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback response if LLM fails
        if language == "es":
            return f"✅ Recordatorio creado: {title} - {due_str}{recurring_str}"
        elif language == "pt":
            return f"✅ Lembrete criado: {title} - {due_str}{recurring_str}"
        else:
            return f"✅ Reminder set: {title} - {due_str}{recurring_str}"
    
    async def _generate_error_response(self, error_data: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate error response using LLM in user's language"""
        
        language = user_context["language"]
        error_message = error_data.get("error", "Unknown error")
        
        system_prompt = f"""Generate a helpful error message for reminder creation in {language}.

ERROR: {error_message}

INSTRUCTIONS:
1. Respond in {language} language
2. Be apologetic but helpful
3. Give an example of correct format
4. Include ❌ emoji

EXAMPLES:
- English: "❌ I need more details. Try: 'Remind me to call mom tomorrow at 3pm'"
- Spanish: "❌ Necesito más detalles. Prueba: 'Recuérdame llamar a mamá mañana a las 3pm'"
- Portuguese: "❌ Preciso de mais detalhes. Tente: 'Lembre-me de ligar para mamãe amanhã às 15h'"

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
            return "❌ Error al crear recordatorio. Prueba: 'Recuérdame llamar a mamá mañana'"
        elif language == "pt":
            return "❌ Erro ao criar lembrete. Tente: 'Lembre-me de ligar para mamãe amanhã'"
        else:
            return "❌ Error creating reminder. Try: 'Remind me to call mom tomorrow'"
    
    async def _generate_welcome_message(self, user_context: Dict[str, Any]) -> str:
        """Generate welcome message for new users"""
        
        language = user_context["language"]
        
        system_prompt = f"""Generate a welcome message for a new user asking for reminder summary in {language}.

INSTRUCTIONS:
1. Respond in {language} language
2. Welcome them warmly
3. Explain they don't have reminders yet
4. Give example of how to create reminders
5. Be encouraging

EXAMPLES:
- English: "👋 Welcome! You don't have any reminders yet. Try: 'Remind me to call mom tomorrow at 3pm'"
- Spanish: "👋 ¡Bienvenido! Aún no tienes recordatorios. Prueba: 'Recuérdame llamar a mamá mañana a las 3pm'"
- Portuguese: "👋 Bem-vindo! Você ainda não tem lembretes. Tente: 'Lembre-me de ligar para mamãe amanhã às 15h'"

Respond with just the welcome message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate welcome message"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback welcome messages
        if language == "es":
            return "👋 ¡Bienvenido! Aún no tienes recordatorios. Prueba: 'Recuérdame llamar a mamá mañana'"
        elif language == "pt":
            return "👋 Bem-vindo! Você ainda não tem lembretes. Tente: 'Lembre-me de ligar para mamãe amanhã'"
        else:
            return "👋 Welcome! You don't have any reminders yet. Try: 'Remind me to call mom tomorrow'"
    
    async def _generate_summary_response(self, summary, user_context: Dict[str, Any]) -> str:
        """Generate summary response using LLM"""
        
        language = user_context["language"]
        
        system_prompt = f"""Generate a reminder summary report in {language}.

SUMMARY DATA:
- Total Reminders: {summary.total_count}
- Pending: {summary.pending_count}
- Completed: {summary.completed_count}
- Due Today: {summary.due_today_count}
- Overdue: {summary.overdue_count}

INSTRUCTIONS:
1. Respond in {language} language
2. Use 📋 emoji
3. Be concise but informative
4. Highlight urgent items if any

EXAMPLES:
- English: "📋 Reminders: 5 pending, 2 due today, 1 overdue"
- Spanish: "📋 Recordatorios: 5 pendientes, 2 para hoy, 1 atrasado"
- Portuguese: "📋 Lembretes: 5 pendentes, 2 para hoje, 1 em atraso"

Respond with just the summary message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate summary message"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback summary
        if language == "es":
            return f"📋 Recordatorios: {summary.pending_count} pendientes, {summary.due_today_count} para hoy"
        elif language == "pt":
            return f"📋 Lembretes: {summary.pending_count} pendentes, {summary.due_today_count} para hoje"
        else:
            return f"📋 Reminders: {summary.pending_count} pending, {summary.due_today_count} due today"
    
    async def _generate_due_reminders_response(self, due_reminders, user_context: Dict[str, Any]) -> str:
        """Generate due reminders notification using LLM"""
        
        language = user_context["language"]
        count = len(due_reminders)
        first_reminder = due_reminders[0].title if due_reminders else ""
        
        system_prompt = f"""Generate a due reminders notification in {language}.

DUE REMINDERS:
- Count: {count}
- First reminder: {first_reminder}
- Show only first + count if multiple

INSTRUCTIONS:
1. Respond in {language} language
2. Use 🔔 emoji
3. Be urgent but helpful
4. List first reminder + count if multiple

EXAMPLES:
- English: "🔔 2 reminders due: Call mom (+1 more)"
- Spanish: "🔔 2 recordatorios: Llamar a mamá (+1 más)"
- Portuguese: "🔔 2 lembretes: Ligar para mamãe (+1 mais)"

Respond with just the notification message."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate due reminders notification"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True)
        
        if response:
            return response
        
        # Fallback notification
        more_text = f" (+{count-1} more)" if count > 1 else ""
        
        if language == "es":
            return f"🔔 {count} recordatorio(s): {first_reminder}{more_text}"
        elif language == "pt":
            return f"🔔 {count} lembrete(s): {first_reminder}{more_text}"
        else:
            return f"🔔 {count} reminder(s): {first_reminder}{more_text}"
    
    # ============================================================================
    # REQUIRED ABSTRACT METHODS FROM BASE CLASS
    # ============================================================================
    
    async def get_user_patterns(self, user_id: str) -> Dict[str, Any]:
        """
        Get user reminder patterns (simplified for now)
        Could be enhanced to provide user's favorite reminder types, times, etc.
        """
        try:
            recent_reminders = await self.database.get_user_reminders(user_id, include_completed=True, limit=20)
            if not recent_reminders:
                return {}
            
            # Extract simple patterns
            types = {}
            priorities = {}
            for reminder in recent_reminders[:10]:
                r_type = reminder.reminder_type
                types[r_type] = types.get(r_type, 0) + 1
                
                priority = reminder.priority
                priorities[priority] = priorities.get(priority, 0) + 1
            
            return {"common_types": types, "common_priorities": priorities}
        except Exception:
            return {}
    
    def _get_response_template(self, template_key: str, context: Dict[str, Any], language: str) -> str:
        """
        Get response template (not used in this implementation since we use LLM directly)
        Required by base class but not used here
        """
        return ""