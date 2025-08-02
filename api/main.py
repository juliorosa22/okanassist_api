# api/main.py - Clean FastAPI app with Telegram bot integration
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from supabase import create_client, Client
import os
import uvicorn
from dotenv import load_dotenv
from datetime import datetime
import asyncio

# Load environment variables
load_dotenv()

# Import your modules
from core.database import Database
from api.core.dependencies import set_dependencies
from api.auth import endpoints as auth_endpoints
from api.app import transactions, reminders, utils
from bot.telegram_bot import TelegramBot
from agents.orchestrator_agent import OrchestratorAgent


# Global instances
database = None
supabase: Client = None
telegram_bot = None
bot_task = None

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global database, supabase, telegram_bot, bot_task
    try:
        print("🚀 Starting Okan Personal Assistant API...")
        
        # Initialize Supabase client
        supabase = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
        print("✅ Supabase client initialized")
        
        # Initialize database
        database = Database(DATABASE_URL)
        await database.connect()
        print("✅ Application database connected")
        
        # Set dependencies for API endpoints
        set_dependencies(supabase, database)
        print("✅ API dependencies configured")
        
        # Initialize Telegram bot if token is provided
        if TELEGRAM_BOT_TOKEN and GROQ_API_KEY:
            print("🤖 Initializing Telegram bot...")
            
            # Create orchestrator for bot
            orchestrator = OrchestratorAgent(GROQ_API_KEY, database)
            
            # Create registration service for bot
            registration_service = UserRegistrationService(database)
            
            # Create and setup bot
            telegram_bot = TelegramBot(
                token=TELEGRAM_BOT_TOKEN,
                orchestrator=orchestrator,
                registration_service=registration_service
            )
            telegram_bot.setup()
            
            # Start bot as background task
            bot_task = asyncio.create_task(telegram_bot.run())
            print("✅ Telegram bot started successfully")
        else:
            print("⚠️ Telegram bot disabled (missing TELEGRAM_BOT_TOKEN or GROQ_API_KEY)")
        
        print("🎉 Okan Personal Assistant API is ready!")
        print("📡 API available at: http://localhost:8000")
        print("📚 Documentation: http://localhost:8000/docs")
        if telegram_bot:
            print("🤖 Telegram bot is running")
        
    except Exception as e:
        print(f"❌ Startup error: {e}")
        raise
    
    yield
    
    # Shutdown
    print("🛑 Shutting down Okan Personal Assistant API...")
    try:
        # Stop Telegram bot
        if telegram_bot:
            await telegram_bot.stop()
            print("✅ Telegram bot stopped")
        
        if bot_task and not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
            print("✅ Bot task cancelled")
        
        # Close database
        if database:
            await database.close()
            print("✅ Database disconnected")
            
    except Exception as e:
        print(f"⚠️ Shutdown error: {e}")
    
    print("👋 Shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Okan Personal Assistant API",
    description="Multi-platform personal assistant with Supabase authentication and Telegram bot",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:19006",
        "https://your-frontend-domain.com",
        "*"  # Remove in production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# Include routers
app.include_router(auth_endpoints.router)
app.include_router(transactions.router)
app.include_router(reminders.router)
app.include_router(utils.router)

# Root endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Okan Personal Assistant API v2.0",
        "features": [
            "Supabase Authentication", 
            "Transaction Tracking", 
            "Smart Reminders",
            "Telegram Bot Integration"
        ],
        "docs": "/docs",
        "health": "/api/health",
        "telegram_bot_active": telegram_bot is not None
    }

# Bot status endpoint
@app.get("/bot/status")
async def bot_status():
    """Get Telegram bot status"""
    if not telegram_bot:
        return {
            "bot_enabled": False,
            "status": "disabled",
            "reason": "No bot token provided"
        }
    
    return {
        "bot_enabled": True,
        "status": "running" if bot_task and not bot_task.done() else "stopped",
        "bot_info": "Telegram bot is active and processing messages"
    }

# Run the server
if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )