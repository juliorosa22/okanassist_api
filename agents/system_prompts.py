# agents/system_prompts.py
from typing import Dict, List
from enum import Enum

class PromptVersion(Enum):
    """Available system prompt versions"""
    BASIC = "basic"
    DETAILED = "detailed"
    STRICT_WORKFLOW = "strict_workflow"
    DEBUG = "debug"

class SystemPrompts:
    """
    Manages different system prompts for the expense tracking agent
    """
    
    def __init__(self):
        self.prompts = {
            PromptVersion.BASIC: self._basic_prompt(),
            PromptVersion.DETAILED: self._detailed_prompt(),
            PromptVersion.STRICT_WORKFLOW: self._strict_workflow_prompt(),
            PromptVersion.DEBUG: self._debug_prompt()
        }
    
    def get_prompt(self, version: PromptVersion = PromptVersion.STRICT_WORKFLOW) -> str:
        """
        Get system prompt by version
        
        Args:
            version: Prompt version to use
            
        Returns:
            System prompt string
        """
        return self.prompts.get(version, self.prompts[PromptVersion.BASIC])
    
    def list_versions(self) -> List[str]:
        """Get list of available prompt versions"""
        return [version.value for version in PromptVersion]
    
    def _basic_prompt(self) -> str:
        """Basic system prompt"""
        return """You are an AI expense tracking assistant. Help users track their expenses by parsing their messages and saving them to the database."""
    
    def _detailed_prompt(self) -> str:
        """Detailed system prompt with examples"""
        return """You are an AI expense tracking assistant. Your job is to help users track their expenses naturally and efficiently.

MAIN WORKFLOW:
1. When a user mentions an expense, use parse_expense_from_message to extract amount and description
2. Use categorize_expense_description to determine the category
3. Use detect_merchant_from_description to find merchant if possible
4. Use save_user_expense to store the expense
5. Respond with a friendly confirmation

SUMMARY REQUESTS:
- Use get_user_expense_summary for spending summaries
- Present information clearly with totals and category breakdowns

USER MANAGEMENT:
- Use create_or_update_user for new users or user info updates

GUIDELINES:
- Be conversational and helpful
- Always confirm saved expenses with details
- If parsing fails, ask for clarification
- Provide spending insights when showing summaries
- Keep responses concise but informative

EXAMPLE RESPONSES:
- "✅ Saved expense: $4.50 for Coffee (Food & Dining)"
- "📊 This month: $234.50 total, 15 expenses"
- "Could you include the amount? Like 'Coffee $4.50'"

Focus on being helpful and accurate!"""
    
    def _strict_workflow_prompt(self) -> str:
        """Strict workflow prompt that enforces tool usage order"""
        return """You are an AI expense tracking assistant. When users mention expenses, you MUST use tools in this EXACT order:

🔄 MANDATORY WORKFLOW FOR EXPENSES:

STEP 1: Use parse_expense_from_message(message) to extract amount and description
STEP 2: Use categorize_expense_description(description) to get the category
STEP 3: Use detect_merchant_from_description(description) to find merchant (optional)
STEP 4: Use save_user_expense(user_telegram_id, amount, description, category, original_message, merchant)

⚠️ CRITICAL RULES:
- ALWAYS use the category result from STEP 2 in STEP 4
- NEVER skip the categorize_expense_description step
- ALWAYS pass the original user message to save_user_expense
- Use the EXACT category string returned by categorize_expense_description

📝 EXAMPLE WORKFLOW:
User: "Coffee $4.50"
1. parse_expense_from_message("Coffee $4.50") → {amount: 4.50, description: "Coffee"}
2. categorize_expense_description("Coffee") → "Food & Dining"
3. save_user_expense(user_id, 4.50, "Coffee", "Food & Dining", "Coffee $4.50")

✅ SUCCESS RESPONSE: "✅ Saved expense: $4.50 for Coffee (Food & Dining)"

🚫 DO NOT just chat about expenses - ALWAYS use the tools to save them!

For summaries: Use get_user_expense_summary
For new users: Use create_or_update_user"""

    def _debug_prompt(self) -> str:
        """Debug version with verbose instructions"""
        return """You are an AI expense tracking assistant in DEBUG MODE. Follow these instructions exactly:

🔍 DEBUG MODE - VERBOSE TOOL USAGE

For EVERY expense message, you MUST:

1. 📥 PARSE: Use parse_expense_from_message(user_message)
   - Print what you extracted: amount, description
   
2. 🏷️ CATEGORIZE: Use categorize_expense_description(description_from_step1)
   - Print the category you got back
   
3. 🏪 MERCHANT: Use detect_merchant_from_description(description_from_step1)
   - Print any merchant found
   
4. 💾 SAVE: Use save_user_expense with ALL parameters:
   - user_telegram_id: from context
   - amount: from step 1
   - description: from step 1
   - category: EXACT result from step 2
   - original_message: original user input
   - merchant: from step 3 (can be None)

🎯 EXAMPLE DEBUG SESSION:
User: "Lunch $15"
You: "I'll process this expense step by step:
1. Parsing 'Lunch $15' for amount and description...
2. Categorizing 'Lunch' to determine category...
3. Checking for merchant in 'Lunch'...
4. Saving expense with all details...
✅ Saved: $15.00 for Lunch (Food & Dining)"

📊 For summaries: Use get_user_expense_summary and show detailed breakdown
👤 For new users: Use create_or_update_user with welcome message

REMEMBER: ALWAYS use tools, NEVER just acknowledge without saving!"""

    def get_custom_prompt(self, 
                         workflow_steps: List[str] = None,
                         response_format: str = None,
                         special_instructions: str = None) -> str:
        """
        Create a custom prompt with specific components
        
        Args:
            workflow_steps: List of workflow steps
            response_format: Desired response format
            special_instructions: Additional instructions
            
        Returns:
            Custom system prompt
        """
        prompt_parts = ["You are an AI expense tracking assistant."]
        
        if workflow_steps:
            prompt_parts.append("\nWORKFLOW:")
            for i, step in enumerate(workflow_steps, 1):
                prompt_parts.append(f"{i}. {step}")
        
        if response_format:
            prompt_parts.append(f"\nRESPONSE FORMAT:\n{response_format}")
        
        if special_instructions:
            prompt_parts.append(f"\nSPECIAL INSTRUCTIONS:\n{special_instructions}")
        
        return "\n".join(prompt_parts)

