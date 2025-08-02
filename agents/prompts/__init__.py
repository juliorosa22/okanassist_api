"""
Centralized prompt management for all agents
Optimized for minimal token usage and maximum efficiency
"""

from .orchestrator_prompts import OrchestratorPrompts, FallbackResponses
from .expense_prompts import ExpensePrompts, ExpenseFallbacks
from .reminder_prompts import ReminderPrompts, ReminderFallbacks

__all__ = ['OrchestratorPrompts', 'FallbackResponses','ExpensePrompts', 'ExpenseFallbacks',
           'ReminderPrompts', 'ReminderFallbacks']