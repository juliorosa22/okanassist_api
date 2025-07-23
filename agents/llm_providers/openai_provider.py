# agents/llm_providers/openai_provider.py
import openai
from .base_llm_provider import BaseLLMProvider
from typing import Dict, Optional, Any, List

class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI LLM provider implementation
    """
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", **kwargs):
        super().__init__(api_key, model, **kwargs)
        
        # Initialize OpenAI client
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            timeout=kwargs.get("timeout", 30)
        )
        
        # Default parameters
        self.temperature = kwargs.get("temperature", 0.1)
        self.max_tokens = kwargs.get("max_tokens", 1000)
    
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
        """
        Generate response using OpenAI
        
        Args:
            messages: List of messages in standard format
            **kwargs: Generation parameters
            
        Returns:
            Generated response text
        """
        try:
            # Use parameters from kwargs or defaults
            temperature = kwargs.get("temperature", self.temperature)
            max_tokens = kwargs.get("max_tokens", self.max_tokens)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # OpenAI uses same format
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content.strip()
            
            return None
            
        except Exception as e:
            print(f"❌ OpenAI generation error: {e}")
            return None
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get OpenAI provider information"""
        return {
            "provider": "OpenAI",
            "model": self.model,
            "api_base": "https://api.openai.com",
            "supports_streaming": True,
            "supports_functions": True,
            "max_context_length": 4096 if "gpt-3.5" in self.model else 8192,
            "config": self.config
        }
    
    async def health_check(self) -> bool:
        """Check if OpenAI is available"""
        try:
            test_messages = [{"role": "user", "content": "test"}]
            response = await self.generate_response(test_messages)
            return response is not None
        except Exception:
            return False