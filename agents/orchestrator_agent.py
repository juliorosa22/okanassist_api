# agents/orchestrator_agent.py
from typing import Dict, Optional
from .router_agent import RouterAgent, TaskType
from .expense_agent import ExpenseAgent
from .reminder_agent import ReminderAgent

class OrchestratorAgent:
    def __init__(self, groq_api_key: str, database_url: str, database_instance):
        # Initialize router
        self.router = RouterAgent(groq_api_key)
        
        # Initialize specialized agents
        self.expense_agent = ExpenseAgent(groq_api_key, database_url, database_instance)
        self.reminder_agent = ReminderAgent(groq_api_key, database_url, database_instance)  # New reminder agent
        
        # Track user context across sessions
        self.user_contexts = {}
    
    async def process_message(self, message: str, user_telegram_id: str, user_info: Dict = None) -> str:
        """Main entry point - routes and processes any user message"""
        try:
            # Route the message
            task_type, context = await self.router.route_message(message, user_telegram_id)
            
            print(f"🎯 ROUTED: {task_type.value} | Context: {context}")
            
            # Delegate to appropriate agent
            if task_type == TaskType.EXPENSE:
                return await self._handle_expense(message, user_telegram_id, context, user_info)
            
            elif task_type == TaskType.REMINDER:  # New reminder handling
                return await self._handle_reminder(message, user_telegram_id, context, user_info)
            
            elif task_type == TaskType.SUMMARY_REQUEST:
                return await self._handle_summary(message, user_telegram_id, context)
            
            else:  # GENERAL_QUERY or UNKNOWN
                return await self._handle_general_query(message, user_telegram_id, context)
        
        except Exception as e:
            print(f"❌ Orchestrator error: {e}")
            return "❌ Sorry, I encountered an error processing your message."
    
    async def _handle_expense(self, message: str, user_id: str, context: Dict, user_info: Dict = None) -> str:
        """Delegate to Expense tracker agent"""
        return await self.expense_agent.process_expense(message, user_id, context)
    
    
    async def _handle_reminder(self, message: str, user_id: str, context: Dict, user_info: Dict = None) -> str:
        """Delegate to reminder agent"""
        return await self.reminder_agent.process_reminder(message, user_id, context)
    
    async def _handle_summary(self, message: str, user_id: str, context: Dict) -> str:
        """Handle summary requests - could involve multiple agents"""
        message_lower = message.lower()
        
        if "expense" in message_lower or "spent" in message_lower or "money" in message_lower:
            return await self.expense_agent.get_conversation_summary(user_id)
        elif "reminder" in message_lower or "due" in message_lower or "schedule" in message_lower:
            return await self.reminder_agent.get_user_reminders_summary(user_id)
        else:
            # Combined summary
            expense_summary = await self.expense_agent.get_conversation_summary(user_id)
            reminder_summary = await self.reminder_agent.get_user_reminders_summary(user_id)
            return f"📊 **Summary**\n\n**💰 Expenses:**\n{expense_summary}\n\n**🔔 Reminders:**\n{reminder_summary}"
    
    def _get_help_message(self) -> str:
        """Generate help message"""
        return """
🤖 **Personal Assistant Help**

**💰 Expense Tracking:**
- "Coffee $4.50"
- "Lunch at McDonald's $12"
- "Gas $45"

**🔔 Reminders:**
- "Remind me to call mom tomorrow at 3pm"
- "Don't forget dinner with John Friday 7pm"
- "Remind me to pay bills in 3 days"
- "Set reminder for meeting Monday 2pm"

**📊 Summaries:**
- "Show my expense summary"
- "What reminders do I have?"
- "What's due today?"

**✅ Managing Reminders:**
- "Mark reminder 5 as done"
- "Show my reminders"
- "What's due this week?"

Just type naturally! I'll understand what you need. 😊
        """
    
    async def _handle_general_query(self, message: str, user_id: str, context: Dict) -> str:
        """Handle general queries and conversation"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['help', 'what can you do', 'commands']):
            return self._get_help_message()
        elif any(word in message_lower for word in ['hello', 'hi', 'hey']):
            return "👋 Hello! I can help you track expenses and manage reminders. Try saying 'Coffee $4.50' or 'Remind me to call mom tomorrow'."
        else:
            return "I can help you track expenses and set reminders. Try 'Coffee $4.50' for expenses or 'Remind me to call mom tomorrow' for reminders. Type 'help' for more examples."

    async def check_due_reminders_for_user(self, user_telegram_id: str) -> Optional[str]:
        """Check if user has any due reminders - useful for proactive notifications"""
        return await self.reminder_agent.check_due_reminders(user_telegram_id)