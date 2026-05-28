# backend/llm_fallback_service.py
import os
import logging
from openai import OpenAI
import httpx

logger = logging.getLogger(__name__)

class MultiProviderLLMService:
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        
        self.openai_client = OpenAI(api_key=self.openai_key, base_url=self.openai_base_url) if (self.openai_key and self.openai_base_url) else (OpenAI(api_key=self.openai_key) if self.openai_key else None)

    def generate_completion(self, system_instruction: str, prompt: str, target_model: str | None = None, temperature: float = 0.3) -> str:
        """Attempts generation with OpenAI, falling back to Anthropic or Gemini on failure."""
        target_model = target_model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        # 1. Primary Attempt: OpenAI
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model=target_model,
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature,
                    timeout=8.0  # Fail fast to trigger fallback quickly
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"⚠️ OpenAI primary provider failed: {str(e)}. Attempting Anthropic Claude fallback...")

        # 2. Secondary Attempt: Anthropic Claude (via REST API to minimize package overhead)
        if self.anthropic_key:
            try:
                headers = {
                    "x-api-key": self.anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                # Map models safely
                claude_model = "claude-3-5-haiku-20241022" if "mini" in target_model else "claude-3-5-sonnet-20241022"
                payload = {
                    "model": claude_model,
                    "max_tokens": 400,
                    "temperature": temperature,
                    "system": system_instruction,
                    "messages": [{"role": "user", "content": prompt}]
                }
                with httpx.Client(timeout=8.0) as client:
                    resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                    if resp.status_code == 200:
                        return resp.json()["content"][0]["text"].strip()
            except Exception as anth_err:
                logger.error(f"⚠️ Anthropic fallback failed: {str(anth_err)}. Attempting Gemini fallback...")

        # 3. Tertiary Attempt: Google Gemini (via REST API)
        if self.gemini_key:
            try:
                gemini_model = "gemini-1.5-flash" if "mini" in target_model else "gemini-1.5-pro"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={self.gemini_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": f"System Instructions:\n{system_instruction}\n\nUser Prompt:\n{prompt}"}
                        ]
                    }],
                    "generationConfig": {"temperature": temperature}
                }
                with httpx.Client(timeout=8.0) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as gem_err:
                logger.critical(f"🚨 All LLM providers exhausted. Execution failed: {str(gem_err)}")
                
        raise RuntimeError("No functional LLM provider available.")

llm_router = MultiProviderLLMService()
