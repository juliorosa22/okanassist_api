# bot/telegram_bot.py
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes
)

from agents.orchestrator_agent import OrchestratorAgent

class TelegramBot:
    """
    Telegram bot interface for multi-task personal assistant
    """
    
    def __init__(self, token: str, groq_api_key: str, database_url: str, database_instance):
        self.token = token
        self.groq_api_key = groq_api_key
        self.database_url = database_url
        self.database_instance = database_instance
        
        # Replace single expense_agent with orchestrator
        self.orchestrator = OrchestratorAgent(
            groq_api_key=groq_api_key,
            database_url=database_url,
            database_instance=database_instance
        )
        self.app = None
    
    def setup(self):
        """Setup the Telegram bot with handlers"""
        self.app = Application.builder().token(self.token).build()
        
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("summary", self.summary_command))
        self.app.add_handler(CommandHandler("expenses", self.expenses_command))
        self.app.add_handler(CommandHandler("reminders", self.reminders_command))
        self.app.add_handler(CommandHandler("due", self.due_reminders_command))
        self.app.add_handler(CommandHandler("categories", self.categories_command))
        
        # Message handler (for all types of messages)
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        return self.app
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Initialize user with the orchestrator
        welcome_message = f"""
🎉 **Welcome to your Personal Assistant!**

Hi {user.first_name}! I'm your AI-powered personal assistant. I can help you with:

💰 **Expense Tracking**
- Just say: "Coffee $4.50" or "Lunch $12 at McDonald's"

🔔 **Reminders**
- Just say: "Remind me to call mom tomorrow at 3pm"
- Or: "Don't forget dinner with John Friday 7pm"

📊 **Summaries & Reports**
- Ask: "Show my expense summary" or "What reminders do I have?"

Just talk to me naturally - I'll understand what you need! 😊

Try sending me an expense or reminder to get started.
        """
        
        # Create/update user in database through orchestrator
        user_info = {
            'first_name': user.first_name,
            'username': user.username,
            'last_name': user.last_name
        }
        
        # Process user initialization
        await self.orchestrator.process_message(
            f"Initialize user: {user.first_name} (ID: {user.id})",
            str(user.id),
            user_info
        )
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🤖 **Personal Assistant Help**

**💰 Expense Tracking:**
- "Coffee $4.50"
- "Lunch at McDonald's $12"
- "Spent $25 on groceries"
- "Gas station $45"

**🔔 Reminders:**
- "Remind me to call mom tomorrow at 3pm"
- "Don't forget dinner with John Friday 7pm"
- "Remind me to pay bills in 3 days"
- "Set reminder for meeting Monday 2pm"

**📊 Summaries:**
- "Show my expense summary"
- "What did I spend on food?"
- "What reminders do I have?"
- "What's due today?"

**✅ Managing Reminders:**
- "Mark reminder as done"
- "Show my upcoming reminders"
- "What's due this week?"

**Commands:**
- /start - Welcome and setup
- /help - Show this help
- /summary - General summary
- /expenses - Expense summary only
- /reminders - Show all reminders
- /due - Show due reminders
- /categories - View expense categories

**Examples:**
- "Coffee $4.50 at Starbucks"
- "Remind me about dentist appointment tomorrow 2pm"
- "How much did I spend this month?"
- "What do I need to do today?"

Just talk to me naturally! 😊
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def summary_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /summary command - general summary"""
        user = update.effective_user
        
        # Let the orchestrator handle the summary request
        response = await self.orchestrator.process_message(
            "Show me a general summary of my expenses and reminders",
            str(user.id)
        )
        
        await update.message.reply_text(response)
    
    async def expenses_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /expenses command - expense summary only"""
        user = update.effective_user
        
        response = await self.orchestrator.process_message(
            "Show me my expense summary",
            str(user.id)
        )
        
        await update.message.reply_text(response)
    
    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reminders command - show all reminders"""
        user = update.effective_user
        
        response = await self.orchestrator.process_message(
            "Show me all my reminders",
            str(user.id)
        )
        
        await update.message.reply_text(response)
    
    async def due_reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /due command - show due reminders"""
        user = update.effective_user
        
        response = await self.orchestrator.process_message(
            "What reminders are due today?",
            str(user.id)
        )
        
        await update.message.reply_text(response)
    
    async def categories_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /categories command"""
        user = update.effective_user
        
        # Let the orchestrator handle the categories request
        response = await self.orchestrator.process_message(
            "What expense categories are available?",
            str(user.id)
        )
        
        await update.message.reply_text(response)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all text messages through orchestrator"""
        user = update.effective_user
        message = update.message.text
        
        # Prepare user info for context
        user_info = {
            'first_name': user.first_name,
            'username': user.username,
            'last_name': user.last_name
        }
        
        print(f"📱 Message from {user.first_name} ({user.id}): {message}")
        
        # Let orchestrator handle routing and processing
        response = await self.orchestrator.process_message(
            message, 
            str(user.id),
            user_info
        )
        
        print(f"🤖 Bot response: {response}")
        
        await update.message.reply_text(response)
    
    async def set_commands(self):
        """Set bot commands for better UX"""
        commands = [
            BotCommand("start", "Start using the personal assistant"),
            BotCommand("help", "Get help and examples"),
            BotCommand("summary", "View general summary"),
            BotCommand("expenses", "View expense summary"),
            BotCommand("reminders", "View all reminders"),
            BotCommand("due", "View due reminders"),
            BotCommand("categories", "View expense categories"),
        ]
        
        await self.app.bot.set_my_commands(commands)
    
    async def send_message_to_user(self, user_id: str, message: str):
        """Send a message to a specific user (useful for proactive notifications)"""
        try:
            await self.app.bot.send_message(chat_id=user_id, text=message)
            print(f"📤 Sent notification to user {user_id}")
        except Exception as e:
            print(f"❌ Failed to send message to user {user_id}: {e}")
    
    async def broadcast_due_reminders(self):
        """Check and send due reminder notifications to all users"""
        try:
            # This would require getting all users from database
            # For now, this is a placeholder for the notification system
            print("🔔 Checking due reminders for all users...")
            
            # You could implement this to:
            # 1. Get all users from database
            # 2. Check due reminders for each user
            # 3. Send notifications for due reminders
            
        except Exception as e:
            print(f"❌ Error broadcasting due reminders: {e}")
    
    async def run(self):
        """Start the bot"""
        if not self.app:
            self.setup()
        
        # Set up commands
        await self.set_commands()
        
        print("🤖 Personal Assistant Bot started")
        print("💡 Users can now:")
        print("   • Track expenses: 'Coffee $4.50'")
        print("   • Set reminders: 'Remind me to call mom tomorrow 3pm'")
        print("   • Ask questions naturally")
        print("   • Get summaries: /summary, /expenses, /reminders")
        print("📱 Available commands: /start, /help, /summary, /expenses, /reminders, /due")
        
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
                print("\n🛑 Stopping bot...")
            finally:
                await self.app.updater.stop()
                await self.app.stop()
    
    async def stop(self):
        """Stop the bot"""
        if self.app and self.app.running:
            await self.app.stop()
            print("🛑 Telegram bot stopped")