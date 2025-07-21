# services/standalone_orchestrator_service.py
from typing import Dict, Any, Optional
from datetime import datetime

from core.database import Database
from agents.intelligent_orchestrator_agent import IntelligentOrchestratorAgent

class StandaloneOrchestratorService:
    """
    Standalone service that can run the orchestrator independently from any platform.
    Provides a complete service infrastructure around the IntelligentOrchestratorAgent.
    """
    
    def __init__(self, groq_api_key: str, database_url: str):
        """
        Initialize the standalone orchestrator service
        
        Args:
            groq_api_key: Groq API key for LLM access
            database_url: PostgreSQL database connection URL
        """
        self.groq_api_key = groq_api_key
        self.database_url = database_url
        self.database: Optional[Database] = None
        self.orchestrator: Optional[IntelligentOrchestratorAgent] = None
        self.is_running = False
        
        # Service metrics
        self.service_metrics = {
            "service_started_at": None,
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "initialization_count": 0,
            "last_health_check": None
        }
    
    async def initialize(self):
        """Initialize the service with database and orchestrator"""
        try:
            print("🔧 Initializing Standalone Orchestrator Service...")
            
            # Initialize database
            print("📊 Connecting to database...")
            self.database = Database(self.database_url)
            await self.database.connect()
            
            # Initialize orchestrator
            print("🧠 Setting up intelligent orchestrator...")
            self.orchestrator = IntelligentOrchestratorAgent(self.groq_api_key, self.database)
            
            # Setup agent tools
            print("🔧 Configuring agent tools...")
            await self._setup_agent_tools()
            
            # Mark service as running
            self.is_running = True
            self.service_metrics["service_started_at"] = datetime.now()
            self.service_metrics["initialization_count"] += 1
            
            print("✅ Standalone Orchestrator Service initialized successfully")
            
        except Exception as e:
            print(f"❌ Failed to initialize service: {e}")
            self.is_running = False
            raise
    
    async def _setup_agent_tools(self):
        """Setup tools for intelligent agents"""
        try:
            # Import and setup expense tools
            from agents.tools.intelligent_expense_tools import set_database as set_expense_db
            set_expense_db(self.database)
            
            # Import and setup reminder tools  
            from agents.tools.intelligent_reminder_tools import set_database as set_reminder_db
            set_reminder_db(self.database)
            
            print("✅ Agent tools configured")
        except ImportError as e:
            print(f"⚠️ Warning: Could not import agent tools: {e}")
            print("⚠️ Service will continue but some features may not work")
    
    async def process_request(self, message: str, platform_type: str, platform_user_id: str, user_info: Dict = None) -> Dict[str, Any]:
        """
        Process a request and return structured response
        
        Args:
            message: User's message
            platform_type: Platform origin (telegram, whatsapp, mobile_app, web_app)
            platform_user_id: Platform-specific user ID
            user_info: Optional user information
            
        Returns:
            Structured response with message and metadata
        """
        
        # Update metrics
        self.service_metrics["total_requests"] += 1
        request_start_time = datetime.now()
        
        # Check if service is running
        if not self.is_running or not self.orchestrator:
            self.service_metrics["failed_requests"] += 1
            return {
                "success": False,
                "message": "Service not initialized",
                "error": "Service not running",
                "error_code": "SERVICE_NOT_INITIALIZED",
                "platform_type": platform_type,
                "platform_user_id": platform_user_id,
                "processed_at": request_start_time.isoformat(),
                "processing_time_ms": 0
            }
        
        try:
            # Process message through orchestrator
            response_message = await self.orchestrator.process_message(
                message, platform_type, platform_user_id, user_info
            )
            
            # Calculate processing time
            processing_time = (datetime.now() - request_start_time).total_seconds() * 1000
            
            # Update success metrics
            self.service_metrics["successful_requests"] += 1
            
            return {
                "success": True,
                "message": response_message,
                "platform_type": platform_type,
                "platform_user_id": platform_user_id,
                "user_info": user_info,
                "processed_at": request_start_time.isoformat(),
                "processing_time_ms": round(processing_time, 2),
                "orchestrator_metrics": self.orchestrator.get_metrics()
            }
            
        except Exception as e:
            # Calculate processing time even for errors
            processing_time = (datetime.now() - request_start_time).total_seconds() * 1000
            
            # Update failure metrics
            self.service_metrics["failed_requests"] += 1
            
            print(f"❌ Service processing error: {e}")
            
            return {
                "success": False,
                "message": "❌ Sorry, there was an error processing your request.",
                "error": str(e),
                "error_code": "PROCESSING_ERROR",
                "platform_type": platform_type,
                "platform_user_id": platform_user_id,
                "processed_at": request_start_time.isoformat(),
                "processing_time_ms": round(processing_time, 2)
            }
    
    async def process_batch_requests(self, requests: list) -> Dict[str, Any]:
        """
        Process multiple requests in batch
        
        Args:
            requests: List of request dictionaries
            
        Returns:
            Batch processing results
        """
        
        if not self.is_running:
            return {
                "success": False,
                "error": "Service not running",
                "processed_count": 0,
                "results": []
            }
        
        batch_start_time = datetime.now()
        results = []
        successful_count = 0
        
        for i, request in enumerate(requests):
            try:
                result = await self.process_request(
                    request.get("message", ""),
                    request.get("platform_type", "unknown"),
                    request.get("platform_user_id", f"batch_user_{i}"),
                    request.get("user_info")
                )
                
                if result["success"]:
                    successful_count += 1
                
                results.append({
                    "request_index": i,
                    "result": result
                })
                
            except Exception as e:
                results.append({
                    "request_index": i,
                    "result": {
                        "success": False,
                        "error": str(e),
                        "error_code": "BATCH_ITEM_ERROR"
                    }
                })
        
        batch_processing_time = (datetime.now() - batch_start_time).total_seconds() * 1000
        
        return {
            "success": True,
            "batch_size": len(requests),
            "processed_count": len(results),
            "successful_count": successful_count,
            "failed_count": len(results) - successful_count,
            "processing_time_ms": round(batch_processing_time, 2),
            "processed_at": batch_start_time.isoformat(),
            "results": results
        }
    
    async def get_health(self) -> Dict[str, Any]:
        """Get comprehensive service health status"""
        
        health_check_time = datetime.now()
        self.service_metrics["last_health_check"] = health_check_time
        
        if not self.orchestrator:
            return {
                "status": "not_initialized",
                "service_running": self.is_running,
                "database_connected": bool(self.database and self.database.pool),
                "orchestrator_available": False,
                "timestamp": health_check_time.isoformat(),
                "uptime_seconds": 0,
                "service_metrics": self.service_metrics
            }
        
        # Get orchestrator health
        orchestrator_health = await self.orchestrator.health_check()
        
        # Calculate uptime
        uptime_seconds = 0
        if self.service_metrics["service_started_at"]:
            uptime_seconds = (health_check_time - self.service_metrics["service_started_at"]).total_seconds()
        
        # Calculate success rate
        success_rate = 0.0
        if self.service_metrics["total_requests"] > 0:
            success_rate = self.service_metrics["successful_requests"] / self.service_metrics["total_requests"]
        
        # Determine overall status
        overall_status = "healthy"
        if not self.is_running:
            overall_status = "not_running"
        elif orchestrator_health["status"] != "healthy":
            overall_status = "degraded"
        elif success_rate < 0.9 and self.service_metrics["total_requests"] > 10:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "service_running": self.is_running,
            "database_connected": bool(self.database and self.database.pool),
            "orchestrator_available": bool(self.orchestrator),
            "orchestrator_health": orchestrator_health,
            "timestamp": health_check_time.isoformat(),
            "uptime_seconds": round(uptime_seconds, 2),
            "success_rate": round(success_rate, 4),
            "service_metrics": self.service_metrics
        }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive service metrics"""
        
        if not self.orchestrator:
            return {
                "error": "Service not initialized",
                "service_metrics": self.service_metrics
            }
        
        # Get orchestrator metrics
        orchestrator_metrics = self.orchestrator.get_metrics()
        
        # Calculate additional service metrics
        success_rate = 0.0
        error_rate = 0.0
        
        if self.service_metrics["total_requests"] > 0:
            success_rate = self.service_metrics["successful_requests"] / self.service_metrics["total_requests"]
            error_rate = self.service_metrics["failed_requests"] / self.service_metrics["total_requests"]
        
        # Calculate average processing time (would need to track this)
        uptime_seconds = 0
        if self.service_metrics["service_started_at"]:
            uptime_seconds = (datetime.now() - self.service_metrics["service_started_at"]).total_seconds()
        
        requests_per_minute = 0.0
        if uptime_seconds > 0:
            requests_per_minute = (self.service_metrics["total_requests"] / uptime_seconds) * 60
        
        return {
            "service_metrics": {
                **self.service_metrics,
                "success_rate": round(success_rate, 4),
                "error_rate": round(error_rate, 4),
                "uptime_seconds": round(uptime_seconds, 2),
                "requests_per_minute": round(requests_per_minute, 2)
            },
            "orchestrator_metrics": orchestrator_metrics,
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get simple service status"""
        return {
            "running": self.is_running,
            "initialized": bool(self.orchestrator),
            "database_connected": bool(self.database and self.database.pool),
            "total_requests": self.service_metrics["total_requests"],
            "timestamp": datetime.now().isoformat()
        }
    
    async def restart(self) -> Dict[str, Any]:
        """Restart the service"""
        try:
            print("🔄 Restarting Standalone Orchestrator Service...")
            
            # Shutdown first
            await self.shutdown()
            
            # Wait a moment
            import asyncio
            await asyncio.sleep(1)
            
            # Reinitialize
            await self.initialize()
            
            return {
                "success": True,
                "message": "Service restarted successfully",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to restart service",
                "timestamp": datetime.now().isoformat()
            }
    
    async def shutdown(self):
        """Gracefully shutdown the service"""
        try:
            print("🛑 Shutting down Standalone Orchestrator Service...")
            
            # Mark as not running
            self.is_running = False
            
            # Close database connection
            if self.database:
                await self.database.close()
                self.database = None
            
            # Clear orchestrator
            self.orchestrator = None
            
            print("✅ Standalone Orchestrator Service shutdown complete")
            
        except Exception as e:
            print(f"❌ Error during service shutdown: {e}")
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get basic service information"""
        return {
            "service_name": "Standalone Orchestrator Service",
            "version": "1.0.0",
            "description": "Independent service for processing natural language messages with intelligent routing",
            "capabilities": [
                "Multi-language expense tracking",
                "Natural language reminder setting",
                "Intelligent message routing",
                "Multi-platform user support",
                "Real-time health monitoring"
            ],
            "supported_platforms": ["telegram", "whatsapp", "mobile_app", "web_app"],
            "supported_languages": ["en", "es", "pt", "fr"],
            "supported_currencies": ["USD", "EUR", "BRL", "GBP", "JPY", "CNY"],
            "database_required": True,
            "llm_provider": "Groq",
            "is_running": self.is_running,
            "initialized": bool(self.orchestrator)
        }
    
    async def validate_request(self, message: str, platform_type: str, platform_user_id: str) -> Dict[str, Any]:
        """Validate a request before processing"""
        
        validation_errors = []
        
        # Validate message
        if not message or not message.strip():
            validation_errors.append("Message cannot be empty")
        elif len(message) > 1000:
            validation_errors.append("Message too long (max 1000 characters)")
        
        # Validate platform type
        valid_platforms = ["telegram", "whatsapp", "mobile_app", "web_app"]
        if platform_type not in valid_platforms:
            validation_errors.append(f"Invalid platform type. Must be one of: {valid_platforms}")
        
        # Validate platform user ID
        if not platform_user_id or not platform_user_id.strip():
            validation_errors.append("Platform user ID cannot be empty")
        elif len(platform_user_id) > 100:
            validation_errors.append("Platform user ID too long (max 100 characters)")
        
        return {
            "valid": len(validation_errors) == 0,
            "errors": validation_errors,
            "message": "Request validation passed" if len(validation_errors) == 0 else f"Validation failed: {'; '.join(validation_errors)}"
        }

# ============================================================================
# CONVENIENCE FUNCTIONS FOR COMMON USAGE PATTERNS
# ============================================================================

async def create_service(groq_api_key: str, database_url: str, auto_initialize: bool = True) -> StandaloneOrchestratorService:
    """
    Convenience function to create and optionally initialize the service
    
    Args:
        groq_api_key: Groq API key
        database_url: Database connection URL
        auto_initialize: Whether to automatically initialize the service
        
    Returns:
        Configured StandaloneOrchestratorService instance
    """
    service = StandaloneOrchestratorService(groq_api_key, database_url)
    
    if auto_initialize:
        await service.initialize()
    
    return service

async def process_message_simple(service: StandaloneOrchestratorService, message: str, platform: str = "web_app", user_id: str = "default_user") -> str:
    """
    Convenience function for simple message processing
    
    Args:
        service: Initialized service instance
        message: User message
        platform: Platform type (default: web_app)
        user_id: User identifier (default: default_user)
        
    Returns:
        Response message string
    """
    result = await service.process_request(message, platform, user_id)
    return result.get("message", "Error processing message")

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def example_usage():
    """Example of how to use the standalone orchestrator service"""
    
    # Create and initialize service
    service = await create_service(
        groq_api_key="your_groq_api_key",
        database_url="postgresql://user:pass@localhost/db"
    )
    
    # Process individual messages
    test_messages = [
        ("Coffee $4.50", "telegram", "user123"),
        ("Remind me to call mom tomorrow at 3pm", "whatsapp", "user456"),
        ("Show my expense summary", "mobile_app", "user789"),
        ("Café €5.50 au Starbucks", "web_app", "user321"),
        ("Hola, ¿cómo estás?", "telegram", "user654"),
    ]
    
    print("🧪 Processing individual messages...")
    for message, platform, user_id in test_messages:
        result = await service.process_request(message, platform, user_id)
        print(f"Message: {message}")
        print(f"Success: {result['success']}")
        print(f"Response: {result['message']}")
        print(f"Processing Time: {result.get('processing_time_ms', 0)}ms")
        print("-" * 50)
    
    # Process batch requests
    batch_requests = [
        {"message": "Lunch $15", "platform_type": "mobile_app", "platform_user_id": "batch_user_1"},
        {"message": "Remind me about meeting", "platform_type": "web_app", "platform_user_id": "batch_user_2"},
        {"message": "What did I spend today?", "platform_type": "telegram", "platform_user_id": "batch_user_3"},
    ]
    
    print("\n🧪 Processing batch requests...")
    batch_result = await service.process_batch_requests(batch_requests)
    print(f"Batch processed: {batch_result['successful_count']}/{batch_result['batch_size']} successful")
    print(f"Total processing time: {batch_result['processing_time_ms']}ms")
    
    # Check health and metrics
    print("\n📊 Service Health and Metrics...")
    health = await service.get_health()
    print(f"Service Status: {health['status']}")
    print(f"Success Rate: {health['success_rate']:.2%}")
    print(f"Uptime: {health['uptime_seconds']:.1f} seconds")
    
    metrics = await service.get_metrics()
    print(f"Total Requests: {metrics['service_metrics']['total_requests']}")
    print(f"Requests/min: {metrics['service_metrics']['requests_per_minute']:.1f}")
    
    # Get service info
    info = service.get_service_info()
    print(f"\n📋 Service Info:")
    print(f"Service: {info['service_name']} v{info['version']}")
    print(f"Supported Platforms: {', '.join(info['supported_platforms'])}")
    print(f"Supported Languages: {', '.join(info['supported_languages'])}")
    
    # Shutdown
    await service.shutdown()

# Run example
if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())