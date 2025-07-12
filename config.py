# config.py
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration"""
    
    # Required API keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Optional settings
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    @classmethod
    def validate(cls):
        """Validate required environment variables"""
        required = {
            'GROQ_API_KEY': cls.GROQ_API_KEY,
            'TELEGRAM_BOT_TOKEN': cls.TELEGRAM_BOT_TOKEN,
            'DATABASE_URL': cls.DATABASE_URL
        }
        
        missing = [name for name, value in required.items() if not value]
        
        if missing:
            print("❌ Missing required environment variables:")
            for var in missing:
                print(f"   {var}")
            raise ValueError(f"Missing: {missing}")
        
        print("✅ Configuration validated")
        return True