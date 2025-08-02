# test_auth_setup.py - Verify environment setup
import os
from dotenv import load_dotenv

def test_environment_setup():
    """Test that all required environment variables are set"""
    load_dotenv()
    
    required_vars = {
        'SUPABASE_URL': os.getenv('SUPABASE_URL'),
        'SUPABASE_PUBLISHABLE_KEY': os.getenv('SUPABASE_PUBLISHABLE_KEY'),
        'DATABASE_URL': os.getenv('DATABASE_URL'),
        'GROQ_API_KEY': os.getenv('GROQ_API_KEY'),
        'GOOGLE_CLIENT_ID': os.getenv('GOOGLE_CLIENT_ID'),
    }
    
    optional_vars = {
        'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
        'SUPABASE_SECRET_KEY': os.getenv('SUPABASE_SECRET_KEY'),
    }
    
    print("🔍 Environment Variables Check")
    print("=" * 50)
    
    # Check required variables
    missing_required = []
    for var, value in required_vars.items():
        if value:
            masked_value = value[:20] + "..." if len(value) > 20 else value
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"❌ {var}: MISSING")
            missing_required.append(var)
    
    # Check optional variables
    print("\nOptional Variables:")
    for var, value in optional_vars.items():
        if value:
            masked_value = value[:20] + "..." if len(value) > 20 else value
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"⚠️  {var}: Not set")
    
    if missing_required:
        print(f"\n❌ Missing required variables: {', '.join(missing_required)}")
        print("Please add them to your .env file")
        return False
    else:
        print("\n✅ All required environment variables are set!")
        return True

if __name__ == "__main__":
    test_environment_setup()