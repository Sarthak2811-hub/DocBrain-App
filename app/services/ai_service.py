import logging
from typing import Generator
from google import genai
from google.genai import types
from app.core.config import settings
from app.core.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class AIService:
    """Service to handle interactions with Google Gemini models using google-genai SDK."""

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is missing! Please configure it in your .env file."
            )
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_CHAT_MODEL

    def generate_stream(self, prompt: str, system_instruction: str = None) -> Generator[str, None, None]:
        """Generate a streaming response from Gemini model."""
        try:
            config = None
            if system_instruction:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2
                )
            
            response_stream = retry_with_backoff(
                self.client.models.generate_content_stream,
                model=self.model,
                contents=prompt,
                config=config
            )
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Failed to generate content stream from Gemini: {str(e)}")
            raise e

    def generate_content(self, prompt: str, system_instruction: str = None) -> str:
        """Generate a complete static response from Gemini model."""
        try:
            config = None
            if system_instruction:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2
                )
            
            response = retry_with_backoff(
                self.client.models.generate_content,
                model=self.model,
                contents=prompt,
                config=config
            )
            return response.text or ""
        except Exception as e:
            logger.error(f"Failed to generate content from Gemini: {str(e)}")
            raise e
