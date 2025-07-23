# agents/llm_providers/factory.py
from typing import Dict, Type, List
from .base_llm_provider import BaseLLMProvider
from .groq_provider import GroqProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider

class LLMProviderFactory:
    """
    Factory class for creating LLM providers
    """
    
    # Registry of available providers
    _providers: Dict[str, Type[BaseLLMProvider]] = {
        "groq": GroqProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_name: str, api_key: str, model: str, **kwargs) -> BaseLLMProvider:
        """
        Create an LLM provider instance
        
        Args:
            provider_name: Name of provider (groq, openai, anthropic)
            api_key: API key for the provider
            model: Model name to use
            **kwargs: Provider-specific configuration
            
        Returns:
            Initialized LLM provider instance
            
        Raises:
            ValueError: If provider not found
        """
        provider_name = provider_name.lower()
        
        if provider_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Unknown provider '{provider_name}'. Available: {available}")
        
        provider_class = cls._providers[provider_name]
        return provider_class(api_key, model, **kwargs)
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseLLMProvider]):
        """
        Register a new LLM provider
        
        Args:
            name: Provider name
            provider_class: Provider class that extends BaseLLMProvider
        """
        cls._providers[name.lower()] = provider_class
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available provider names"""
        return list(cls._providers.keys())