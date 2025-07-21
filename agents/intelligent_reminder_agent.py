# agents/intelligent_reminder_agent.py
from typing import Dict, Optional, Any
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime, timedelta
import json
import re

from core.database import Database
from core.models import User, UserPlatform, Reminder, ReminderType, Priority

class IntelligentReminderAgent:
    """
    LLM-powered reminder agent that understands natural language 
    time expressions and context in multiple languages
    """
    
    def __init__(self, groq_api_key: str, database: Database):
        self.llm = ChatGroq(
            model="llama3-70b-8192",
            api_key=groq_api_key,
            temperature=0.1
        )
        self.database = database
    
    async def process_reminder(self, message: str, platform_type: str, platform_user_id: str) -> str:
        """
        Main method to process reminder messages intelligently
        
        Args:
            message: User's natural language reminder message
            platform_type: Platform where message originated
            platform_user_id: Platform-specific user identifier
            
        Returns:
            Intelligent response confirming reminder or requesting clarification
        """
        
        # Get user context
        user_context = await self._get_user_context(platform_type, platform_user_id)
        
        # Parse reminder using LLM intelligence
        parsed_reminder = await self._intelligent_reminder_parsing(message, user_context)
        
        if not parsed_reminder.get("success"):
            return await self._generate_clarification_request(
                message, parsed_reminder.get("error"), parsed_reminder.get("needs_clarification", []), user_context
            )
        
        # Save the intelligently parsed reminder
        save_result = await self._save_reminder(parsed_reminder, user_context, message)
        
        if not save_result.get("success"):
            return await self._generate_error_response(save_result.get("error"), user_context)
        
        # Generate intelligent confirmation response
        return await self._generate_confirmation(save_result, parsed_reminder, user_context)
    
    async def _get_user_context(self, platform_type: str, platform_user_id: str) -> Dict[str, Any]:
        """Get comprehensive user context for intelligent processing"""
        try:
            user_platform_data = await self.database.get_user_by_platform(platform_type, platform_user_id)
            
            if user_platform_data:
                user, platform = user_platform_data
                
                # Get recent reminders for pattern learning
                recent_reminders = await self.database.get_user_reminders(user.id, include_completed=True, limit=20)
                reminder_patterns = self._extract_reminder_patterns(recent_reminders)
                
                return {
                    "user": user,
                    "platform": platform,
                    "language": user.language,
                    "timezone": user.timezone,
                    "country": user.country_code,
                    "current_time": datetime.now(),
                    "reminder_patterns": reminder_patterns,
                    "is_new_user": False
                }
            else:
                # New user context
                return {
                    "user": None,
                    "platform": None,
                    "language": "en",
                    "timezone": "UTC",
                    "country": "US",
                    "current_time": datetime.now(),
                    "reminder_patterns": {},
                    "is_new_user": True
                }
                
        except Exception as e:
            print(f"❌ Error getting user context: {e}")
            return {
                "user": None,
                "platform": None,
                "language": "en",
                "timezone": "UTC",
                "country": "US",
                "current_time": datetime.now(),
                "reminder_patterns": {},
                "is_new_user": True
            }
    
    async def _intelligent_reminder_parsing(self, message: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to intelligently parse reminder from natural language"""
        
        current_time = user_context["current_time"]
        timezone = user_context["timezone"]
        language = user_context["language"]
        
        system_prompt = f"""You are an intelligent reminder assistant. Parse natural language reminder messages into structured data.

USER CONTEXT:
- Language: {language}
- Timezone: {timezone}
- Current DateTime: {current_time.strftime('%Y-%m-%d %H:%M')} ({timezone})
- Day of Week: {current_time.strftime('%A')}

RECENT REMINDER PATTERNS:
{self._format_reminder_patterns_for_prompt(user_context["reminder_patterns"])}

TASK:
Parse the reminder message and extract structured information. Be intelligent about:
1. Time expressions (relative and absolute)
2. Reminder type inference
3. Priority detection
4. Language understanding
5. Missing information identification

RESPONSE FORMAT (JSON only):
{{
    "success": true/false,
    "title": "concise_reminder_title",
    "description": "detailed_description",
    "due_datetime": "YYYY-MM-DD HH:MM" or null,
    "reminder_type": "task|event|deadline|habit|general",
    "priority": "urgent|high|medium|low",
    "confidence": 0.0_to_1.0,
    "needs_clarification": ["field1", "field2"],
    "detected_language": "language_code",
    "error": "error_message_if_failed"
}}

TIME PARSING RULES:
- "tomorrow at 3pm" → {{current_time + 1 day at 15:00}}
- "in 2 hours" → {{current_time + 2 hours}}
- "Friday morning" → {{next Friday at 09:00}}
- "next week" → {{next Monday at 09:00}}
- "today at 5pm" → {{today at 17:00}}
- "in 30 minutes" → {{current_time + 30 minutes}}

PRIORITY INFERENCE:
- urgent: "immediately", "asap", "right away", "critical", "emergency"
- high: "important", "must", "deadline", "today", "tomorrow"
- medium: "should", "need to", "this week", normal reminders
- low: "sometime", "when possible", "maybe", "eventually"

TYPE INFERENCE:
- task: "call", "buy", "do", "finish", "send", "complete", "pick up"
- event: "meeting", "dinner", "appointment", "party", "lunch", "visit"
- deadline: "deadline", "due", "payment", "submit", "file", "pay bill"
- habit: "daily", "every day", "weekly", "routine"
- general: default for unclear types

PARSING EXAMPLES:
- "Remind me to call mom tomorrow at 3pm" → title: "Call mom", due: tomorrow 15:00, type: task
- "Don't forget dinner with John Friday 7pm" → title: "Dinner with John", due: Friday 19:00, type: event
- "Meeting at 2pm today" → title: "Meeting", due: today 14:00, type: event, priority: high
- "Pay bills by end of month" → title: "Pay bills", type: deadline, priority: high
- "Comprar leche mañana" → title: "Comprar leche", due: tomorrow 09:00, type: task

Handle multiple languages naturally. If parsing fails, set success=false and specify what needs clarification."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Parse this reminder: {message}")
            ])
            
            # Extract JSON from response
            json_text = self._extract_json_from_response(response.content)
            if not json_text:
                return {
                    "success": False,
                    "error": "Could not parse reminder information",
                    "needs_clarification": ["description"]
                }
            
            parsed = json.loads(json_text)
            
            # Validate and enhance parsing
            return await self._validate_reminder_parsing(parsed, user_context)
            
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid response format: {str(e)}",
                "needs_clarification": ["description"]
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Parsing failed: {str(e)}",
                "needs_clarification": ["description"]
            }
    
    async def _validate_reminder_parsing(self, parsed: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and enhance the LLM reminder parsing result"""
        
        if not parsed.get("success"):
            return parsed
        
        # Validate required fields
        if not parsed.get("title") and not parsed.get("description"):
            return {
                "success": False,
                "error": "Missing reminder title or description",
                "needs_clarification": ["description"]
            }
        
        # Set defaults
        parsed["title"] = parsed.get("title") or parsed.get("description", "Reminder")[:50]
        parsed["description"] = parsed.get("description") or parsed.get("title", "")
        parsed["reminder_type"] = parsed.get("reminder_type", "general")
        parsed["priority"] = parsed.get("priority", "medium")
        parsed["detected_language"] = parsed.get("detected_language", user_context["language"])
        
        # Validate due_datetime format and convert to datetime object
        if parsed.get("due_datetime"):
            try:
                # Parse the datetime string
                due_dt = datetime.strptime(parsed["due_datetime"], "%Y-%m-%d %H:%M")
                
                # Ensure it's not in the past (unless it's within next hour for immediate reminders)
                if due_dt < user_context["current_time"] - timedelta(hours=1):
                    # Assume user meant next occurrence (next day, next week, etc.)
                    if due_dt.date() < user_context["current_time"].date():
                        due_dt = due_dt.replace(year=user_context["current_time"].year + 1)
                
                parsed["due_datetime_obj"] = due_dt
                
            except ValueError:
                parsed["due_datetime"] = None
                parsed["due_datetime_obj"] = None
        
        # Validate enum values
        valid_types = [t.value for t in ReminderType]
        if parsed["reminder_type"] not in valid_types:
            parsed["reminder_type"] = "general"
        
        valid_priorities = [p.value for p in Priority]
        if parsed["priority"] not in valid_priorities:
            parsed["priority"] = "medium"
        
        return parsed
    
    async def _save_reminder(self, parsed_reminder: Dict[str, Any], user_context: Dict[str, Any], original_message: str) -> Dict[str, Any]:
        """Save the intelligently parsed reminder to database"""
        
        try:
            # Ensure we have a user
            
            user_id = user_context["user"].id
            
            # Create reminder object
            reminder = Reminder(
                user_id=user_id,
                title=parsed_reminder["title"],
                description=parsed_reminder["description"],
                source_platform=user_context.get("platform", {}).get("platform_type", "unknown"),
                due_datetime=parsed_reminder.get("due_datetime_obj"),
                reminder_type=parsed_reminder["reminder_type"],
                priority=parsed_reminder["priority"],
                is_completed=False,
                created_at=datetime.now()
            )
            
            # Save to database
            saved_reminder = await self.database.save_reminder(reminder)
            
            return {
                "success": True,
                "reminder": saved_reminder,
                "parsed_data": parsed_reminder
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to save reminder: {str(e)}"
            }
    
    async def _generate_confirmation(self, save_result: Dict[str, Any], parsed_reminder: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate intelligent confirmation message in user's language"""
        
        due_info = ""
        if parsed_reminder.get("due_datetime_obj"):
            due_dt = parsed_reminder["due_datetime_obj"]
            due_info = f" on {due_dt.strftime('%Y-%m-%d')} at {due_dt.strftime('%H:%M')}"
        
        confirmation_prompt = f"""Generate a friendly confirmation message for a successfully saved reminder.

USER CONTEXT:
- Language: {user_context["language"]}
- Timezone: {user_context["timezone"]}

REMINDER DETAILS:
- Title: {parsed_reminder["title"]}
- Description: {parsed_reminder["description"]}
- Due: {due_info if due_info else "No specific time"}
- Type: {parsed_reminder["reminder_type"]}
- Priority: {parsed_reminder["priority"]}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Be concise and friendly
3. Include key details clearly
4. Use appropriate emoji based on type and priority
5. Format date/time for the user's locale

EXAMPLES:
- English: "✅ Reminder set: Call mom on 2025-07-21 at 15:00"
- Spanish: "✅ Recordatorio creado: Llamar a mamá el 21/07/2025 a las 15:00"
- Portuguese: "✅ Lembrete criado: Ligar para mamãe em 21/07/2025 às 15:00"
- French: "✅ Rappel créé: Appeler maman le 21/07/2025 à 15h00"

Respond with just the confirmation message, no additional text."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=confirmation_prompt),
                HumanMessage(content="Generate confirmation message")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            # Fallback confirmation
            return f"✅ Reminder set: {parsed_reminder['title']}{due_info}"
    
    async def _generate_clarification_request(self, original_message: str, error: str, needs_clarification: list, user_context: Dict[str, Any]) -> str:
        """Generate helpful clarification request in user's language"""
        
        clarification_prompt = f"""Generate a helpful clarification request for a reminder that couldn't be parsed.

USER CONTEXT:
- Language: {user_context["language"]}
- Current Time: {user_context["current_time"].strftime('%Y-%m-%d %H:%M')}

ORIGINAL MESSAGE: "{original_message}"
ERROR: {error}
NEEDS CLARIFICATION: {needs_clarification}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Be specific about what's missing or unclear
3. Give examples of proper format
4. Be helpful and encouraging
5. Suggest natural language examples

EXAMPLES:
- English: "I need more details about your reminder. Try: 'Remind me to call mom tomorrow at 3pm'"
- Spanish: "Necesito más detalles sobre tu recordatorio. Prueba: 'Recuérdame llamar a mamá mañana a las 3pm'"
- Portuguese: "Preciso de mais detalhes sobre seu lembrete. Tente: 'Lembre-me de ligar para mamãe amanhã às 15h'"

Respond with just the clarification message."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=clarification_prompt),
                HumanMessage(content="Generate clarification request")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            # Fallback clarification
            return "I need more details about your reminder. Try: 'Remind me to call mom tomorrow at 3pm'"
    
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
- English: "❌ Sorry, there was an error saving your reminder. Please try again."
- Spanish: "❌ Lo siento, hubo un error guardando tu recordatorio. Inténtalo de nuevo."
- Portuguese: "❌ Desculpe, houve um erro ao salvar seu lembrete. Tente novamente."

Respond with just the error message."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=error_prompt),
                HumanMessage(content="Generate error message")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            return "❌ Sorry, there was an error processing your reminder. Please try again."
    
    async def get_user_reminders_summary(self, platform_type: str, platform_user_id: str) -> str:
        """Get intelligent reminder summary for user"""
        
        user_context = await self._get_user_context(platform_type, platform_user_id)
        
        if user_context["is_new_user"]:
            return await self._generate_new_user_reminder_message(user_context)
        
        # Get reminder summary
        summary = await self.database.get_reminder_summary(user_context["user"].id, days=30)
        
        # Get due reminders
        due_reminders = await self.database.get_due_reminders(user_context["user"].id, hours_ahead=24)
        
        # Generate intelligent summary response
        summary_prompt = f"""Generate an intelligent reminder summary report.

USER CONTEXT:
- Language: {user_context["language"]}
- Current Time: {user_context["current_time"].strftime('%Y-%m-%d %H:%M')}

SUMMARY DATA:
- Total Reminders: {summary.total_count}
- Completed: {summary.completed_count}
- Pending: {summary.pending_count}
- Overdue: {summary.overdue_count}
- Due Today: {summary.due_today_count}
- Due Tomorrow: {summary.due_tomorrow_count}
- Due Soon (24h): {len(due_reminders)}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Include key insights and priorities
3. Be concise but informative
4. Use emojis for visual appeal
5. Highlight urgent items

EXAMPLES:
- English: "📋 Reminders: 5 pending, 2 due today, 1 overdue. You have 3 urgent tasks to complete."
- Spanish: "📋 Recordatorios: 5 pendientes, 2 para hoy, 1 atrasado. Tienes 3 tareas urgentes."

Respond with just the summary message."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=summary_prompt),
                HumanMessage(content="Generate reminder summary")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            # Fallback summary
            return f"📋 Reminders: {summary.pending_count} pending, {summary.due_today_count} due today, {summary.overdue_count} overdue"
    
    async def check_due_reminders(self, platform_type: str, platform_user_id: str) -> str:
        """Check for due reminders and return appropriate message"""
        
        user_context = await self._get_user_context(platform_type, platform_user_id)
        
        if user_context["is_new_user"]:
            return "✅ No reminders due right now"
        
        due_reminders = await self.database.get_due_reminders(user_context["user"].id, hours_ahead=2)
        
        if not due_reminders:
            return "✅ No reminders due right now"
        
        # Generate due reminder notification
        due_prompt = f"""Generate a notification for due reminders.

USER CONTEXT:
- Language: {user_context["language"]}
- Current Time: {user_context["current_time"].strftime('%Y-%m-%d %H:%M')}

DUE REMINDERS: {len(due_reminders)} reminders due soon

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. List urgent reminders concisely
3. Use appropriate urgency indicators
4. Be helpful and clear

EXAMPLES:
- English: "🔔 2 reminders due: Call mom (3pm), Meeting (4pm)"
- Spanish: "🔔 2 recordatorios: Llamar a mamá (15h), Reunión (16h)"

Respond with just the notification message."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=due_prompt),
                HumanMessage(content="Generate due reminder notification")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            # Fallback notification
            if len(due_reminders) == 1:
                return f"🔔 Reminder due: {due_reminders[0].title}"
            else:
                titles = [r.title for r in due_reminders[:3]]
                more = f" (+{len(due_reminders)-3} more)" if len(due_reminders) > 3 else ""
                return f"🔔 {len(due_reminders)} reminders due: {', '.join(titles)}{more}"
    
    # Helper methods
    def _extract_json_from_response(self, response_text: str) -> Optional[str]:
        """Extract JSON from LLM response"""
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        return json_match.group() if json_match else None
    
    def _extract_reminder_patterns(self, recent_reminders) -> Dict[str, Any]:
        """Extract patterns from user's recent reminders for learning"""
        if not recent_reminders:
            return {}
        
        patterns = {
            "common_types": {},
            "common_priorities": {},
            "typical_times": {},
            "frequent_keywords": {}
        }
        
        for reminder in recent_reminders:
            # Track type frequency
            r_type = reminder.reminder_type
            patterns["common_types"][r_type] = patterns["common_types"].get(r_type, 0) + 1
            
            # Track priority frequency
            priority = reminder.priority
            patterns["common_priorities"][priority] = patterns["common_priorities"].get(priority, 0) + 1
            
            # Track typical times if available
            if reminder.due_datetime:
                hour = reminder.due_datetime.hour
                if hour not in patterns["typical_times"]:
                    patterns["typical_times"][hour] = 0
                patterns["typical_times"][hour] += 1
            
            # Extract keywords from descriptions
            keywords = reminder.description.lower().split()
            for keyword in keywords:
                if len(keyword) > 3:  # Skip short words
                    patterns["frequent_keywords"][keyword] = patterns["frequent_keywords"].get(keyword, 0) + 1
        
        return patterns
    
    def _format_reminder_patterns_for_prompt(self, patterns: Dict[str, Any]) -> str:
        """Format reminder patterns for LLM prompt"""
        if not patterns:
            return "No reminder history available"
        
        formatted = []
        
        if patterns.get("common_types"):
            top_types = sorted(patterns["common_types"].items(), key=lambda x: x[1], reverse=True)[:3]
            formatted.append(f"Frequent types: {', '.join([t for t, count in top_types])}")
        
        if patterns.get("common_priorities"):
            top_priorities = sorted(patterns["common_priorities"].items(), key=lambda x: x[1], reverse=True)[:2]
            formatted.append(f"Typical priorities: {', '.join([p for p, count in top_priorities])}")
        
        if patterns.get("typical_times"):
            top_hours = sorted(patterns["typical_times"].items(), key=lambda x: x[1], reverse=True)[:3]
            formatted.append(f"Common times: {', '.join([f'{h}:00' for h, count in top_hours])}")
        
        return " | ".join(formatted) if formatted else "Learning user patterns..."
    
    async def _generate_new_user_reminder_message(self, user_context: Dict[str, Any]) -> str:
        """Generate welcome message for new users asking about reminders"""
        
        welcome_prompt = f"""Generate a friendly welcome message for a new user asking about reminders.

USER CONTEXT:
- Language: {user_context["language"]}

INSTRUCTIONS:
1. Respond in {user_context["language"]}
2. Explain they don't have reminders yet
3. Give example of how to create reminders
4. Be encouraging and helpful

EXAMPLES:
- English: "👋 Welcome! You don't have any reminders yet. Try saying 'Remind me to call mom tomorrow at 3pm'."
- Spanish: "👋 ¡Bienvenido! Aún no tienes recordatorios. Prueba diciendo 'Recuérdame llamar a mamá mañana a las 3pm'."

Respond with just the welcome message."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=welcome_prompt),
                HumanMessage(content="Generate welcome message")
            ])
            
            return response.content.strip()
            
        except Exception as e:
            return "👋 Welcome! You don't have any reminders yet. Try saying 'Remind me to call mom tomorrow at 3pm'."
    
    