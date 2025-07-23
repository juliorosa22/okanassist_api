from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
import asyncio

class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers
    Enables pluggable LLM backends (Groq, OpenAI, Anthropic, etc.)
    """
    
    def __init__(self, api_key: str, model: str, **kwargs):
        """
        Initialize LLM provider
        
        Args:
            api_key: API key for the provider
            model: Model name to use
            **kwargs: Provider-specific configuration
        """
        self.api_key = api_key
        self.model = model
        self.config = kwargs
        self.provider_name = self.__class__.__name__.replace("Provider", "")
    
    @abstractmethod
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
        """
        Generate response from LLM
        
        Args:
            messages: List of messages in format [{"role": "system|user|assistant", "content": "text"}]
            **kwargs: Generation parameters (temperature, max_tokens, etc.)
            
        Returns:
            Generated response text or None if failed
        """
        pass
    
    @abstractmethod
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about this provider
        
        Returns:
            Dictionary with provider details
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is available
        
        Returns:
            True if provider is healthy, False otherwise
        """
        pass