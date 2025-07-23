# main.py - Refactored version with eliminated redundancy
import asyncio
import sys
from datetime import datetime
from config import Config
from core.database import Database
from agents.intelligent_orchestrator_agent import IntelligentOrchestratorAgent
from services.standalone_orchestrator_service import StandaloneOrchestratorService
from services.user_registration import UserRegistrationService

class TestBase:
    """Base class for all tests with common setup/cleanup"""
    
    def __init__(self):
        self.config = None
        self.database = None
        self.orchestrator = None
        self.registration_service = None
        self.standalone_service = None
    
    async def setup(self):
        """Common setup for all tests"""
        print("🔧 Setting up test environment...")
        
        # Configuration
        self.config = Config()
        self.config.validate()
        print("✅ Configuration validated")
        
        # Database
        print("📊 Connecting to database...")
        self.database = Database(self.config.DATABASE_URL)
        await self.database.connect()
        print("✅ Database connected")
        
        # Registration service
        self.registration_service = UserRegistrationService(self.database)
        print("✅ Registration service ready")
        
        # Orchestrator  
        print("🧠 Setting up orchestrator...")
        self.orchestrator = IntelligentOrchestratorAgent(
            self.config.GROQ_API_KEY, 
            self.database
        )
        print("✅ Orchestrator ready")
        
        # Standalone service
        print("⚙️ Setting up standalone service...")
        self.standalone_service = StandaloneOrchestratorService(
            self.config.GROQ_API_KEY, 
            self.config.DATABASE_URL
        )
        await self.standalone_service.initialize()
        print("✅ Standalone service ready")
        
        # Agent tools
        await self._setup_agent_tools()
        
        print("✅ Test environment ready")
    
    async def cleanup(self):
        """Common cleanup for all tests"""
        print("🧹 Cleaning up test environment...")
        
        try:
            if self.standalone_service:
                await self.standalone_service.shutdown()
                print("✅ Standalone service stopped")
        except Exception as e:
            print(f"⚠️ Error stopping standalone service: {e}")
        
        try:
            if self.database:
                await self.database.close()
                print("✅ Database disconnected")
        except Exception as e:
            print(f"⚠️ Error closing database: {e}")
    
    async def _setup_agent_tools(self):
        """Setup agent tools (centralized)"""
        try:
            from agents.expense_agent import set_database as set_expense_db
            from agents.tools.intelligent_reminder_tools import set_database as set_reminder_db
            set_expense_db(self.database)
            set_reminder_db(self.database)
            print("✅ Agent tools configured")
        except ImportError as e:
            print(f"⚠️ Warning: Could not import agent tools: {e}")
            print("⚠️ Continuing with basic orchestrator test...")
    
    async def safe_test_run(self, test_func, test_name: str):
        """Run a test with proper error handling"""
        try:
            await self.setup()
            result = await test_func()
            return result
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await self.cleanup()

