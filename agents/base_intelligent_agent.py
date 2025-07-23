# agents/base_intelligent_agent.py (Updated version)
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
import json
import re
import asyncio
from datetime import datetime

from .llm_providers import LLMProviderFactory, BaseLLMProvider

class BaseIntelligentAgent(ABC):
    """
    Abstract base class for all intelligent agents with modular LLM support
    """
    
    def __init__(self, llm_config: Dict[str, Any], database):
        """
        Initialize base agent with modular LLM provider
        
        Args:
            llm_config: LLM configuration dict with keys:
                - provider: "groq", "openai", "anthropic"
                - api_key: API key for the provider
                - model: Model name to use
                - **kwargs: Provider-specific options
            database: Database instance for data operations
        """
        self.database = database
        self.llm_config = llm_config
        
        # Create LLM provider using factory
        self.llm_provider: BaseLLMProvider = LLMProviderFactory.create_provider(
            provider_name=llm_config["provider"],
            api_key=llm_config["api_key"],
            model=llm_config["model"],
            **llm_config.get("options", {})
        )
        
        # Shared utilities and caches
        self.response_cache = {}
        self.user_context_cache = {}
        self.max_cache_size = 100
        
        print(f"✅ Initialized agent with {self.llm_provider.provider_name} provider")
    
    # ============================================================================
    # MODULAR LLM OPERATIONS
    # ============================================================================
    
    async def safe_llm_call(self, messages: List[Dict[str, str]], max_retries: int = 3, 
                           timeout: int = 30, cache: bool = True, **generation_kwargs) -> Optional[str]:
        """
        Resilient LLM call with support for any provider
        
        Args:
            messages: List of messages in standard format [{"role": "system|user", "content": "text"}]
            max_retries: Maximum retry attempts
            timeout: Timeout in seconds
            cache: Whether to cache the response
            **generation_kwargs: Provider-specific generation parameters
            
        Returns:
            LLM response content or None if all retries failed
        """
        # Create cache key from messages
        cache_key = str(hash(str(messages))) if cache else None
        
        # Check cache first
        if cache and cache_key in self.response_cache:
            return self.response_cache[cache_key]
        
        for attempt in range(max_retries):
            try:
                # Use modular LLM provider
                response = await asyncio.wait_for(
                    self.llm_provider.generate_response(messages, **generation_kwargs),
                    timeout=timeout
                )
                
                if response:
                    # Cache successful responses (with size limit)
                    if cache and len(self.response_cache) < self.max_cache_size:
                        self.response_cache[cache_key] = response
                    
                    return response
                else:
                    print(f"⚠️ Empty LLM response on attempt {attempt + 1}")
                    
            except asyncio.TimeoutError:
                print(f"⚠️ LLM timeout on attempt {attempt + 1}/{max_retries}")
                
            except Exception as e:
                print(f"⚠️ LLM error on attempt {attempt + 1}/{max_retries}: {e}")
                
                # Exponential backoff for retries
                if attempt < max_retries - 1:
                    wait_time = min(0.5 * (2 ** attempt), 5)  # Max 5 seconds
                    await asyncio.sleep(wait_time)
        
        print(f"❌ All LLM retry attempts failed after {max_retries} tries")
        return None
    
    async def switch_llm_provider(self, new_config: Dict[str, Any]) -> bool:
        """
        Switch to a different LLM provider at runtime
        
        Args:
            new_config: New LLM configuration
            
        Returns:
            True if switch successful, False otherwise
        """
        try:
            # Create new provider
            new_provider = LLMProviderFactory.create_provider(
                provider_name=new_config["provider"],
                api_key=new_config["api_key"],
                model=new_config["model"],
                **new_config.get("options", {})
            )
            
            # Test the new provider
            if await new_provider.health_check():
                old_provider = self.llm_provider.provider_name
                self.llm_provider = new_provider
                self.llm_config = new_config
                
                # Clear cache since we're using a different provider
                self.clear_cache()
                
                print(f"✅ Switched from {old_provider} to {new_provider.provider_name}")
                return True
            else:
                print(f"❌ New provider {new_config['provider']} failed health check")
                return False
                
        except Exception as e:
            print(f"❌ Error switching LLM provider: {e}")
            return False
    
    def get_llm_info(self) -> Dict[str, Any]:
        """Get current LLM provider information"""
        return self.llm_provider.get_provider_info()
    
    async def llm_health_check(self) -> bool:
        """Check if current LLM provider is healthy"""
        return await self.llm_provider.health_check()
    
    # ... rest of the BaseIntelligentAgent methods remain the same ...
    # (keeping the previous user context, validation, and utility methods)
    
    # ============================================================================
    # ABSTRACT METHODS (Must be implemented by subclasses)
    # ============================================================================
    
    @abstractmethod
    async def process_message(self, message: str, platform_type: str, platform_user_id: str) -> str:
        """Process a message - main entry point for each agent"""
        pass
    
    @abstractmethod
    async def get_user_patterns(self, user_id: str) -> Dict[str, Any]:
        """Get user patterns specific to this agent type"""
        pass
    
    @abstractmethod
    def _get_response_template(self, template_key: str, context: Dict[str, Any], language: str) -> str:
        """Get response template for this agent type"""
        pass