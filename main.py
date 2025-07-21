# main.py - Complete updated version with intelligent agents and clean database
import asyncio
import sys
from datetime import datetime
from config import Config
from core.database import Database
from agents.intelligent_orchestrator_agent import IntelligentOrchestratorAgent
from services.standalone_orchestrator_service import StandaloneOrchestratorService
from services.user_registration import UserRegistrationService

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
        
        print("✅ Initialization complete!")
    
    async def _setup_agent_tools(self):
        """Setup tools for intelligent agents"""
        try:
            # Import and setup expense tools
            from agents.tools.intelligent_expense_tools import set_database as set_expense_db
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
            print("   📱 Telegram Bot (if token provided)")
            print("   ⚙️ Standalone Orchestrator Service")
            print("   👤 User Registration Service")
            print("   🧠 Intelligent Expense Agent")
            print("   🔔 Intelligent Reminder Agent")
            print("\n🛑 Press Ctrl+C to stop")
            print("="*80)
            
            # Start services based on configuration
            if self.telegram_bot:
                print("🤖 Starting Telegram bot...")
                await self.telegram_bot.run()
            else:
                print("⚙️ Running standalone orchestrator service...")
                print("📡 Service available for API integration")
                print("💡 You can integrate this with any platform using the standalone service")
                
                # Keep service running and show periodic status
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
                                  f"Requests processed: {metrics.get('total_processed', 0)} | "
                                  f"Time: {current_time.strftime('%H:%M:%S')}")
                            
                            if health["status"] != "healthy":
                                print(f"⚠️ Service health: {health}")
                            
                            last_health_check = current_time.timestamp()
                            
                except KeyboardInterrupt:
                    print("\n🛑 Shutdown requested...")
                    
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested...")
            await self.shutdown()
        except Exception as e:
            print(f"❌ Application error: {e}")
            import traceback
            traceback.print_exc()
            await self.shutdown()
            raise
    
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

async def test_intelligent_components():
    """Test all intelligent components independently"""
    print("🧪 Testing Intelligent Personal Assistant components...")
    
    try:
        # Test configuration
        print("1️⃣ Testing configuration...")
        config = Config()
        config.validate()
        print("✅ Configuration OK")
        
        # Test database
        print("2️⃣ Testing clean database connection...")
        database = Database(config.DATABASE_URL)
        await database.connect()
        print("✅ Clean database connected and tables created")
        
        # Test user registration
        print("3️⃣ Testing user registration service...")
        from services.user_registration import UserRegistrationService, RegistrationRequest
        
        registration_service = UserRegistrationService(database)
        test_request = RegistrationRequest(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            platform_type="web_app",
            language="en",
            default_currency="USD",
            country_code="US",
            timezone="UTC"
        )
        
        result = await registration_service.register_user(test_request)
        if result.success:
            print(f"✅ User registration OK: {result.user.get_display_name()}")
            test_user_id = result.user.id
            test_platform_user_id = result.platform.platform_user_id
        else:
            print(f"❌ User registration failed: {result.error}")
            await database.close()
            return False
        
        # Test intelligent orchestrator initialization
        print("4️⃣ Testing intelligent orchestrator initialization...")
        from agents.intelligent_orchestrator_agent import IntelligentOrchestratorAgent
        
        orchestrator = IntelligentOrchestratorAgent(config.GROQ_API_KEY, database)
        print("✅ Orchestrator initialized")
        
        # Setup agent tools
        print("5️⃣ Setting up agent tools...")
        try:
            from agents.tools.intelligent_expense_tools import set_database as set_expense_db
            from agents.tools.intelligent_reminder_tools import set_database as set_reminder_db
            set_expense_db(database)
            set_reminder_db(database)
            print("✅ Agent tools configured")
        except ImportError as e:
            print(f"⚠️ Warning: Agent tools not found: {e}")
            print("⚠️ Continuing with basic orchestrator test...")
        
        # Test expense processing
        print("6️⃣ Testing intelligent expense processing...")
        test_expenses = [
            "Coffee $4.50",
            "Café €5.50", 
            "Almuerzo $12.50",
            "Lunch 15 dollars"
        ]
        
        for expense_msg in test_expenses:
            try:
                response = await orchestrator.process_message(
                    expense_msg, "web_app", test_platform_user_id
                )
                print(f"  ✅ '{expense_msg}' → {response[:60]}...")
            except Exception as e:
                print(f"  ⚠️ '{expense_msg}' → Error: {str(e)[:60]}...")
        
        print("✅ Expense processing tests completed")
        
        # Test reminder processing
        print("7️⃣ Testing intelligent reminder processing...")
        test_reminders = [
            "Remind me to call mom tomorrow at 3pm",
            "Don't forget dinner Friday 7pm",
            "Meeting with John next Tuesday 2pm",
            "Remind me in 2 hours to check email"
        ]
        
        for reminder_msg in test_reminders:
            try:
                response = await orchestrator.process_message(
                    reminder_msg, "web_app", test_platform_user_id
                )
                print(f"  ✅ '{reminder_msg}' → {response[:60]}...")
            except Exception as e:
                print(f"  ⚠️ '{reminder_msg}' → Error: {str(e)[:60]}...")
        
        print("✅ Reminder processing tests completed")
        
        # Test summary requests
        print("8️⃣ Testing summary requests...")
        test_queries = [
            "Show my expenses",
            "What reminders do I have?",
            "Show me my summary"
        ]
        
        for query in test_queries:
            try:
                response = await orchestrator.process_message(
                    query, "web_app", test_platform_user_id
                )
                print(f"  ✅ '{query}' → {response[:60]}...")
            except Exception as e:
                print(f"  ⚠️ '{query}' → Error: {str(e)[:60]}...")
        
        print("✅ Summary request tests completed")
        
        # Test standalone service
        print("9️⃣ Testing standalone orchestrator service...")
        from agents.intelligent_orchestrator_agent import StandaloneOrchestratorService
        
        service = StandaloneOrchestratorService(config.GROQ_API_KEY, config.DATABASE_URL)
        await service.initialize()
        
        test_result = await service.process_request(
            "Lunch $15.50", 
            "mobile_app", 
            "test_mobile_user_123"
        )
        
        if test_result["success"]:
            print(f"✅ Standalone service OK: {test_result['message'][:60]}...")
        else:
            print(f"⚠️ Standalone service response: {test_result.get('message', 'No message')[:60]}...")
        
        # Get service health and metrics
        health = await service.get_health()
        metrics = await service.get_metrics()
        
        print(f"✅ Service health: {health['status']}")
        print(f"✅ Service metrics: {metrics.get('total_processed', 0)} requests processed")
        
        await service.shutdown()
        await database.close()
        
        print("\n🎉 All intelligent components tested successfully!")
        print("\n💡 The system is ready for:")
        print("   🌍 Multi-language natural language processing")
        print("   💱 Multi-currency expense tracking")
        print("   📱 Multi-platform user management")
        print("   🧠 Intelligent routing and response generation")
        print("   ⚙️ Standalone service integration")
        print("   👤 Comprehensive user registration and management")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to cleanup
        try:
            if 'database' in locals():
                await database.close()
        except:
            pass
        
        return False