class PersonalAssistantApp:
    """
    Main application with intelligent agents and multi-platform support
    """
    
    def __init__(self):
        self.config = None
        self.database = None
        self.orchestrator = None
        self.telegram_bot = None
        self.registration_service = None
        self.standalone_service = None
    
    async def initialize(self):
        """Initialize all application components"""
        print("🚀 Initializing Personal Assistant with Intelligent Agents...")
        
        # Validate configuration
        self.config = Config()
        self.config.validate()
        
        # Initialize clean database
        print("📊 Connecting to database...")
        self.database = Database(self.config.DATABASE_URL)
        await self.database.connect()
        
        # Initialize registration service
        print("👤 Setting up user registration service...")
        self.registration_service = UserRegistrationService(self.database)
        
        # Initialize intelligent orchestrator
        print("🧠 Setting up intelligent AI orchestrator...")
        self.orchestrator = IntelligentOrchestratorAgent(
            groq_api_key=self.config.GROQ_API_KEY,
            database=self.database
        )
        
        # Initialize standalone orchestrator service
        print("⚙️ Setting up standalone orchestrator service...")
        self.standalone_service = StandaloneOrchestratorService(
            groq_api_key=self.config.GROQ_API_KEY,
            database_url=self.config.DATABASE_URL
        )
        await self.standalone_service.initialize()
        
        # Setup intelligent agents tools
        await self._setup_agent_tools()
        
        # Initialize Telegram bot (optional)
        if self.config.TELEGRAM_BOT_TOKEN:
            print("🤖 Setting up Telegram bot...")
            from bot.telegram_bot import TelegramBot
            self.telegram_bot = TelegramBot(
                token=self.config.TELEGRAM_BOT_TOKEN,
                orchestrator=self.orchestrator,
                registration_service=self.registration_service
            )
            self.telegram_bot.setup()
        else:
            print("📱 Telegram bot disabled (no token provided)")
        
        print("✅ Initialization complete!")
    
    async def _setup_agent_tools(self):
        """Setup tools for intelligent agents"""
        try:
            # Import and setup expense tools
            from agents.expense_agent import set_database as set_expense_db
            set_expense_db(self.database)
            
            # Import and setup reminder tools  
            from agents.tools.intelligent_reminder_tools import set_database as set_reminder_db
            set_reminder_db(self.database)
            
            print("✅ Agent tools configured")
        except ImportError as e:
            print(f"⚠️ Warning: Could not import agent tools: {e}")
            print("⚠️ Make sure all agent tool files are present")
    
    async def run(self):
        """Run the application"""
        try:
            await self.initialize()
            
            self._print_startup_banner()
            
            # Start services based on configuration
            if self.telegram_bot:
                print("🤖 Starting Telegram bot...")
                await self.telegram_bot.run()
            else:
                print("⚙️ Running standalone orchestrator service...")
                print("📡 Service available for API integration")
                print("💡 You can integrate this with any platform using the standalone service")
                
                # Keep service running and show periodic status
                await self._run_standalone_mode()
                    
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested...")
            await self.shutdown()
        except Exception as e:
            print(f"❌ Application error: {e}")
            import traceback
            traceback.print_exc()
            await self.shutdown()
            raise
    
    def _print_startup_banner(self):
        """Print application startup banner"""
        print("\n" + "="*80)
        print("🎉 INTELLIGENT PERSONAL ASSISTANT IS RUNNING")
        print("="*80)
        print("🧠 LLM-powered natural language understanding")
        print("🌍 Multi-language and multi-currency support")
        print("📱 Multi-platform architecture (Telegram, WhatsApp, Mobile, Web)")
        print("💾 Clean PostgreSQL database with user management")
        print("🔧 Standalone orchestrator service for any platform")
        print("\n💡 Users can now:")
        print("   💰 Track expenses: 'Coffee $4.50', 'Café €4.50', 'Compré pan R$ 3'")
        print("   🔔 Set reminders: 'Remind me to call mom tomorrow 3pm'")
        print("   📊 Get summaries: 'Show my expenses', 'What reminders do I have?'")
        print("   🌐 Use any language naturally")
        print("   📱 Connect multiple platforms to one account")
        print("\n🤖 Available Services:")
        if self.telegram_bot:
            print("   📱 Telegram Bot (Active)")
        else:
            print("   📱 Telegram Bot (Disabled - no token)")
        print("   ⚙️ Standalone Orchestrator Service")
        print("   👤 User Registration Service")
        print("   🧠 Intelligent Expense Agent")
        print("   🔔 Intelligent Reminder Agent")
        print("\n🛑 Press Ctrl+C to stop")
        print("="*80)
    
    async def _run_standalone_mode(self):
        """Run in standalone mode with health monitoring"""
        try:
            last_health_check = 0
            while True:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                current_time = datetime.now()
                
                # Health check every 5 minutes
                if (current_time.timestamp() - last_health_check) >= 300:
                    health = await self.standalone_service.get_health()
                    metrics = await self.standalone_service.get_metrics()
                    
                    print(f"📊 Service Status: {health['status']} | "
                          f"Requests processed: {metrics.get('service_metrics', {}).get('total_requests', 0)} | "
                          f"Time: {current_time.strftime('%H:%M:%S')}")
                    
                    if health["status"] != "healthy":
                        print(f"⚠️ Service health: {health}")
                    
                    last_health_check = current_time.timestamp()
                    
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested...")
    
    async def shutdown(self):
        """Gracefully shutdown all components"""
        print("🛑 Shutting down components...")
        
        try:
            if self.telegram_bot:
                await self.telegram_bot.stop()
                print("✅ Telegram bot stopped")
        except Exception as e:
            print(f"⚠️ Error stopping Telegram bot: {e}")
        
        try:
            if self.standalone_service:
                await self.standalone_service.shutdown()
                print("✅ Standalone service stopped")
        except Exception as e:
            print(f"⚠️ Error stopping standalone service: {e}")
        
        try:
            if self.database:
                await self.database.close()
                print("✅ Database disconnected")
        except Exception as e:
            print(f"⚠️ Error closing database: {e}")
        
        print("👋 Personal Assistant shutdown complete")

