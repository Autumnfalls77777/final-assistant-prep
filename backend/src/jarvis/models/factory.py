"""Build the configured model router."""

from __future__ import annotations

from ..config import Settings
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .router import ModelRouter
from .schemas import ProviderName


def build_model_router(settings: Settings) -> ModelRouter:
    """Create providers from validated settings without making network calls."""

    providers = {
        ProviderName.GEMINI: GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.model_timeout_seconds,
        ),
        ProviderName.OLLAMA: OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.model_timeout_seconds,
        ),
    }
    return ModelRouter(
        providers=providers,
        default_provider=ProviderName(settings.default_model_provider),
        fallback_enabled=settings.local_fallback_enabled,
    )
