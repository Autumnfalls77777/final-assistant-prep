"""Model-provider errors with safe public messages."""

from __future__ import annotations

from collections.abc import Sequence

from .schemas import ProviderName


class ModelProviderError(Exception):
    """Base error raised by a configured model provider."""

    def __init__(self, provider: ProviderName, message: str) -> None:
        self.provider = provider
        super().__init__(message)


class ProviderUnavailableError(ModelProviderError):
    """The provider is not configured or cannot be reached."""


class ProviderResponseError(ModelProviderError):
    """The provider responded with unusable or unsuccessful output."""


class NoProviderAvailableError(Exception):
    """Every configured provider attempt failed."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = list(errors)
        detail = "; ".join(self.errors) if self.errors else "No providers are configured."
        super().__init__(f"No model provider is available. {detail}")