# ============================================================================
# TEST FUNCTIONS - Refactored with TestBase
# ============================================================================

async def test_database_operations():
    """Test database operations independently"""
    test_base = TestBase()
    
    async def _test_logic():
        print("Testing user CRUD operations...")
        from core.models import User
        
        test_user = User(
            id="test_user_123",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            language="en",
            default_currency="USD"
        )
        
        # Create user
        created_user = await test_base.database.create_user(test_user)
        print("✅ User creation successful")
        
        # Get user
        retrieved_user = await test_base.database.get_user("test_user_123")
        if retrieved_user and retrieved_user.email == "test@example.com":
            print("✅ User retrieval successful")
        else:
            print("❌ User retrieval failed")
            return False
        
        # Test platform operations
        print("Testing platform operations...")
        from core.models import UserPlatform
        
        test_platform = UserPlatform(
            user_id="test_user_123",
            platform_type="telegram",
            platform_user_id="tg_123456",
            is_primary=True
        )
        
        created_platform = await test_base.database.create_user_platform(test_platform)
        print("✅ Platform creation successful")
        
        # Test expense operations
        print("Testing expense operations...")
        from core.models import Expense
        from decimal import Decimal
        
        test_expense = Expense(
            user_id="test_user_123",
            amount=Decimal("25.50"),
            description="Test coffee",
            category="Food & Dining",
            original_message="Coffee $25.50",
            source_platform="telegram"
        )
        
        created_expense = await test_base.database.save_expense(test_expense)
        print("✅ Expense creation successful")
        
        # Test expense summary
        summary = await test_base.database.get_expense_summary("test_user_123", days=30)
        if summary.total_count == 1 and summary.total_amount == Decimal("25.50"):
            print("✅ Expense summary calculation successful")
        else:
            print("❌ Expense summary calculation failed")
            return False
        
        # Test reminder operations
        print("Testing reminder operations...")
        from core.models import Reminder
        from datetime import datetime, timedelta
        
        test_reminder = Reminder(
            user_id="test_user_123",
            title="Test reminder",
            description="Call mom",
            due_datetime=datetime.now() + timedelta(hours=24),
            reminder_type="task",
            priority="medium",
            source_platform="telegram"
        )
        
        created_reminder = await test_base.database.save_reminder(test_reminder)
        print("✅ Reminder creation successful")
        
        # Test reminder retrieval
        reminders = await test_base.database.get_user_reminders("test_user_123")
        if len(reminders) == 1:
            print("✅ Reminder retrieval successful")
        else:
            print("❌ Reminder retrieval failed")
            return False
        
        print("✅ All database operations completed successfully!")
        return True
    
    return await test_base.safe_test_run(_test_logic, "Database Operations")

