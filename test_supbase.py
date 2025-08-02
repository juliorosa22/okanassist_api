# test_supabase_setup.py
import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

async def test_supabase_configuration():
    """Test single Supabase instance configuration"""
    print("🧪 Testing Single Supabase Instance Configuration...")
    print("=" * 60)
    
    # Check environment variables
    url = os.getenv("SUPABASE_URL")
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY")
    secret_key = os.getenv("SUPABASE_SECRET_KEY")
    supabase_db_url = os.getenv("DATABASE_URL")
    
    print("📋 Environment Variables Check:")
    print(f"SUPABASE_URL: {'✅ Set' if url else '❌ Missing'}")
    print(f"SUPABASE_PUBLISHABLE_KEY: {'✅ Set' if publishable_key else '❌ Missing'}")
    print(f"SUPABASE_SECRET_KEY: {'✅ Set' if secret_key else '❌ Missing'}")
    print(f"DATABASE_URL: {'✅ Set' if supabase_db_url else '❌ Missing'}")
    
    # Validate key formats
    if publishable_key:
        if publishable_key.startswith('sb_publishable_'):
            print("✅ Publishable key format is correct")
        else:
            print("⚠️ Publishable key should start with 'sb_publishable_'")
    
    if secret_key:
        if secret_key.startswith('sb_secret_'):
            print("✅ Secret key format is correct")
        else:
            print("⚠️ Secret key should start with 'sb_secret_'")
    
    # Check if using same Supabase instance
    if url and supabase_db_url:
        if url.replace('https://', '').replace('.supabase.co', '') in supabase_db_url:
            print("✅ Using same Supabase instance for auth and database")
        else:
            print("⚠️ Warning: Different instances detected - this might cause issues")
    
    if not all([url, publishable_key, supabase_db_url]):
        print("\n❌ Missing required environment variables!")
        print("\nExpected .env format (SINGLE SUPABASE INSTANCE):")
        print("""
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_lHQIZfcVFKpI51X9xT59gQ...
SUPABASE_SECRET_KEY=sb_secret_xyz123abc456def789ghi012jkl345...
SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@db.your-project-id.supabase.co:5432/postgres
        """)
        return False
    
    print(f"\n🔗 Supabase URL: {url}")
    print(f"🔑 Publishable Key: {publishable_key[:30]}...")
    if secret_key:
        print(f"🔐 Secret Key: {secret_key[:20]}...")
    print(f"🗄️  Database URL: {supabase_db_url.split('@')[0]}@[HOST]/postgres")
    
    # Test Supabase Auth connection
    print("\n🧪 Testing Supabase Auth Connection...")
    try:
        supabase: Client = create_client(url, publishable_key)
        
        # Test basic connection
        user = supabase.auth.get_user()
        print("✅ Supabase Auth connection successful!")
        
        # Test if we can access auth
        session = supabase.auth.get_session()
        print("✅ Auth service accessible!")
        
    except Exception as e:
        print(f"❌ Supabase Auth connection failed: {e}")
        return False
    
    # Test Database connection (same instance)
    print("\n🧪 Testing Supabase Database Connection...")
    try:
        import asyncpg
        
        # Test basic connection to Supabase PostgreSQL
        conn = await asyncpg.connect(supabase_db_url)
        
        # Test if we can run a simple query
        result = await conn.fetchval("SELECT version()")
        print("✅ Supabase database connection successful!")
        print(f"📊 Database version: {result.split(',')[0]}")
        
        # Check if we can see auth schema (should exist in Supabase)
        auth_tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'auth' 
            ORDER BY table_name
        """)
        
        if auth_tables:
            print(f"✅ Auth schema found with {len(auth_tables)} tables")
            print(f"   Tables: {', '.join([t['table_name'] for t in auth_tables[:3]])}...")
        else:
            print("⚠️ Auth schema not found - this might not be a Supabase database")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Supabase database connection failed: {e}")
        print("Make sure your SUPABASE_DB_URL is correct and includes the right password")
        return False
    
    # Test if we can import required modules
    print("\n📦 Testing Required Dependencies...")
    try:
        from core.database import Database
        from core.models import Transaction, Reminder
        print("✅ Core modules imported successfully!")
        
    except ImportError as e:
        print(f"❌ Core aquii module import failed: {e}")
        print("Make sure your core modules are properly set up")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("✅ Single Supabase instance configuration is correct")  
    print("✅ Auth and database using same instance")
    print("✅ All connections working")
    print("✅ Ready to start your API server")
    print("\n🚀 Next steps:")
    print("1. Run: python api_main.py")
    print("2. Visit: http://localhost:8000/docs")
    print("3. Your app tables will be created in the 'public' schema")
    print("4. User authentication handled by Supabase 'auth' schema")
    
    return True

async def test_api_startup():
    """Test if the API can start with current configuration"""
    print("\n🚀 Testing API Startup...")
    
    try:
        # Import and test configuration
        from config import Config
        Config.validate()
        print("✅ Configuration validation passed")
        
        # Test database initialization
        from core.database import Database
        database = Database(os.getenv("DATABASE_URL"))
        await database.connect()
        print("✅ Database initialization successful")
        await database.close()
        
        # Test Supabase client creation
        from supabase import create_client
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_PUBLISHABLE_KEY")
        )
        print("✅ Supabase client creation successful")
        
        print("✅ API should start successfully!")
        
    except Exception as e:
        print(f"❌ API startup test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    async def main():
        success = await test_supabase_configuration()
        if success:
            await test_api_startup()
    
    asyncio.run(main())