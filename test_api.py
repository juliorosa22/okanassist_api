# test_api_health.py - Test API connectivity and health
import asyncio
import aiohttp
import os
from dotenv import load_dotenv

async def test_api_health():
    """Test API health and basic connectivity"""
    load_dotenv()
    
    api_url = os.getenv('API_HOST')
    port= os.getenv('API_PORT')
    api_url= f"{api_url}:{port}" if api_url.startswith('http') else f"http://{api_url}:{port}"
    print("🔍 API Health Check")
    print("=" * 50)
    print(f"Testing API at: {api_url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test root endpoint
            print("\n1. Testing root endpoint...")
            async with session.get(f"{api_url}/") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Root endpoint: {data.get('message', 'OK')}")
                    print(f"   Features: {', '.join(data.get('features', []))}")
                    print(f"   Telegram bot: {data.get('telegram_bot_active', 'Unknown')}")
                else:
                    print(f"❌ Root endpoint failed: {response.status}")
            
            # Test health endpoint
            print("\n2. Testing health endpoint...")
            async with session.get(f"{api_url}/api/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Health check: {data.get('status', 'Unknown')}")
                    print(f"   Database: {data.get('database', 'Unknown')}")
                    print(f"   Service: {data.get('service', 'Unknown')}")
                else:
                    print(f"❌ Health check failed: {response.status}")
            
            # Test Google auth URL endpoint
            print("\n3. Testing Google auth URL endpoint...")
            async with session.get(f"{api_url}/auth/google/url?redirect_scheme=okanassist") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        print(f"✅ Google auth URL generated")
                        print(f"   Client ID: {data.get('client_id', 'Unknown')[:20]}...")
                        print(f"   Auth URL: {data.get('auth_url', 'Unknown')[:50]}...")
                    else:
                        print(f"❌ Google auth URL failed: {data}")
                else:
                    data = await response.json() if response.content_type == 'application/json' else {}
                    print(f"❌ Google auth URL endpoint failed: {response.status}")
                    print(f"   Error: {data.get('detail', 'Unknown error')}")
            
            # Test categories endpoint
            print("\n4. Testing categories endpoint...")
            async with session.get(f"{api_url}/api/categories") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        expense_cats = len(data.get('categories', {}).get('expense', []))
                        income_cats = len(data.get('categories', {}).get('income', []))
                        print(f"✅ Categories: {expense_cats} expense, {income_cats} income")
                    else:
                        print(f"❌ Categories failed: {data}")
                else:
                    print(f"❌ Categories endpoint failed: {response.status}")
            
            print("\n🎉 API health check completed!")
            
    except aiohttp.ClientConnectorError:
        print(f"❌ Cannot connect to API at {api_url}")
        print("   Make sure the API server is running")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_api_health())