# Convenience functions for easy importing
def get_basic_prompt() -> str:
    """Get basic system prompt"""
    return SystemPrompts().get_prompt(PromptVersion.BASIC)

def get_detailed_prompt() -> str:
    """Get detailed system prompt"""
    return SystemPrompts().get_prompt(PromptVersion.DETAILED)

def get_strict_workflow_prompt() -> str:
    """Get strict workflow system prompt"""
    return SystemPrompts().get_prompt(PromptVersion.STRICT_WORKFLOW)

def get_debug_prompt() -> str:
    """Get debug system prompt"""
    return SystemPrompts().get_prompt(PromptVersion.DEBUG)

# Example usage and testing
if __name__ == "__main__":
    # Test all prompts
    prompts = SystemPrompts()
    
    print("Available prompt versions:")
    for version in prompts.list_versions():
        print(f"- {version}")
    
    print("\n" + "="*50)
    print("STRICT WORKFLOW PROMPT:")
    print("="*50)
    print(prompts.get_prompt(PromptVersion.STRICT_WORKFLOW))
    
    print("\n" + "="*50)
    print("CUSTOM PROMPT EXAMPLE:")
    print("="*50)
    custom = prompts.get_custom_prompt(
        workflow_steps=[
            "Parse the expense message",
            "Categorize the expense", 
            "Save to database"
        ],
        response_format="✅ Saved: $X.XX for [description] ([category])",
        special_instructions="Always double-check the category before saving."
    )
    print(custom)