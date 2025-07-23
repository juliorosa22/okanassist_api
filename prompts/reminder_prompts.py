# agents/prompts/reminder_prompts.py
"""
Concise system prompts for the ReminderAgent
Optimized for minimal token usage while maintaining parsing accuracy
"""

from typing import Dict, Any
from datetime import datetime, timedelta

class ReminderPrompts:
    """Token-optimized prompts for reminder agent"""
    
    @staticmethod
    def reminder_parsing(user_context: Dict[str, Any]) -> str:
        """Compact reminder parsing prompt"""
        
        current_time = user_context["current_time"]
        
        return f"""Parse reminder from natural language. User: {user_context["language"]}, {user_context["timezone"]}

Current: {current_time.strftime('%Y-%m-%d %H:%M')} ({current_time.strftime('%A')})

Extract: title, description, due_datetime, reminder_type, priority, language, recurrence

Types: task, event, deadline, habit, general
Priorities: urgent, high, medium, low

JSON response:
{{"success": true, "title": "Call mom", "description": "Call mom", "due_datetime": "YYYY-MM-DD HH:MM", "reminder_type": "task", "priority": "medium", "is_recurring": false, "detected_language": "en", "confidence": 0.9}}

Time parsing:
- "tomorrow 3pm" → {(current_time + timedelta(days=1)).strftime('%Y-%m-%d')} 15:00
- "in 2 hours" → {(current_time + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M')}
- "Friday morning" → next Friday 09:00
- "today 5pm" → {current_time.strftime('%Y-%m-%d')} 17:00

Priority detection:
- urgent: immediately, asap, critical, urgente, imediatamente
- high: important, must, deadline, importante, prazo
- medium: should, need, debería, preciso
- low: maybe, sometime, quizás, talvez

Type detection:
- task: call, buy, do, llamar, comprar, ligar
- event: meeting, dinner, reunión, jantar
- deadline: deadline, due, payment, plazo, pagamento
- habit: daily, every day, diario, diário

Languages: es keywords→es, pt keywords→pt, default→en
Recurrence: "every day/daily"→daily, "every week"→weekly, "every month"→monthly

If missing title/description, set success=false."""

    @staticmethod
    def success_confirmation(language: str, title: str, due_datetime: str = None, priority: str = "medium", is_recurring: bool = False, recurrence_pattern: str = None) -> str:
        """Compact success confirmation prompt"""
        
        recurring_text = f" (recurring {recurrence_pattern})" if is_recurring and recurrence_pattern else ""
        due_text = f" on {due_datetime}" if due_datetime else ""
        
        return f"""Generate reminder confirmation in {language}.

Reminder: {title}{due_text}{recurring_text} - {priority} priority

Format: "✅ [Reminder set/Recordatorio creado/Lembrete criado]: {title}{due_text}{recurring_text}"

Languages: en→"Reminder set", es→"Recordatorio creado", pt→"Lembrete criado"

Be concise, friendly, include key details."""

    @staticmethod
    def error_response(language: str, error_message: str) -> str:
        """Compact error response prompt"""
        
        return f"""Generate helpful reminder error in {language}. Error: {error_message}

Format: "❌ [brief issue] [suggest format with example]"

Examples:
- en: "❌ Need more details. Try: 'Remind me to call mom tomorrow at 3pm'"
- es: "❌ Necesito más detalles. Prueba: 'Recuérdame llamar a mamá mañana'"
- pt: "❌ Preciso de mais detalhes. Tente: 'Lembre-me de ligar amanhã'"

Be helpful, encouraging."""

    @staticmethod
    def welcome_message(language: str) -> str:
        """Compact welcome message prompt"""
        
        return f"""Generate reminder welcome in {language} for new user.

Format: "👋 Welcome! No reminders yet. Try: [example in user's language]"

Examples:
- en: "Remind me to call mom tomorrow at 3pm"
- es: "Recuérdame llamar a mamá mañana"
- pt: "Lembre-me de ligar para mamãe amanhã"

Be encouraging, show natural example."""

    @staticmethod
    def summary_response(language: str, total_count: int, pending_count: int, completed_count: int, due_today_count: int, overdue_count: int) -> str:
        """Compact summary response prompt"""
        
        return f"""Generate reminder summary in {language}.

Data: {total_count} total, {pending_count} pending, {completed_count} completed, {due_today_count} due today, {overdue_count} overdue

Format: "📋 Reminders: {pending_count} pending, {due_today_count} due today, {overdue_count} overdue"

Languages: en→"Reminders", es→"Recordatorios", pt→"Lembretes"
Terms: pending→pendientes/pendentes, due today→para hoy/para hoje, overdue→atrasado/em atraso

Highlight urgent items if overdue > 0."""

    @staticmethod
    def due_reminders_notification(language: str, reminder_count: int, first_reminder_title: str) -> str:
        """Compact due reminders notification prompt"""
        
        return f"""Generate due reminders notification in {language}.

Count: {reminder_count}, First: {first_reminder_title}

Format: "🔔 {reminder_count} reminder(s) due: {first_reminder_title}" + " (+X more)" if count > 1

Languages: 
- en: "reminder(s) due"
- es: "recordatorio(s)"  
- pt: "lembrete(s)"

Be urgent but helpful."""

