# config.py - Updated for new Supabase key format
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration with new Supabase key format"""
    
    # Supabase configuration (new key format)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")  # sb_publishable_...
    SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")  # sb_secret_... (server-side only)
    
    # Database configuration (for application tables)
    DATABASE_URL = os.getenv("DATABASE_URL")  # Your application database
    
    # AI/ML configuration
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    
    # Optional external services
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # API configuration
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # Security configuration
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:19006").split(",")
    
    @classmethod
    def validate(cls):
        """Validate required environment variables"""
        required = {
            'SUPABASE_URL': cls.SUPABASE_URL,
            'SUPABASE_PUBLISHABLE_KEY': cls.SUPABASE_PUBLISHABLE_KEY,
            'DATABASE_URL': cls.DATABASE_URL,
            'GROQ_API_KEY': cls.GROQ_API_KEY
        }
        
        missing = [name for name, value in required.items() if not value]
        
        if missing:
            print("❌ Missing required environment variables:")
            for var in missing:
                print(f"   {var}")
            raise ValueError(f"Missing: {missing}")
        
        # Validate key formats
        if cls.SUPABASE_PUBLISHABLE_KEY and not cls.SUPABASE_PUBLISHABLE_KEY.startswith('sb_publishable_'):
            print("⚠️  Warning: SUPABASE_PUBLISHABLE_KEY should start with 'sb_publishable_'")
        
        if cls.SUPABASE_SECRET_KEY and not cls.SUPABASE_SECRET_KEY.startswith('sb_secret_'):
            print("⚠️  Warning: SUPABASE_SECRET_KEY should start with 'sb_secret_'")
        
        print("✅ Configuration validated")
        return True

# Example .env file content with new key format:
ENV_EXAMPLE = """
# Supabase Configuration (New Key Format)
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_lHQIZfcVFKpI51X9xT59gQ_CEs9ZQwr...
SUPABASE_SECRET_KEY=sb_secret_xyz123abc456def789...

# Application Database (your PostgreSQL for app-specific tables)
DATABASE_URL=postgresql://user:password@localhost:5432/okan_app

# AI Configuration
GROQ_API_KEY=your-groq-api-key

# Optional Services
TELEGRAM_BOT_TOKEN=your-telegram-bot-token

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:19006,https://your-frontend.com
"""