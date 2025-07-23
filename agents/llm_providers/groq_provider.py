# agents/llm_providers/groq_provider.py
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from .base_llm_provider import BaseLLMProvider
from typing import Dict, Optional, Any, List

class GroqProvider(BaseLLMProvider):
    """
    Groq LLM provider implementation
    """
    
    def __init__(self, api_key: str, model: str = "llama3-70b-8192", **kwargs):
        super().__init__(api_key, model, **kwargs)
        
        # Initialize Groq client
        self.client = ChatGroq(
            model=model,
            api_key=api_key,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", None),
            timeout=kwargs.get("timeout", 30)
        )
    
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
        """
        Generate response using Groq
        
        Args:
            messages: List of messages in standard format
            **kwargs: Generation parameters
            
        Returns:
            Generated response text
        """
        try:
            # Convert standard format to LangChain messages
            langchain_messages = self._convert_to_langchain_messages(messages)
            
            # Generate response
            response = await self.client.ainvoke(langchain_messages)
            
            if response and response.content:
                return response.content.strip()
            
            return None
            
        except Exception as e:
            print(f"❌ Groq generation error: {e}")
            return None
    
    def _convert_to_langchain_messages(self, messages: List[Dict[str, str]]) -> List:
        """Convert standard message format to LangChain messages"""
        langchain_messages = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
        
        return langchain_messages
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get Groq provider information"""
        return {
            "provider": "Groq",
            "model": self.model,
            "api_base": "https://api.groq.com",
            "supports_streaming": True,
            "supports_functions": True,
            "max_context_length": 8192,  # Depends on model
            "config": self.config
        }
    
    async def health_check(self) -> bool:
        """Check if Groq is available"""
        try:
            test_messages = [{"role": "user", "content": "test"}]
            response = await self.generate_response(test_messages)
            return response is not None
        except Exception:
            return False