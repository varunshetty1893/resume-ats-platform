"""Zentra AI Provider Framework.

Exported components:
- ai_service: Central orchestration singleton with Gemini -> Groq -> Local fallback
- AIService: Main service class
- BaseAIProvider: Provider interface
- GeminiAIProvider: Google Gemini implementation
- GroqAIProvider: Groq Llama implementation
- LocalAIProvider: Local deterministic fallback
"""

from app.ai.base import BaseAIProvider
from app.ai.gemini_provider import GeminiAIProvider
from app.ai.groq_provider import GroqAIProvider
from app.ai.local_provider import LocalAIProvider
from app.ai.service import AIService, ai_service

__all__ = [
    "ai_service",
    "AIService",
    "BaseAIProvider",
    "GeminiAIProvider",
    "GroqAIProvider",
    "LocalAIProvider",
]
