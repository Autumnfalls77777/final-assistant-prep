"""Validated application configuration."""

from __future__ import annotations

import ipaddress
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings for the currently implemented phases.

    Only settings required by Phases 0-3 are modeled. Later-phase keys in
    ``.env`` remain intentionally ignored until those phases are authorized.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    timezone: str = "UTC"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1024, le=65535)
    audit_log_path: Path = Path("var/audit.jsonl")

    default_model_provider: Literal["gemini", "ollama"] = "gemini"
    local_fallback_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1"
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_key: SecretStr | None = None
    model_timeout_seconds: float = Field(default=60.0, ge=1.0, le=300.0)
    max_tool_iterations: int = Field(default=3, ge=1, le=6)
    max_tool_calls_per_turn: int = Field(default=8, ge=1, le=20)

    memory_db_path: Path = Path("var/jarvis.db")
    memory_max_results: int = Field(default=5, ge=1, le=10)
    memory_min_score: float = Field(default=0.12, ge=0.0, le=1.0)
    memory_retention_days: int = Field(default=365, ge=1, le=3650)
    memory_working_ttl_hours: int = Field(default=24, ge=1, le=720)
    memory_context_max_chars: int = Field(default=4000, ge=500, le=8000)
    memory_auto_store_chat: bool = True

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_app_env(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        return {"dev": "development", "prod": "production", "testing": "test"}.get(
            normalized, normalized
        )

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().upper()
        return "WARNING" if normalized == "WARN" else normalized

    @field_validator("default_model_provider", mode="before")
    @classmethod
    def _normalize_model_provider(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().lower()

    @field_validator("gemini_model", "ollama_model")
    @classmethod
    def _require_model_name(cls, value: str) -> str:
        model_name = value.strip()
        if not model_name:
            raise ValueError("Model names must not be empty")
        return model_name

    @field_validator("api_host")
    @classmethod
    def _require_loopback_host(cls, value: str) -> str:
        host = value.strip()
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("API_HOST must be a loopback IP address (127.0.0.1 or ::1)") from exc
        if not address.is_loopback:
            raise ValueError("API_HOST must be a loopback IP address (127.0.0.1 or ::1)")
        return host

    @field_validator("timezone")
    @classmethod
    def _require_valid_timezone(cls, value: str) -> str:
        timezone_name = value.strip()
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("TIMEZONE must be a valid IANA timezone") from exc
        return timezone_name

    @field_validator("ollama_base_url")
    @classmethod
    def _require_loopback_ollama_url(cls, value: str) -> str:
        raw_url = value.strip().rstrip("/")
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("OLLAMA_BASE_URL must use http or https")
        if not parsed.hostname:
            raise ValueError("OLLAMA_BASE_URL must include a hostname")
        if parsed.username or parsed.password:
            raise ValueError("OLLAMA_BASE_URL must not include credentials")
        if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("OLLAMA_BASE_URL must be an origin without a path or query")
        if parsed.hostname != "localhost":
            try:
                address = ipaddress.ip_address(parsed.hostname)
            except ValueError as exc:
                raise ValueError("OLLAMA_BASE_URL must point to loopback") from exc
            if not address.is_loopback:
                raise ValueError("OLLAMA_BASE_URL must point to loopback")
        return raw_url


@lru_cache
def get_settings() -> Settings:
    """Return cached, validated settings loaded from the project .env file."""

    return Settings()
