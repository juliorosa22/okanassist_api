# agents/router_agent.py
from enum import Enum
from typing import Dict, Optional, Tuple
import re
from langchain_core.tools import tool
from langchain_groq import ChatGroq

class TaskType(Enum):
    EXPENSE = "expense"
    REMINDER = "reminder"  
    GENERAL_QUERY = "general_query"
    SUMMARY_REQUEST = "summary_request"
    UNKNOWN = "unknown"

class RouterAgent:
    """
    Main router that determines task type and delegates to appropriate handler
    """
    
    def __init__(self, groq_api_key: str):
        self.llm = ChatGroq(
            model="llama3-8b-8192",
            api_key=groq_api_key,
            temperature=0
        )
        
        # Pattern-based routing (fast path)
        self.patterns = {
            TaskType.EXPENSE: [
                r'\$\d+(?:\.\d{2})?',  # $45.50
                r'\d+(?:\.\d{2})?\s*(?:dollars?|bucks?|\$)',
                r'spent\s+\$?\d+',
                r'cost\s+\$?\d+',
                r'paid\s+\$?\d+'
            ],
            TaskType.REMINDER: [
                r'remind me',
                r'don\'t forget',
                r'remember to',
                r'set reminder',
                r'reminder:',
                r'remind me to',
                r'remind me about',
                r'in \d+ (?:hours?|days?|weeks?)',
                r'(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
                r'\d{1,2}(?::\d{2})?\s*(?:am|pm)',
            ]
        }
    
    async def route_message(self, message: str, user_id: str) -> Tuple[TaskType, Dict]:
        """
        Route message to appropriate handler
        
        Returns:
            (task_type, context_data)
        """
        # First try pattern-based routing (fast)
        task_type = self._pattern_route(message)
        
        # If unclear, use LLM for classification
        if task_type == TaskType.UNKNOWN:
            task_type = await self._llm_route(message)
        
        # Extract relevant context based on task type
        context = await self._extract_context(message, task_type)
        
        return task_type, context
    
    def _pattern_route(self, message: str) -> TaskType:
        """Fast pattern-based routing"""
        message_lower = message.lower()
        
        # Check for expense patterns
        for pattern in self.patterns[TaskType.EXPENSE]:
            if re.search(pattern, message, re.IGNORECASE):
                return TaskType.EXPENSE
        
        # Check for appointment patterns
        for pattern in self.patterns[TaskType.REMINDER]:
            if re.search(pattern, message, re.IGNORECASE):
                return TaskType.REMINDER
        
        # Check for summary requests
        summary_keywords = ['summary', 'report', 'total', 'spent', 'how much']
        if any(keyword in message_lower for keyword in summary_keywords):
            return TaskType.SUMMARY_REQUEST
        
        return TaskType.UNKNOWN
    
    async def _llm_route(self, message: str) -> TaskType:
        """LLM-based routing for ambiguous cases"""
        prompt = f"""
        Classify this user message into one of these categories:
        - EXPENSE: Recording money spent (contains amount and description)
        - REMINDER: Scheduling or time-based events
        - SUMMARY_REQUEST: Asking for reports, totals, or summaries
        - GENERAL_QUERY: Questions or general conversation
        
        Message: "{message}"
        
        Respond with only the category name.
        """
        
        try:
            response = await self.llm.ainvoke(prompt)
            category = response.content.strip().upper()
            
            for task_type in TaskType:
                if task_type.name == category:
                    return task_type
        except:
            pass
        
        return TaskType.GENERAL_QUERY
    
    async def _extract_context(self, message: str, task_type: TaskType) -> Dict:
        """Extract relevant context based on task type"""
        context = {
            "original_message": message,
            "task_type": task_type.value
        }
        
        if task_type == TaskType.EXPENSE:
            context.update(self._extract_expense_context(message))
        elif task_type == TaskType.REMINDER:  # Updated from APPOINTMENT
            context.update(self._extract_reminder_context(message))
        
        return context
    
    def _extract_expense_context(self, message: str) -> Dict:
        """Extract expense-specific context"""
        # Extract amount
        amount_patterns = [
            r'\$(\d+(?:\.\d{2})?)',
            r'(\d+(?:\.\d{2})?)\s*(?:dollars?|bucks?|\$)'
        ]
        
        amount = None
        for pattern in amount_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                try:
                    amount = float(match.group(1))
                    break
                except:
                    continue
        
        return {
            "has_amount": amount is not None,
            "estimated_amount": amount,
            "urgency": "high" if amount and amount > 100 else "normal"
        }
    
    def _extract_reminder_context(self, message: str) -> Dict:
        """Extract reminder-specific context"""
        
        # Enhanced time patterns for reminders
        time_patterns = [
            r'(\d{1,2}(?::\d{2})?)\s*(am|pm)',          # 3pm, 3:30pm
            r'at\s+(\d{1,2}(?::\d{2})?)',               # at 15:30, at 3
            r'(\d{1,2}):(\d{2})',                       # 15:30, 03:45
            r'in\s+(\d+)\s*hours?',                     # in 2 hours
            r'in\s+(\d+)\s*minutes?',                   # in 30 minutes
        ]
        
        # Enhanced date patterns for reminders
        date_patterns = [
            r'(today|tomorrow)',                        # today, tomorrow
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',  # weekdays
            r'day after tomorrow',                      # day after tomorrow
            r'next\s+(week|month)',                     # next week, next month
            r'in\s+(\d+)\s*days?',                      # in 3 days
            r'in\s+(\d+)\s*weeks?',                     # in 2 weeks
            r'(\d{1,2})/(\d{1,2})',                     # 12/25, 3/15
            r'(\d{4})-(\d{1,2})-(\d{1,2})',            # 2025-07-15
        ]
        
        # Reminder type indicators
        reminder_triggers = [
            r'remind me',
            r'don\'t forget',
            r'remember to',
            r'set reminder',
            r'reminder:',
            r'remind me to',
            r'remind me about'
        ]
        
        # Priority indicators
        priority_indicators = {
            'urgent': [r'urgent', r'asap', r'immediately', r'critical', r'emergency'],
            'high': [r'important', r'soon', r'today', r'deadline', r'must'],
            'low': [r'sometime', r'when you can', r'eventually', r'maybe']
        }
        
        # Reminder type keywords
        type_keywords = {
            'task': [r'call', r'email', r'buy', r'pick up', r'finish', r'complete', r'do', r'send', r'submit'],
            'event': [r'meeting', r'dinner', r'lunch', r'appointment', r'party', r'concert', r'game'],
            'deadline': [r'deadline', r'due', r'payment', r'bill', r'submit', r'file', r'pay'],
            'habit': [r'daily', r'weekly', r'every day', r'routine', r'habit']
        }
        
        message_lower = message.lower()
        
        # Check for time presence
        has_time = any(re.search(pattern, message, re.IGNORECASE) for pattern in time_patterns)
        
        # Check for date presence
        has_date = any(re.search(pattern, message, re.IGNORECASE) for pattern in date_patterns)
        
        # Check for reminder triggers
        has_reminder_trigger = any(re.search(trigger, message, re.IGNORECASE) for trigger in reminder_triggers)
        
        # Determine priority
        detected_priority = "medium"  # default
        for priority, keywords in priority_indicators.items():
            if any(re.search(keyword, message, re.IGNORECASE) for keyword in keywords):
                detected_priority = priority
                break
        
        # Determine reminder type
        detected_type = "general"  # default
        for type_name, keywords in type_keywords.items():
            if any(re.search(keyword, message, re.IGNORECASE) for keyword in keywords):
                detected_type = type_name
                break
        
        # Check for relative time expressions
        has_relative_time = any(re.search(pattern, message, re.IGNORECASE) for pattern in [
            r'in\s+\d+\s*(?:minutes?|hours?|days?|weeks?)',
            r'later today',
            r'this\s+(?:morning|afternoon|evening)',
            r'tonight'
        ])
        
        # Determine urgency based on multiple factors
        urgency = "normal"
        if any(keyword in message_lower for keyword in ['today', 'now', 'asap', 'urgent', 'immediately']):
            urgency = "high"
        elif any(keyword in message_lower for keyword in ['in.*hour', 'in.*minute', 'later today']):
            urgency = "medium"
        elif any(keyword in message_lower for keyword in ['sometime', 'eventually', 'when you can']):
            urgency = "low"
        
        # Check for completion keywords (for marking reminders as done)
        has_completion_intent = any(re.search(pattern, message, re.IGNORECASE) for pattern in [
            r'mark.*(?:done|complete|finished)',
            r'completed?',
            r'finished?',
            r'done with'
        ])
        
        # Check for query intent (asking about reminders)
        has_query_intent = any(re.search(pattern, message, re.IGNORECASE) for pattern in [
            r'show.*reminder',
            r'what.*reminder',
            r'list.*reminder',
            r'due.*today',
            r'due.*tomorrow',
            r'what.*due'
        ])
        
        return {
            "has_time": has_time,
            "has_date": has_date,
            "has_relative_time": has_relative_time,
            "has_reminder_trigger": has_reminder_trigger,
            "has_completion_intent": has_completion_intent,
            "has_query_intent": has_query_intent,
            "detected_priority": detected_priority,
            "detected_type": detected_type,
            "urgency": urgency,
            "complexity": self._assess_reminder_complexity(message, has_time, has_date, has_relative_time)
        }

    def _assess_reminder_complexity(self, message: str, has_time: bool, has_date: bool, has_relative_time: bool) -> str:
        """Assess the complexity of the reminder request"""
        complexity_score = 0
        
        # Add points for various complexity factors
        if has_time:
            complexity_score += 1
        if has_date:
            complexity_score += 1
        if has_relative_time:
            complexity_score += 1
        
        # Check for multiple components
        if len(message.split()) > 8:
            complexity_score += 1
        
        # Check for complex time expressions
        complex_patterns = [
            r'every\s+(?:day|week|month)',      # recurring
            r'until\s+',                       # duration
            r'between\s+.*and',                # time ranges
            r'starting\s+',                    # start dates
        ]
        
        if any(re.search(pattern, message, re.IGNORECASE) for pattern in complex_patterns):
            complexity_score += 2
        
        # Determine complexity level
        if complexity_score >= 4:
            return "high"
        elif complexity_score >= 2:
            return "medium"
        else:
            return "simple"