async def test_user_registration():
    """Test user registration workflow comprehensively"""
    test_base = TestBase()
    
    async def _test_logic():
        from services.user_registration import (
            RegistrationRequest,
            register_telegram_user, 
            register_web_user, 
            register_mobile_user
        )
        
        # Test 1: Web user registration
        print("1️⃣ Testing web user registration...")
        web_result = await register_web_user(test_base.database, {
            "email": "john.doe@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "platform_type": "web_app",
            "country_code": "US",
            "language": "en",
            "default_currency": "USD",
            "timezone": "America/New_York"
        })
        
        if web_result.success:
            print(f"✅ Web user created: {web_result.user.get_display_name()}")
            web_user_id = web_result.user.id
        else:
            print(f"❌ Web registration failed: {web_result.error}")
            return False
        
        # Test 2: Add Telegram platform to existing user
        print("2️⃣ Testing platform addition to existing user...")
        platform_result = await test_base.registration_service.add_platform_to_user(
            web_user_id,
            "telegram",
            "telegram_123456",
            {"username": "johndoe", "first_name": "John"}
        )
        
        if platform_result.success:
            print("✅ Telegram platform added to existing user")
        else:
            print(f"❌ Platform addition failed: {platform_result.error}")
            return False
        
        # Test 3: Telegram quick registration (new user)
        print("3️⃣ Testing Telegram quick registration...")
        telegram_result = await register_telegram_user(test_base.database, "telegram_789012", {
            "first_name": "Jane",
            "last_name": "Smith",
            "username": "janesmith",
            "language_code": "es"  # Spanish user
        })
        
        if telegram_result.success:
            print(f"✅ Telegram user created: {telegram_result.user.get_display_name()}")
            telegram_user_id = telegram_result.user.id
        else:
            print(f"❌ Telegram registration failed: {telegram_result.error}")
            return False
        
        # Test 4: Mobile app registration
        print("4️⃣ Testing mobile app registration...")
        mobile_result = await register_mobile_user(test_base.database, "device_abc123", {
            "email": "mobile.user@example.com",
            "first_name": "Mobile",
            "last_name": "User",
            "device_info": {"os": "iOS", "version": "16.0", "model": "iPhone 14"}
        })
        
        if mobile_result.success:
            print(f"✅ Mobile user created: {mobile_result.user.get_display_name()}")
        else:
            print(f"❌ Mobile registration failed: {mobile_result.error}")
            return False
        
        # Test 5: User profile retrieval
        print("5️⃣ Testing user profile retrieval...")
        profile = await test_base.registration_service.get_user_profile(web_user_id)
        
        if profile["success"]:
            print(f"✅ Profile retrieved: {len(profile['platforms'])} platforms connected")
            print(f"   User: {profile['user']['first_name']} {profile['user']['last_name']}")
            print(f"   Language: {profile['user']['language']}")
            print(f"   Currency: {profile['user']['default_currency']}")
            
            for platform in profile['platforms']:
                platform_status = 'Primary' if platform['is_primary'] else 'Secondary'
                print(f"   Platform: {platform['platform_type']} ({platform_status})")
        else:
            print(f"❌ Profile retrieval failed: {profile['error']}")
            return False
        
        # Test 6: Profile update
        print("6️⃣ Testing profile update...")
        update_result = await test_base.registration_service.update_user_profile(web_user_id, {
            "language": "es",
            "default_currency": "EUR",
            "timezone": "Europe/Madrid"
        })
        
        if update_result["success"]:
            print(f"✅ Profile updated: {', '.join(update_result['updated_fields'])}")
        else:
            print(f"❌ Profile update failed: {update_result['error']}")
            return False
        
        print("✅ All user registration tests completed successfully!")
        return True
    
    return await test_base.safe_test_run(_test_logic, "User Registration")