class ReminderFallbacks:
    """Ultra-compact fallback responses"""
    
    SUCCESS = {
        "en": "✅ Reminder set: {title}",
        "es": "✅ Recordatorio creado: {title}",
        "pt": "✅ Lembrete criado: {title}"
    }
    
    SUCCESS_WITH_TIME = {
        "en": "✅ Reminder set: {title} on {due_datetime}",
        "es": "✅ Recordatorio creado: {title} el {due_datetime}",
        "pt": "✅ Lembrete criado: {title} em {due_datetime}"
    }
    
    ERROR = {
        "en": "❌ Error creating reminder. Try: 'Remind me to call mom tomorrow'",
        "es": "❌ Error creando recordatorio. Prueba: 'Recuérdame llamar a mamá mañana'",
        "pt": "❌ Erro criando lembrete. Tente: 'Lembre-me de ligar para mamãe amanhã'"
    }
    
    WELCOME = {
        "en": "👋 Welcome! No reminders yet. Try: 'Remind me to call mom tomorrow'",
        "es": "👋 ¡Bienvenido! Sin recordatorios aún. Prueba: 'Recuérdame llamar a mamá'",
        "pt": "👋 Bem-vindo! Sem lembretes ainda. Tente: 'Lembre-me de ligar para mamãe'"
    }
    
    SUMMARY = {
        "en": "📋 Reminders: {pending} pending, {due_today} due today",
        "es": "📋 Recordatorios: {pending} pendientes, {due_today} para hoy", 
        "pt": "📋 Lembretes: {pending} pendentes, {due_today} para hoje"
    }
    
    DUE_NOTIFICATION = {
        "en": "🔔 {count} reminder(s) due: {title}",
        "es": "🔔 {count} recordatorio(s): {title}",
        "pt": "🔔 {count} lembrete(s): {title}"
    }
    
    NO_REMINDERS_DUE = {
        "en": "✅ No reminders due right now",
        "es": "✅ No hay recordatorios pendientes ahora",
        "pt": "✅ Não há lembretes pendentes agora"
    }
    
    @staticmethod
    def format_success(language: str, title: str, due_datetime: str = None, is_recurring: bool = False, recurrence_pattern: str = None) -> str:
        """Format success message"""
        
        if due_datetime:
            template = ReminderFallbacks.SUCCESS_WITH_TIME.get(language, ReminderFallbacks.SUCCESS_WITH_TIME["en"])
            result = template.format(title=title, due_datetime=due_datetime)
        else:
            template = ReminderFallbacks.SUCCESS.get(language, ReminderFallbacks.SUCCESS["en"])
            result = template.format(title=title)
        
        if is_recurring and recurrence_pattern:
            recurring_text = {
                "en": f" (recurring {recurrence_pattern})",
                "es": f" (recurrente {recurrence_pattern})",
                "pt": f" (recorrente {recurrence_pattern})"
            }
            result += recurring_text.get(language, recurring_text["en"])
        
        return result
    
    @staticmethod
    def format_summary(language: str, pending_count: int, due_today_count: int, overdue_count: int = 0) -> str:
        """Format summary message"""
        template = ReminderFallbacks.SUMMARY.get(language, ReminderFallbacks.SUMMARY["en"])
        result = template.format(pending=pending_count, due_today=due_today_count)
        
        if overdue_count > 0:
            overdue_text = {
                "en": f", {overdue_count} overdue",
                "es": f", {overdue_count} atrasados",
                "pt": f", {overdue_count} em atraso"
            }
            result += overdue_text.get(language, overdue_text["en"])
        
        return result
    
    @staticmethod
    def format_due_notification(language: str, count: int, first_title: str) -> str:
        """Format due notification message"""
        template = ReminderFallbacks.DUE_NOTIFICATION.get(language, ReminderFallbacks.DUE_NOTIFICATION["en"])
        result = template.format(count=count, title=first_title)
        
        if count > 1:
            more_text = {
                "en": f" (+{count-1} more)",
                "es": f" (+{count-1} más)",
                "pt": f" (+{count-1} mais)"
            }
            result += more_text.get(language, more_text["en"])
        
        return result

# Token usage optimization:
# - Reduced from ~1200 tokens to ~300 tokens per prompt (~75% reduction)
# - Removed verbose examples and explanations
# - Compact time parsing rules
# - Consolidated language detection
# - Smart fallbacks with dynamic formatting