# agents/expense_agent.py
from typing import Dict
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
#from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage

from .tools.expense_tools import (
    parse_expense_from_message,
    categorize_expense_description,
    save_user_expense,
    get_user_expense_summary,
    create_or_update_user,
    get_expense_categories,
    detect_merchant_from_description,
    set_database
)

class ExpenseAgent:
    """
    LangGraph agent for expense tracking with intelligent conversation flow
    """
    
    def __init__(self, groq_api_key: str, database_url: str, database_instance):
        self.groq_api_key = groq_api_key
        self.database_url = database_url
        
        # Set database for tools
        set_database(database_instance)
        
        # Initialize LLM
        self.llm = ChatGroq(
            model="llama3-8b-8192",
            api_key=groq_api_key,
            temperature=0
        )
        
        # Define tools available to the agent
        self.tools = [
            parse_expense_from_message,
            categorize_expense_description,
            save_user_expense,
            get_user_expense_summary,
            create_or_update_user,
            get_expense_categories,
            detect_merchant_from_description
        ]
        
        # Create agent with memory
        self.memory = MemorySaver() #PostgresSaver.from_conn_string(database_url)
        
        # System message for the agent
        system_message = """You are an AI expense tracking assistant. When users mention expenses, you MUST use tools in this EXACT order:

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
        
        # Create the agent
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            checkpointer=self.memory,
            prompt=system_message
        )
    
    async def process_expense(self, message: str, user_telegram_id: str, 
                        user_info: Dict = None) -> str:
        
        return await self._handle_expense_directly(message, user_telegram_id, user_info)
        

    async def _handle_expense_directly(self, message: str, user_telegram_id: str, user_info: Dict = None) -> str:
        """Handle expense parsing with guaranteed sequential execution"""
        try:
            # Step 1: Parse
            parse_result = await parse_expense_from_message.ainvoke({"message": message})
            if not parse_result.get("success"):
                return f"❌ {parse_result.get('error', 'Could not parse expense')}"
            
            # Step 2: Categorize
            category = await categorize_expense_description.ainvoke({"description": parse_result["description"]})
            
            # Step 3: Detect merchant (optional)
            merchant = await detect_merchant_from_description.ainvoke({"description": parse_result["description"]})
            
            # Step 4: Save with all data
            save_result = await save_user_expense.ainvoke({
                "user_telegram_id": user_telegram_id,
                "amount": parse_result["amount"],
                "description": parse_result["description"],
                "category": category,
                "original_message": message,
                "merchant": merchant
            })
            
            if save_result.get("success"):
                return f"✅ Saved expense: ${save_result['amount']:.2f} for {save_result['description']} ({save_result['category']})"
            else:
                return f"❌ Failed to save: {save_result.get('error')}"
                
        except Exception as e:
            return f"❌ Error processing expense: {str(e)}"

    async def get_conversation_summary(self, user_telegram_id: str) -> str:
        """
        Get a summary of the user's expense tracking activity
        
        Args:
            user_telegram_id: User's Telegram ID
            
        Returns:
            Summary message
        """
        config = {"configurable": {"thread_id": user_telegram_id}}
        
        summary_request = "Please provide a summary of my expense tracking activity and spending patterns."
        
        try:
            response = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=summary_request)]},
                config
            )
            
            return response["messages"][-1].content
            
        except Exception as e:
            return f"❌ Error getting summary: {str(e)}"
    
    async def handle_natural_query(self, query: str, user_telegram_id: str) -> str:
        """
        Handle natural language queries about expenses
        
        Args:
            query: User's natural language query
            user_telegram_id: User's Telegram ID
            
        Returns:
            Agent's response
        """
        config = {"configurable": {"thread_id": user_telegram_id}}
        
        try:
            response = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=query)]},
                config
            )
            
            return response["messages"][-1].content
            
        except Exception as e:
            return f"❌ Error processing query: {str(e)}"
            
        except Exception as e:
            return f"❌ Sorry, I encountered an error: {str(e)}"
    
    async def initialize_user(self, user_telegram_id: str, username: str = None,
                            first_name: str = None, last_name: str = None) -> str:
        """
        Initialize a new user
        
        Args:
            user_telegram_id: User's Telegram ID
            username: Username
            first_name: First name
            last_name: Last name
            
        Returns:
            Welcome message
        """
        config = {"configurable": {"thread_id": user_telegram_id}}
        
        init_message = f"""New user setup:
- Telegram ID: {user_telegram_id}
- Username: {username}
- Name: {first_name} {last_name or ''}

Please create this user and send a welcome message explaining how to track expenses."""
        
        try:
            response = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=init_message)]},
                config
            )
            
            return response["messages"][-1].content
        except Exception as e:
            return f"❌ Error initializing user: {str(e)}"
