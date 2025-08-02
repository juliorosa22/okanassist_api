# start_api.py - API startup script in project root
#!/usr/bin/env python3
"""
Startup script for Okan Personal Assistant API
Run this from the project root directory
"""

import sys
import os
from pathlib import Path

# Ensure we're in the right directory
project_root = Path(__file__).parent
os.chdir(project_root)

# Add project root to Python path
sys.path.insert(0, str(project_root))

# Now import and run the API
if __name__ == "__main__":
    try:
        from api.main import app
        import uvicorn
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Get configuration
        host = os.getenv("API_HOST", "0.0.0.0")
        port = int(os.getenv("API_PORT", 8000))
        debug = os.getenv("DEBUG", "false").lower() == "true"
        
        print(f"🚀 Starting Okan API on {host}:{port}")
        print(f"📁 Project root: {project_root}")
        print(f"🐛 Debug mode: {debug}")
        
        # Start the server
        uvicorn.run(
            "api.main:app",
            host=host,
            port=port,
            reload=debug,
            reload_dirs=[str(project_root)] if debug else None
        )
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this from the project root directory")
        print("and all dependencies are installed")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Startup error: {e}")
        sys.exit(1)