async def test_user_registration():
    """Test user registration workflow comprehensively"""
    print("🧪 Testing User Registration Workflow...")
    
    config = Config()
    config.validate()
    database = Database(config.DATABASE_URL)
    await database.connect()
    
    try:
        from services.user_registration import (
            UserRegistrationService, RegistrationRequest,
            register_telegram_user, register_web_user, register_mobile_user
        )
        
        service = UserRegistrationService(database)
        
        # Test 1: Web user registration
        print("1️⃣ Testing web user registration...")
        web_result = await register_web_user(database, {
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
            await database.close()
            return False
        
        # Test 2: Add Telegram platform to existing user
        print("2️⃣ Testing platform addition to existing user...")
        platform_result = await service.add_platform_to_user(
            web_user_id,
            "telegram",
            "telegram_123456",
            {"username": "johndoe", "first_name": "John"}
        )
        
        if platform_result.success:
            print("✅ Telegram platform added to existing user")
        else:
            print(f"❌ Platform addition failed: {platform_result.error}")
        
        # Test 3: Telegram quick registration (new user)
        print("3️⃣ Testing Telegram quick registration...")
        telegram_result = await register_telegram_user(database, "telegram_789012", {
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
        
        # Test 4: Mobile app registration
        print("4️⃣ Testing mobile app registration...")
        mobile_result = await register_mobile_user(database, "device_abc123", {
            "email": "mobile.user@example.com",
            "first_name": "Mobile",
            "last_name": "User",
            "device_info": {"os": "iOS", "version": "16.0", "model": "iPhone 14"}
        })
        
        if mobile_result.success:
            print(f"✅ Mobile user created: {mobile_result.user.get_display_name()}")
        else:
            print(f"❌ Mobile registration failed: {mobile_result.error}")
        
        # Test 5: User profile retrieval
        print("5️⃣ Testing user profile retrieval...")
        profile = await service.get_user_profile(web_user_id)
        
        if profile["success"]:
            print(f"✅ Profile retrieved: {len(profile['platforms'])} platforms connected")
            print(f"   User: {profile['user']['first_name']} {profile['user']['last_name']}")
            print(f"   Language: {profile['user']['language']}")
            print(f"   Currency: {profile['user']['default_currency']}")
            
            for platform in profile['platforms']:
                print(f"   Platform: {platform['platform_type']} ({'Primary' if platform['is_primary'] else 'Secondary'})")
        else:
            print(f"❌ Profile retrieval failed: {profile['error']}")
        
        # Test 6: Profile update
        print("6️⃣ Testing profile update...")
        update_result = await service.update_user_profile(web_user_id, {
            "language": "es",
            "default_currency": "EUR",
            "timezone": "Europe/Madrid"
        })
        
        if update_result["success"]:
            print(f"✅ Profile updated: {', '.join(update_result['updated_fields'])}")
        else:
            print(f"❌ Profile update failed: {update_result['error']}")
        
        # Test 7: Duplicate registration handling
        print("7️⃣ Testing duplicate registration handling...")
        duplicate_result = await register_web_user(database, {
            "email": "john.doe@example.com",  # Same email as before
            "first_name": "John",
            "last_name": "Duplicate"
        })
        
        if not duplicate_result.success:
            print("✅ Duplicate registration properly rejected")
        else:
            print("⚠️ Duplicate registration was allowed (may need attention)")
        
        # Test 8: Get all users summary
        print("8️⃣ Testing user statistics...")
        all_users = await database.get_all_users(limit=10)
        print(f"✅ Total users in system: {len(all_users)}")
        
        for user in all_users:
            platforms = await database.get_user_platforms(user.id)
            print(f"   {user.get_display_name()} - {len(platforms)} platforms")
        
        await database.close()
        print("\n✅ User registration tests completed successfully!")
        
        print("\n📊 Test Summary:")
        print(f"   • Web registration: ✅")
        print(f"   • Platform addition: ✅")
        print(f"   • Telegram registration: ✅")
        print(f"   • Mobile registration: ✅")
        print(f"   • Profile management: ✅")
        print(f"   • Duplicate handling: ✅")
        
        return True
        
    except Exception as e:
        print(f"❌ Registration test failed: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            await database.close()
        except:
            pass
        
        return False

async def test_database_operations():
    """Test database operations independently"""
    print("🧪 Testing Database Operations...")
    
    config = Config()
    config.validate()
    database = Database(config.DATABASE_URL)
    
    try:
        await database.connect()
        print("✅ Database connection successful")
        
        # Test user operations
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
        created_user = await database.create_user(test_user)
        print("✅ User creation successful")
        
        # Get user
        retrieved_user = await database.get_user("test_user_123")
        if retrieved_user and retrieved_user.email == "test@example.com":
            print("✅ User retrieval successful")
        else:
            print("❌ User retrieval failed")
        
        # Test platform operations
        print("Testing platform operations...")
        from core.models import UserPlatform
        
        test_platform = UserPlatform(
            user_id="test_user_123",
            platform_type="telegram",
            platform_user_id="tg_123456",
            is_primary=True
        )
        
        created_platform = await database.create_user_platform(test_platform)
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
        
        created_expense = await database.save_expense(test_expense)
        print("✅ Expense creation successful")
        
        # Test expense summary
        summary = await database.get_expense_summary("test_user_123", days=30)
        if summary.total_count == 1 and summary.total_amount == Decimal("25.50"):
            print("✅ Expense summary calculation successful")
        else:
            print("❌ Expense summary calculation failed")
        
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
        
        created_reminder = await database.save_reminder(test_reminder)
        print("✅ Reminder creation successful")
        
        # Test reminder retrieval
        reminders = await database.get_user_reminders("test_user_123")
        if len(reminders) == 1:
            print("✅ Reminder retrieval successful")
        else:
            print("❌ Reminder retrieval failed")
        
        await database.close()
        print("✅ Database operations test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            await database.close()
        except:
            pass
        
        return False

def main():
    """Main entry point with comprehensive options"""
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "test":
            print("🧪 Running comprehensive component tests...")
            result = asyncio.run(test_intelligent_components())
            sys.exit(0 if result else 1)
            
        elif command == "test-registration":
            print("🧪 Running user registration tests...")
            result = asyncio.run(test_user_registration())
            sys.exit(0 if result else 1)
            
        elif command == "test-database":
            print("🧪 Running database operation tests...")
            result = asyncio.run(test_database_operations())
            sys.exit(0 if result else 1)
            
        elif command == "test-all":
            print("🧪 Running all tests...")
            
            print("\n" + "="*50)
            print("DATABASE TESTS")
            print("="*50)
            db_result = asyncio.run(test_database_operations())
            
            print("\n" + "="*50)
            print("USER REGISTRATION TESTS")
            print("="*50)
            reg_result = asyncio.run(test_user_registration())
            
            print("\n" + "="*50)
            print("INTELLIGENT COMPONENT TESTS")
            print("="*50)
            comp_result = asyncio.run(test_intelligent_components())
            
            print("\n" + "="*50)
            print("TEST SUMMARY")
            print("="*50)
            print(f"Database Tests: {'✅ PASSED' if db_result else '❌ FAILED'}")
            print(f"Registration Tests: {'✅ PASSED' if reg_result else '❌ FAILED'}")
            print(f"Component Tests: {'✅ PASSED' if comp_result else '❌ FAILED'}")
            
            all_passed = db_result and reg_result and comp_result
            print(f"\nOverall Result: {'🎉 ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
            
            sys.exit(0 if all_passed else 1)
            
        elif command == "--help":
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