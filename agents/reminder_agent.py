# agents/reminder_agent.py
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import json

from .base_intelligent_agent import BaseIntelligentAgent
from ..prompts.reminder_prompts import ReminderPrompts, ReminderFallbacks
from core.models import Reminder, ReminderType, Priority

class ReminderAgent(BaseIntelligentAgent):
    """
    Clean ReminderAgent with separated prompts and minimal token usage
    Handles reminder parsing, scheduling, and notifications with intelligent responses
    """
    
    async def process_message(self, message: str, platform_type: str, platform_user_id: str) -> str:
        """
        Process reminder message efficiently
        
        Args:
            message: User's reminder message (e.g., "Remind me to call mom tomorrow at 3pm")
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
        
        # Parse reminder using LLM
        parsed_reminder = await self._parse_reminder_llm(message, user_context)
        
        if not parsed_reminder["success"]:
            return await self._generate_error_response(parsed_reminder, user_context)
        
        # Save to database
        save_result = await self._save_reminder_db(parsed_reminder, user_context, message)
        
        if not save_result["success"]:
            return await self._generate_error_response(save_result, user_context)
        
        # Generate success response
        return await self._generate_success_response(parsed_reminder, user_context)
    
    async def get_user_reminders_summary(self, platform_type: str, platform_user_id: str) -> str:
        """Get reminder summary efficiently"""
        
        user_context = await self.get_user_context(platform_type, platform_user_id)
        
        if user_context["is_new_user"]:
            return await self._generate_welcome_message(user_context)
        
        try:
            summary = await self.database.get_reminder_summary(user_context["user"].id, days=30)
            return await self._generate_summary_response(summary, user_context)
        except Exception as e:
            print(f"❌ Reminder summary error: {e}")
            return ReminderFallbacks.ERROR.get(user_context["language"], ReminderFallbacks.ERROR["en"])
    
    async def check_due_reminders(self, platform_type: str, platform_user_id: str) -> str:
        """Check for due reminders efficiently"""
        
        user_context = await self.get_user_context(platform_type, platform_user_id)
        
        if user_context["is_new_user"]:
            return ReminderFallbacks.NO_REMINDERS_DUE.get(
                user_context["language"], 
                ReminderFallbacks.NO_REMINDERS_DUE["en"]
            )
        
        try:
            due_reminders = await self.database.get_due_reminders(user_context["user"].id, hours_ahead=2)
            
            if not due_reminders:
                return ReminderFallbacks.NO_REMINDERS_DUE.get(
                    user_context["language"], 
                    ReminderFallbacks.NO_REMINDERS_DUE["en"]
                )
            
            return await self._generate_due_reminders_response(due_reminders, user_context)
            
        except Exception as e:
            print(f"❌ Due reminders error: {e}")
            return ReminderFallbacks.NO_REMINDERS_DUE.get(
                user_context["language"], 
                ReminderFallbacks.NO_REMINDERS_DUE["en"]
            )
    
    # ============================================================================
    # LLM PARSING
    # ============================================================================
    
    async def _parse_reminder_llm(self, message: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse reminder using compact LLM prompt"""
        
        # Add current time to user context for time parsing
        user_context["current_time"] = datetime.now()
        
        prompt = ReminderPrompts.reminder_parsing(user_context)
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
            return self._validate_parsed_reminder(parsed, user_context)
            
        except (json.JSONDecodeError, Exception) as e:
            return {"success": False, "error": f"Parse error: {str(e)}"}
    
    def _validate_parsed_reminder(self, parsed: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Quick reminder validation"""
        
        if not parsed.get("success"):
            return parsed
        
        # Validate required fields
        if not parsed.get("title") and not parsed.get("description"):
            return {"success": False, "error": "Missing reminder details"}
        
        # Set defaults
        if not parsed.get("title"):
            parsed["title"] = parsed.get("description", "Reminder")[:50]
        if not parsed.get("description"):
            parsed["description"] = parsed.get("title", "Reminder")
        
        # Validate enum values
        valid_types = [t.value for t in ReminderType]
        if parsed.get("reminder_type") not in valid_types:
            parsed["reminder_type"] = "general"
        
        valid_priorities = [p.value for p in Priority]
        if parsed.get("priority") not in valid_priorities:
            parsed["priority"] = "medium"
        
        valid_languages = ["en", "es", "pt"]
        if parsed.get("detected_language") not in valid_languages:
            parsed["detected_language"] = user_context["language"]
        
        # Handle due_datetime
        if parsed.get("due_datetime"):
            try:
                # Handle different time formats from LLM
                due_str = parsed["due_datetime"]
                if "next-friday" in due_str.lower():
                    # Calculate next Friday
                    current_time = user_context["current_time"]
                    days_ahead = 4 - current_time.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    next_friday = current_time + timedelta(days=days_ahead)
                    time_part = due_str.split(" ")[1] if " " in due_str else "09:00"
                    hour, minute = time_part.split(":")
                    parsed["due_datetime_obj"] = next_friday.replace(
                        hour=int(hour), minute=int(minute), second=0, microsecond=0
                    )
                else:
                    # Parse standard datetime format
                    parsed["due_datetime_obj"] = datetime.strptime(due_str, "%Y-%m-%d %H:%M")
                
                # Ensure it's not too far in the past
                current_time = user_context["current_time"]
                if parsed["due_datetime_obj"] < current_time - timedelta(hours=1):
                    # Adjust to next occurrence if seems to be in the past
                    if parsed["due_datetime_obj"].date() < current_time.date():
                        parsed["due_datetime_obj"] = parsed["due_datetime_obj"] + timedelta(days=1)
                
            except (ValueError, AttributeError):
                # If parsing fails, set to 1 hour from now
                parsed["due_datetime_obj"] = user_context["current_time"] + timedelta(hours=1)
        else:
            # No specific time mentioned
            parsed["due_datetime_obj"] = None
        
        # Validate recurrence
        if parsed.get("is_recurring"):
            valid_patterns = ["daily", "weekly", "monthly"]
            if parsed.get("recurrence_pattern") not in valid_patterns:
                parsed["recurrence_pattern"] = "weekly"
        else:
            parsed["is_recurring"] = False
            parsed["recurrence_pattern"] = None
        
        # Clean and validate
        parsed["confidence"] = max(0.0, min(1.0, parsed.get("confidence", 0.8)))
        parsed["title"] = parsed["title"].strip()
        parsed["description"] = parsed["description"].strip()
        
        return parsed
    
    # ============================================================================
    # DATABASE OPERATIONS
    # ============================================================================
    
    async def _save_reminder_db(self, parsed_reminder: Dict[str, Any], user_context: Dict[str, Any], original_message: str) -> Dict[str, Any]:
        """Save reminder to database efficiently"""
        
        try:
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
            
            saved_reminder = await self.database.save_reminder(reminder)
            
            print(f"💾 REMINDER: {parsed_reminder['title']} - {parsed_reminder.get('due_datetime_obj')} ({parsed_reminder['priority']})")
            
            return {"success": True, "reminder_id": saved_reminder.id, "reminder": saved_reminder}
            
        except Exception as e:
            print(f"❌ Save reminder error: {e}")
            return {"success": False, "error": f"Save failed: {str(e)}"}
    
    # ============================================================================
    # RESPONSE GENERATION
    # ============================================================================
    
    async def _generate_success_response(self, parsed_reminder: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate success response efficiently"""
        
        language = parsed_reminder.get("detected_language", user_context["language"])
        title = parsed_reminder["title"]
        due_datetime = None
        if parsed_reminder.get("due_datetime_obj"):
            due_datetime = parsed_reminder["due_datetime_obj"].strftime("%Y-%m-%d %H:%M")
        priority = parsed_reminder["priority"]
        is_recurring = parsed_reminder.get("is_recurring", False)
        recurrence_pattern = parsed_reminder.get("recurrence_pattern")
        
        prompt = ReminderPrompts.success_confirmation(
            language, title, due_datetime, priority, is_recurring, recurrence_pattern
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate confirmation"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True, timeout=8)
        
        if response:
            return response
        
        # Fallback response
        return ReminderFallbacks.format_success(
            language, title, due_datetime, is_recurring, recurrence_pattern
        )
    
    async def _generate_error_response(self, error_data: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate error response efficiently"""
        
        language = user_context["language"]
        error_message = error_data.get("error", "Unknown error")
        
        prompt = ReminderPrompts.error_response(language, error_message)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate error message"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True, timeout=8)
        
        if response:
            return response
        
        # Fallback error
        return ReminderFallbacks.ERROR.get(language, ReminderFallbacks.ERROR["en"])
    
    async def _generate_welcome_message(self, user_context: Dict[str, Any]) -> str:
        """Generate welcome message efficiently"""
        
        language = user_context["language"]
        
        prompt = ReminderPrompts.welcome_message(language)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate welcome"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True, timeout=8)
        
        if response:
            return response
        
        # Fallback welcome
        return ReminderFallbacks.WELCOME.get(language, ReminderFallbacks.WELCOME["en"])
    
    async def _generate_summary_response(self, summary, user_context: Dict[str, Any]) -> str:
        """Generate summary response efficiently"""
        
        language = user_context["language"]
        
        prompt = ReminderPrompts.summary_response(
            language, 
            summary.total_count,
            summary.pending_count, 
            summary.completed_count,
            summary.due_today_count,
            summary.overdue_count
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate summary"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True, timeout=8)
        
        if response:
            return response
        
        # Fallback summary
        return ReminderFallbacks.format_summary(
            language, summary.pending_count, summary.due_today_count, summary.overdue_count
        )
    
    async def _generate_due_reminders_response(self, due_reminders, user_context: Dict[str, Any]) -> str:
        """Generate due reminders notification efficiently"""
        
        language = user_context["language"]
        count = len(due_reminders)
        first_title = due_reminders[0].title if due_reminders else ""
        
        prompt = ReminderPrompts.due_reminders_notification(language, count, first_title)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate notification"}
        ]
        
        response = await self.safe_llm_call(messages, cache=True, timeout=8)
        
        if response:
            return response
        
        # Fallback notification
        return ReminderFallbacks.format_due_notification(language, count, first_title)
    
    # ============================================================================
    # REQUIRED ABSTRACT METHODS
    # ============================================================================
    
    async def get_user_patterns(self, user_id: str) -> Dict[str, Any]:
        """Get user reminder patterns (simplified)"""
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
        """Not used - we use direct LLM calls"""
        return ""