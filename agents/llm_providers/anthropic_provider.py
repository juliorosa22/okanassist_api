# agents/llm_providers/anthropic_provider.py
import anthropic
from .base_llm_provider import BaseLLMProvider
from typing import Dict, Optional, Any, List

class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude LLM provider implementation
    """
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229", **kwargs):
        super().__init__(api_key, model, **kwargs)
        
        # Initialize Anthropic client
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=kwargs.get("timeout", 30)
        )
        
        # Default parameters
        self.temperature = kwargs.get("temperature", 0.1)
        self.max_tokens = kwargs.get("max_tokens", 1000)
    
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
        """
        Generate response using Anthropic Claude
        
        Args:
            messages: List of messages in standard format
            **kwargs: Generation parameters
            
        Returns:
            Generated response text
        """
        try:
            # Convert messages to Anthropic format
            system_message = ""
            user_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    user_messages.append(msg)
            
            # Use parameters from kwargs or defaults
            temperature = kwargs.get("temperature", self.temperature)
            max_tokens = kwargs.get("max_tokens", self.max_tokens)
            
            response = await self.client.messages.create(
                model=self.model,
                system=system_message,
                messages=user_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if response.content and response.content[0].text:
                return response.content[0].text.strip()
            
            return None
            
        except Exception as e:
            print(f"❌ Anthropic generation error: {e}")
            return None
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get Anthropic provider information"""
        return {
            "provider": "Anthropic",
            "model": self.model,
            "api_base": "https://api.anthropic.com",
            "supports_streaming": True,
            "supports_functions": False,  # Depends on model
            "max_context_length": 200000,  # Claude 3 has large context
            "config": self.config
        }
    
    async def health_check(self) -> bool:
        """Check if Anthropic is available"""
        try:
            test_messages = [{"role": "user", "content": "test"}]
            response = await self.generate_response(test_messages)
            return response is not None
        except Exception:
            return False