# test_supabase.py - Quick test script for Supabase connection
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

async def test_supabase_connection():
    """Test Supabase PostgreSQL connection"""
    load_dotenv()
    
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL not found in .env file")
        print("Make sure your .env file contains:")
        print("DATABASE_URL=postgresql://postgres:PASSWORD@db.REF.supabase.co:5432/postgres")
        return False
    
    print("🔍 Testing Supabase connection...")
    print(f"URL: {database_url[:50]}...") # Hide sensitive parts
    
    try:
        # Test connection
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to Supabase!")
        
        # Test basic query
        result = await conn.fetchval("SELECT version()")
        print(f"✅ Database version: {result[:50]}...")
        
        # Test permissions
        await conn.execute("SELECT NOW()")
        print("✅ Basic queries working")
        
        # Check if tables exist
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        
        table_names = [row['table_name'] for row in tables]
        print(f"📊 Existing tables: {table_names}")
        
        # Create test table if doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_connection (
                id SERIAL PRIMARY KEY,
                message TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Insert test data
        await conn.execute("""
            INSERT INTO test_connection (message) 
            VALUES ('Connection test successful!')
        """)
        
        # Read test data
        test_result = await conn.fetchval("""
            SELECT message FROM test_connection 
            ORDER BY created_at DESC LIMIT 1
        """)
        print(f"✅ Test write/read: {test_result}")
        
        # Cleanup
        await conn.execute("DROP TABLE test_connection")
        print("✅ Cleanup completed")
        
        await conn.close()
        print("🎉 Supabase connection test PASSED!")
        return True
        
    except asyncpg.InvalidAuthorizationSpecificationError:
        print("❌ Authentication failed - check your password")
        return False
    except asyncpg.InvalidCatalogNameError:
        print("❌ Database not found - check your project reference")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_supabase_connection())