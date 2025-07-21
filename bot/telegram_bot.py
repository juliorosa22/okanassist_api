# bot/telegram_bot.py - Simplified version using intelligent orchestrator
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes
)

from agents.intelligent_orchestrator_agent import IntelligentOrchestratorAgent
from services.user_registration import UserRegistrationService, register_telegram_user

class TelegramBot:
    """
    Simplified Telegram bot that delegates everything to the intelligent orchestrator
    """
    
    def __init__(self, token: str, orchestrator: IntelligentOrchestratorAgent, 
                 registration_service: UserRegistrationService):
        self.token = token
        self.orchestrator = orchestrator
        self.registration_service = registration_service
        self.app = None
    
    def setup(self):
        """Setup the Telegram bot with minimal handlers"""
        self.app = Application.builder().token(self.token).build()
        
        # Only essential command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        
        # Main message handler - everything goes to orchestrator
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        return self.app
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - delegate to orchestrator"""
        user = update.effective_user
        
        # Ensure user is registered
        await self._ensure_user_registered(user)
        
        # Let orchestrator handle the welcome
        response = await self.orchestrator.process_message(
            "Hello, I'm new here", "telegram", str(user.id)
        )
        
        await update.message.reply_text(response)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command - delegate to orchestrator"""
        user = update.effective_user
        
        # Ensure user is registered
        await self._ensure_user_registered(user)
        
        # Let orchestrator handle help
        response = await self.orchestrator.process_message(
            "help", "telegram", str(user.id)
        )
        
        await update.message.reply_text(response)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all messages - delegate everything to orchestrator"""
        user = update.effective_user
        message = update.message.text
        
        print(f"📱 Telegram message from {user.first_name} ({user.id}): {message}")
        
        try:
            # Ensure user is registered
            await self._ensure_user_registered(user)
            
            # Let orchestrator handle everything
            response = await self.orchestrator.process_message(
                message, "telegram", str(user.id)
            )
            
            print(f"🤖 Response: {response}")
            
            await update.message.reply_text(response)
            
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            
            # Simple error response
            error_message = "❌ Sorry, I encountered an error. Please try again."
            await update.message.reply_text(error_message)
    
    async def _ensure_user_registered(self, user):
        """Ensure user is registered in the system"""
        try:
            # Check if user exists
            existing = await self.registration_service.database.get_user_by_platform(
                "telegram", str(user.id)
            )
            
            if not existing:
                # Auto-register user
                result = await register_telegram_user(
                    self.registration_service.database,
                    str(user.id),
                    {
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "username": user.username,
                        "language_code": user.language_code
                    }
                )
                
                if result.success:
                    print(f"✅ Auto-registered Telegram user: {user.first_name} ({user.id})")
                else:
                    print(f"❌ Failed to register user: {result.error}")
            
        except Exception as e:
            print(f"❌ Error ensuring user registration: {e}")
    
    async def set_commands(self):
        """Set minimal bot commands"""
        commands = [
            BotCommand("start", "Start using the assistant"),
            BotCommand("help", "Get help and examples"),
        ]
        
        await self.app.bot.set_my_commands(commands)
    
    async def run(self):
        """Start the bot"""
        if not self.app:
            self.setup()
        
        # Set up commands
        await self.set_commands()
        
        print("🤖 Simplified Telegram Bot started")
        print("💡 All messages are handled by the intelligent orchestrator")
        print("🎯 Commands: /start, /help")
        print("📝 Everything else is natural language processing")
        
        # Start polling
        async with self.app:
            await self.app.start()
            await self.app.updater.start_polling()
            
            # Keep running until stopped
            try:
                import asyncio
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Stopping Telegram bot...")
            finally:
                await self.app.updater.stop()
                await self.app.stop()
    
    async def stop(self):
        """Stop the bot"""
        if self.app and self.app.running:
            await self.app.stop()
            print("🛑 Telegram bot stopped")