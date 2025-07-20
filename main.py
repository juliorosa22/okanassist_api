# main.py
import asyncio
import sys
from config import Config
from core.database import Database
from agents.orchestrator_agent import OrchestratorAgent
from bot.telegram_bot import TelegramBot

class PersonalAssistantApp:
    """
    Main application orchestrating all personal assistant components
    """
    
    def __init__(self):
        self.config = None
        self.database = None
        self.orchestrator = None
        self.telegram_bot = None
    
    async def initialize(self):
        """Initialize all application components"""
        print("🚀 Initializing Personal Assistant...")
        
        # Validate configuration
        self.config = Config()
        self.config.validate()
        
        # Initialize database
        print("📊 Connecting to database...")
        self.database = Database(self.config.DATABASE_URL)
        await self.database.connect()
        
        # Initialize orchestrator with all agents
        print("🧠 Setting up AI orchestrator...")
        self.orchestrator = OrchestratorAgent(
            groq_api_key=self.config.GROQ_API_KEY,
            database_url=self.config.DATABASE_URL,
            database_instance=self.database
        )
        
        # Initialize Telegram bot
        print("🤖 Setting up Telegram bot...")
        self.telegram_bot = TelegramBot(
            token=self.config.TELEGRAM_BOT_TOKEN,
            groq_api_key=self.config.GROQ_API_KEY,
            database_url=self.config.DATABASE_URL,
            database_instance=self.database
        )
        self.telegram_bot.setup()
        
        print("✅ Initialization complete!")
    
    async def run(self):
        """Run the application"""
        try:
            await self.initialize()
            
            print("\n" + "="*70)
            print("🎉 PERSONAL ASSISTANT BOT IS RUNNING")
            print("="*70)
            print("📱 Bot ready to receive messages on Telegram")
            print("🧠 AI-powered multi-task processing with intelligent routing")
            print("💾 PostgreSQL database for reliable storage")
            print("🔮 Expandable architecture for future capabilities")
            print("\n💡 Users can now:")
            print("   💰 Track expenses: 'Coffee $4.50'")
            print("   🔔 Set reminders: 'Remind me to call mom tomorrow 3pm'")
            print("   📊 Get summaries: /summary, /expenses, /reminders")
            print("   ❓ Ask questions naturally")
            print("   ✅ Manage reminders: 'What's due today?'")
            print("\n🤖 Available Commands:")
            print("   /start   - Welcome and setup")
            print("   /help    - Show help and examples") 
            print("   /summary - General summary")
            print("   /expenses - Expense summary")
            print("   /reminders - Show reminders")
            print("   /due     - Show due reminders")
            print("\n🛑 Press Ctrl+C to stop")
            print("="*70)
            
            # Start the bot
            await self.telegram_bot.run()
            
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested...")
            await self.shutdown()
        except Exception as e:
            print(f"❌ Application error: {e}")
            await self.shutdown()
            raise
    
    async def shutdown(self):
        """Gracefully shutdown all components"""
        print("🛑 Shutting down components...")
        
        if self.telegram_bot:
            await self.telegram_bot.stop()
            print("✅ Telegram bot stopped")
        
        if self.database:
            await self.database.close()
            print("✅ Database disconnected")
        
        print("👋 Personal Assistant shutdown complete")

async def test_components():
    """Test all components independently"""
    print("🧪 Testing Personal Assistant components...")
    
    try:
        # Test configuration
        print("Testing configuration...")
        config = Config()
        config.validate()
        print("✅ Configuration OK")
        
        # Test database
        print("Testing database connection...")
        database = Database(config.DATABASE_URL)
        await database.connect()
        print("✅ Database OK")
        
        # Test orchestrator initialization
        print("Testing AI orchestrator...")
        orchestrator = OrchestratorAgent(
            groq_api_key=config.GROQ_API_KEY,
            database_url=config.DATABASE_URL,
            database_instance=database
        )
        print("✅ Orchestrator OK")
        
        # Test expense processing
        print("Testing expense parsing...")
        test_expense = "Coffee $4.50"
        response = await orchestrator.process_message(test_expense, "test_user_123")
        print(f"Test expense: '{test_expense}'")
        print(f"Response: {response[:100]}...")
        print("✅ Expense processing OK")
        
        # Test reminder processing
        print("Testing reminder parsing...")
        test_reminder = "Remind me to call mom tomorrow at 3pm"
        response = await orchestrator.process_message(test_reminder, "test_user_123")
        print(f"Test reminder: '{test_reminder}'")
        print(f"Response: {response[:100]}...")
        print("✅ Reminder processing OK")
        
        # Test routing
        print("Testing message routing...")
        test_messages = [
            "Lunch $12.50",  # Should route to expense
            "Don't forget dinner tonight",  # Should route to reminder
            "Show me my summary",  # Should route to summary
            "Hello there"  # Should route to general
        ]
        
        for msg in test_messages:
            task_type, context = await orchestrator.router.route_message(msg, "test_user_123")
            print(f"  '{msg}' → {task_type.value}")
        
        print("✅ Message routing OK")
        
        await database.close()
        print("\n🎉 All tests passed! Personal Assistant ready to run.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

async def test_individual_component(component: str):
    """Test individual components"""
    config = Config()
    config.validate()
    database = Database(config.DATABASE_URL)
    await database.connect()
    user_id_test="7461277257"
    
    try:
        if component == "expense":
            print("🧪 Testing expense agent...")
            from agents.expense_agent import ExpenseAgent
            agent = ExpenseAgent(config.GROQ_API_KEY, config.DATABASE_URL, database)
            response = await agent.process_expense("Coffee $4.50", user_id_test)
            print(f"Response: {response}")
            
        elif component == "reminder":
            print("🧪 Testing reminder agent...")
            from agents.reminder_agent import ReminderAgent
            agent = ReminderAgent(config.GROQ_API_KEY, database)
            response = await agent.process_reminder("Remind me to call mom tomorrow", user_id_test)
            print(f"Response: {response}")
            
        elif component == "router":
            print("🧪 Testing router...")
            from agents.router_agent import RouterAgent
            router = RouterAgent(config.GROQ_API_KEY)
            
            test_cases = [
                "Coffee $5.50",
                "Remind me about meeting",
                "Show my expenses",
                "Hello"
            ]
            
            for msg in test_cases:
                task_type, context = await router.route_message(msg, user_id_test)
                print(f"'{msg}' → {task_type.value} | Context: {context.get('urgency', 'N/A')}")
                
        else:
            print(f"❌ Unknown component: {component}")
            return False
            
    finally:
        await database.close()
    
    return True

def main():
    """Main entry point"""
    
    # Check for test mode
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            result = asyncio.run(test_components())
            sys.exit(0 if result else 1)
        elif sys.argv[1] == "test-component" and len(sys.argv) > 2:
            component = sys.argv[2]
            result = asyncio.run(test_individual_component(component))
            sys.exit(0 if result else 1)
        elif sys.argv[1] == "--help":
            print("Personal Assistant Bot")
            print("\nUsage:")
            print("  python main.py                    # Run the bot")
            print("  python main.py test               # Test all components")
            print("  python main.py test-component <name>  # Test specific component")
            print("\nComponents:")
            print("  expense   # Test expense tracking")
            print("  reminder  # Test reminder system") 
            print("  router    # Test message routing")
            print("\nExamples:")
            print("  python main.py test-component expense")
            print("  python main.py test-component router")
            sys.exit(0)
    
    # Run the application
    app = PersonalAssistantApp()
    asyncio.run(app.run())

if __name__ == "__main__":
    main()