# agents/reminder_agent.py
from typing import Dict, Optional
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from .tools.reminder_tools import (
    parse_reminder_from_message,
    save_reminder,
    get_user_reminders,
    mark_reminder_complete,
    get_due_reminders,
    update_reminder,
    delete_reminder,
    set_database as set_reminder_database
)

class ReminderAgent:
    """
    Specialized agent for reminder/scheduling tasks
    """
    
    def __init__(self, groq_api_key: str, database_url: str, database_instance):
        self.groq_api_key = groq_api_key
        
        # Set database for tools
        set_reminder_database(database_instance)
        
        # Initialize LLM
        self.llm = ChatGroq(
            model="llama3-8b-8192",
            api_key=groq_api_key,
            temperature=0
        )
        
        # Define tools
        self.tools = [
            parse_reminder_from_message,
            save_reminder,
            get_user_reminders,
            mark_reminder_complete,
            get_due_reminders,
            update_reminder,
            delete_reminder
        ]
        
        # Create agent with memory
        self.memory = MemorySaver()
        
        system_message = """You are an AI reminder assistant. Handle reminder requests with this workflow:

🔄 MANDATORY WORKFLOW FOR REMINDERS:

STEP 1: Use parse_reminder_from_message(message) to extract time, date, and description
STEP 2: Use save_reminder(user_telegram_id, title, description, due_date, due_time, reminder_type, priority)

⚠️ CRITICAL RULES:
- ALWAYS extract meaningful reminder details
- Parse relative dates like "tomorrow", "next week", "in 2 hours"
- Set appropriate priority (low, medium, high, urgent)
- Use clear, actionable reminder titles

📝 EXAMPLE WORKFLOWS:

User: "Remind me to call mom tomorrow at 3pm"
1. parse_reminder_from_message("Remind me to call mom tomorrow at 3pm")
   → {title: "Call mom", description: "Call mom", due_date: "2025-07-13", due_time: "15:00", type: "task"}
2. save_reminder(user_id, "Call mom", "Call mom", "2025-07-13", "15:00", "task", "medium")

User: "Don't forget dinner with John Friday 7pm"
1. parse_reminder_from_message("Don't forget dinner with John Friday 7pm")
   → {title: "Dinner with John", due_date: "2025-07-18", due_time: "19:00", type: "event"}
2. save_reminder(user_id, "Dinner with John", "Dinner with John", "2025-07-18", "19:00", "event", "medium")

✅ SUCCESS RESPONSE: "✅ Reminder set: [Title] on [Date] at [Time]"

🔍 FOR QUERIES:
- "Show my reminders" → Use get_user_reminders
- "What's due today?" → Use get_due_reminders
- "Mark [reminder] as done" → Use mark_reminder_complete

📋 REMINDER TYPES:
- task: Things to do
- event: Events to attend
- deadline: Important deadlines
- habit: Recurring habits
- general: Other reminders

🚨 PRIORITY LEVELS:
- urgent: Time-sensitive, important
- high: Important but not urgent
- medium: Normal reminders
- low: Nice-to-have reminders

Always confirm saved reminders with clear details!"""
        
        # Create the agent
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            checkpointer=self.memory,
            prompt=system_message
        )
    
    async def process_reminder(self, message: str, user_telegram_id: str, context: Dict = None) -> str:
        """Process reminder-related messages"""
        return await self._handle_reminder_directly(message, user_telegram_id, context)
        
    async def _handle_reminder_directly(self, message: str, user_telegram_id: str, context: Dict = None) -> str:
        """Handle reminder parsing with guaranteed sequential execution"""
        try:
            # Step 1: Parse reminder
            from .tools.reminder_tools import parse_reminder_from_message
            parse_result = await parse_reminder_from_message.ainvoke({"message": message})
            
            if not parse_result.get("success"):
                return f"❌ {parse_result.get('error', 'Could not parse reminder')}"
            
            # Step 2: Save reminder
            from .tools.reminder_tools import save_reminder
            save_result = await save_reminder.ainvoke({
                "user_telegram_id": user_telegram_id,
                "title": parse_result["title"],
                "description": parse_result["description"],
                "due_date": parse_result.get("due_date"),
                "due_time": parse_result.get("due_time"),
                "reminder_type": parse_result.get("reminder_type", "general"),
                "priority": parse_result.get("priority", "medium")
            })
            
            if save_result.get("success"):
                due_info = ""
                if parse_result.get("due_date"):
                    due_info = f" on {parse_result['due_date']}"
                if parse_result.get("due_time"):
                    due_info += f" at {parse_result['due_time']}"
                
                return f"✅ Reminder set: {save_result['title']}{due_info}"
            else:
                return f"❌ Failed to save reminder: {save_result.get('error')}"
                
        except Exception as e:
            return f"❌ Error processing reminder: {str(e)}"
    
    async def get_user_reminders_summary(self, user_telegram_id: str) -> str:
        """Get summary of user's reminders"""
        config = {"configurable": {"thread_id": f"{user_telegram_id}_reminders"}}
        
        try:
            response = await self.agent.ainvoke(
                {"messages": [{"role": "user", "content": "Show me my reminders summary"}]},
                config
            )
            return response["messages"][-1].content
        except Exception as e:
            return f"❌ Error getting reminders: {str(e)}"
    
    async def check_due_reminders(self, user_telegram_id: str) -> str:
        """Check for due reminders"""
        try:
            from .tools.reminder_tools import get_due_reminders
            due_result = await get_due_reminders.ainvoke({"user_telegram_id": user_telegram_id})
            
            if due_result.get("success") and due_result.get("reminders"):
                reminders = due_result["reminders"]
                if len(reminders) == 1:
                    reminder = reminders[0]
                    return f"🔔 Reminder due: {reminder['title']}"
                else:
                    titles = [r['title'] for r in reminders[:3]]
                    more = f" (+{len(reminders)-3} more)" if len(reminders) > 3 else ""
                    return f"🔔 {len(reminders)} reminders due: {', '.join(titles)}{more}"
            else:
                return "✅ No reminders due right now"
                
        except Exception as e:
            return f"❌ Error checking due reminders: {str(e)}"