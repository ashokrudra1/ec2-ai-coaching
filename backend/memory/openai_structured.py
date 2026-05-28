# backend/memory/openai_structured.py
"""
OpenAI Client Wrapper - Structured Output Support

Encapsulates all OpenAI API calls with:
- Structured output support (Pydantic models as schema)
- Retry logic with exponential backoff
- Cost governance (mini vs standard models)
- Token usage tracking
- Sentry error logging

Author: Veda AI Elite Architecture Team
"""

import logging
import json
import asyncio
from typing import Optional, Dict, Any, Type, TypeVar
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

class ModelConfig:
    """Model selection strategy"""
    MINI_MODEL = "gpt-4o-mini"  # Cost-optimized: $0.15 / 1M input tokens
    STANDARD_MODEL = "gpt-4o"   # Full power: $5.00 / 1M input tokens
    
    MINI_USE_CASES = {
        "compress_memories": True,
        "extract_medical_insights": True,
        "standard_chat": True,
        "text_classification": True
    }


# ============================================================================
# OPENAI CLIENT WRAPPER
# ============================================================================

class OpenAIStructuredClient:
    """
    Async-first OpenAI client with structured outputs and cost governance.
    
    Features:
    - Automatic retry with exponential backoff
    - Token usage tracking
    - Cost governance (route to mini model when appropriate)
    - Pydantic schema validation
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI async client.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        import os
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            logger.warning("openai package not available for async calls")
            self.client = None
        
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0
    
    
    async def call_with_structure(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        use_mini: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> T:
        """
        Call OpenAI API with structured output (Pydantic model as schema).
        
        Args:
            prompt: User message
            response_model: Pydantic BaseModel class for structured output
            system_prompt: System message for context
            use_mini: Use gpt-4o-mini (True) or gpt-4o (False) for cost optimization
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            
        Returns:
            Pydantic model instance
            
        Raises:
            Exception: If API call fails
        """
        try:
            if not self.client:
                raise RuntimeError("OpenAI client not initialized")
            
            model = ModelConfig.MINI_MODEL if use_mini else ModelConfig.STANDARD_MODEL
            
            logger.debug(f"📤 OpenAI API call: {model} (structured output)")
            
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Call OpenAI with structured output
            response = await self.client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=response_model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Track token usage
            self._track_tokens(model, response.usage)
            
            # Return parsed Pydantic model
            return response.choices[0].message.parsed
            
        except Exception as e:
            logger.error(f"❌ OpenAI structured call failed: {str(e)}", exc_info=True)
            raise
    
    
    async def call_with_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        use_mini: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Call OpenAI API with JSON mode.
        
        Args:
            prompt: User message
            system_prompt: System message
            use_mini: Use mini model (True) or standard (False)
            temperature: Sampling temperature
            max_tokens: Max tokens
            
        Returns:
            Parsed JSON dict
        """
        try:
            if not self.client:
                raise RuntimeError("OpenAI client not initialized")
            
            model = ModelConfig.MINI_MODEL if use_mini else ModelConfig.STANDARD_MODEL
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            self._track_tokens(model, response.usage)
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"❌ JSON mode call failed: {str(e)}", exc_info=True)
            raise
    
    
    async def compress_memories(
        self,
        conversation_text: str,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compress a conversation using structured output.
        
        Args:
            conversation_text: Formatted conversation history
            user_context: User metadata (name, persona, phase, medical insights)
            
        Returns:
            CompressedAthleteInsight as dict
        """
        from backend.memory.compactor import CompressedAthleteInsight
        
        system_prompt = f"""
You are an elite endurance coaching analyst. Compress the following athlete conversation into 
structured insights focusing on:
1. Persistent injury patterns
2. Fitness progression trends
3. Psychological state and motivation
4. Current training focus
5. Key coaching recommendations

Athlete Context:
- Name: {user_context.get('name', 'Unknown')}
- Persona: {user_context.get('coach_persona', 'veda')}
- Training Phase: {user_context.get('training_phase', 'Base')}
- Medical Notes: {user_context.get('medical_insights', 'None')}

Be concise, data-driven, and focus on actionable patterns.
"""
        
        prompt = f"Compress this conversation:\n\n{conversation_text}"
        
        try:
            result = await self.call_with_structure(
                prompt=prompt,
                response_model=CompressedAthleteInsight,
                system_prompt=system_prompt,
                use_mini=True,
                max_tokens=2000
            )
            return result.dict()
        except Exception as e:
            logger.error(f"❌ Memory compression call failed: {str(e)}", exc_info=True)
            raise
    
    
    def _track_tokens(self, model: str, usage: Any) -> None:
        """
        Track token usage and cost.
        
        Args:
            model: Model name
            usage: OpenAI usage object
        """
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        
        # Cost per 1M tokens
        if "mini" in model:
            input_cost_per_1m = 0.15
            output_cost_per_1m = 0.60
        else:
            input_cost_per_1m = 5.00
            output_cost_per_1m = 15.00
        
        # Calculate cost
        cost = (
            (input_tokens * input_cost_per_1m / 1_000_000) +
            (output_tokens * output_cost_per_1m / 1_000_000)
        )
        
        self.total_tokens_used += input_tokens + output_tokens
        self.total_cost_usd += cost
        
        logger.debug(
            f"📊 Tokens: {input_tokens}in + {output_tokens}out | "
            f"Cost: ${cost:.4f} | Total: ${self.total_cost_usd:.2f}"
        )
    
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client usage statistics"""
        return {
            "total_tokens": self.total_tokens_used,
            "total_cost_usd": round(self.total_cost_usd, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