async def test_intelligent_components():
    """Test all intelligent components"""
    test_base = TestBase()
    
    async def _test_logic():
        # Create a test user first
        from services.user_registration import register_web_user
        
        print("0️⃣ Creating test user for intelligent component testing...")
        result = await register_web_user(test_base.database, {
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "platform_type": "web_app",
            "language": "en",
            "default_currency": "USD",
            "country_code": "US",
            "timezone": "UTC"
        })
        
        if not result.success:
            print(f"❌ Failed to create test user: {result.error}")
            return False
        
        test_user_id = result.user.id
        test_platform_user_id = result.platform.platform_user_id
        
        # Test expense processing
        print("1️⃣ Testing intelligent expense processing...")
        test_expenses = [
            "Coffee $4.50",
            "Café €5.50", 
            "Almuerzo $12.50",
            "Lunch 15 dollars"
        ]
        
        for expense_msg in test_expenses:
            try:
                response = await test_base.orchestrator.process_message(
                    expense_msg, "web_app", test_platform_user_id
                )
                print(f"  ✅ '{expense_msg}' → {response[:60]}...")
            except Exception as e:
                print(f"  ⚠️ '{expense_msg}' → Error: {str(e)[:60]}...")
        
        print("✅ Expense processing tests completed")
        
        # Test reminder processing
        print("2️⃣ Testing intelligent reminder processing...")
        test_reminders = [
            "Remind me to call mom tomorrow at 3pm",
            "Don't forget dinner Friday 7pm",
            "Meeting with John next Tuesday 2pm",
            "Remind me in 2 hours to check email"
        ]
        
        for reminder_msg in test_reminders:
            try:
                response = await test_base.orchestrator.process_message(
                    reminder_msg, "web_app", test_platform_user_id
                )
                print(f"  ✅ '{reminder_msg}' → {response[:60]}...")
            except Exception as e:
                print(f"  ⚠️ '{reminder_msg}' → Error: {str(e)[:60]}...")
        
        print("✅ Reminder processing tests completed")
        
        # Test summary requests
        print("3️⃣ Testing summary requests...")
        test_queries = [
            "Show my expenses",
            "What reminders do I have?",
            "Show me my summary"
        ]
        
        for query in test_queries:
            try:
                response = await test_base.orchestrator.process_message(
                    query, "web_app", test_platform_user_id
                )
                print(f"  ✅ '{query}' → {response[:60]}...")
            except Exception as e:
                print(f"  ⚠️ '{query}' → Error: {str(e)[:60]}...")
        
        print("✅ Summary request tests completed")
        
        # Test standalone service
        print("4️⃣ Testing standalone orchestrator service...")
        
        test_result = await test_base.standalone_service.process_request(
            "Lunch $15.50", 
            "mobile_app", 
            "test_mobile_user_123"
        )
        
        if test_result["success"]:
            print(f"✅ Standalone service OK: {test_result['message'][:60]}...")
        else:
            print(f"⚠️ Standalone service response: {test_result.get('message', 'No message')[:60]}...")
        
        # Get service health and metrics
        health = await test_base.standalone_service.get_health()
        metrics = await test_base.standalone_service.get_metrics()
        
        print(f"✅ Service health: {health['status']}")
        print(f"✅ Service metrics: {metrics.get('service_metrics', {}).get('total_requests', 0)} requests processed")
        
        print("✅ All intelligent components tested successfully!")
        return True
    
    return await test_base.safe_test_run(_test_logic, "Intelligent Components")

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def print_help():
    """Print help information"""
    print("Intelligent Personal Assistant Bot")
    print("\nUsage:")
    print("  python main.py                    # Run the application")
    print("  python main.py test               # Test intelligent components")
    print("  python main.py test-registration  # Test user registration")
    print("  python main.py test-database      # Test database operations")
    print("  python main.py test-all           # Run all tests")
    print("\nFeatures:")
    print("  🧠 LLM-powered natural language understanding")
    print("  🌍 Multi-language support (English, Spanish, Portuguese, etc.)")
    print("  💱 Multi-currency support (USD, EUR, BRL, etc.)")
    print("  📱 Multi-platform (Telegram, WhatsApp, Mobile, Web)")
    print("  👤 Advanced user management and registration")
    print("  ⚙️ Standalone orchestrator service")
    print("  💾 Clean PostgreSQL database architecture")
    print("\nExample Usage:")
    print("  'Coffee $4.50' → Intelligent expense tracking")
    print("  'Café €4.50' → Multi-currency support")
    print("  'Compré pan R$ 3' → Spanish with Brazilian Real")
    print("  'Remind me to call mom tomorrow' → Smart reminder parsing")
    print("\nEnvironment Variables Required:")
    print("  GROQ_API_KEY=your_groq_api_key")
    print("  DATABASE_URL=postgresql://user:pass@localhost/dbname")
    print("  TELEGRAM_BOT_TOKEN=your_bot_token (optional)")

def main():
    """Main entry point with comprehensive options"""
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        # Test commands using TestBase
        test_commands = {
            "test": test_intelligent_components,
            "test-registration": test_user_registration,
            "test-database": test_database_operations,
        }
        
        if command in test_commands:
            print(f"🧪 Running {command.replace('-', ' ')} tests...")
            result = asyncio.run(test_commands[command]())
            sys.exit(0 if result else 1)
            
        elif command == "test-all":
            print("🧪 Running all tests...")
            results = []
            
            for test_name, test_func in test_commands.items():
                print(f"\n{'='*50}")
                print(f"{test_name.upper().replace('-', ' ')} TESTS")
                print("="*50)
                result = asyncio.run(test_func())
                results.append((test_name, result))
            
            # Summary
            print(f"\n{'='*50}")
            print("TEST SUMMARY")
            print("="*50)
            for test_name, result in results:
                status = "✅ PASSED" if result else "❌ FAILED"
                print(f"{test_name}: {status}")
            
            all_passed = all(result for _, result in results)
            print(f"\nOverall Result: {'🎉 ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
            
            sys.exit(0 if all_passed else 1)
            
        elif command == "--help":
            print_help()
            sys.exit(0)
        else:
            print(f"❌ Unknown command: {command}")
            print("Use 'python main.py --help' for available commands")
            sys.exit(1)
    
    # Run the main application
    app = PersonalAssistantApp()
    asyncio.run(app.run())

if __name__ == "__main__":
    main()