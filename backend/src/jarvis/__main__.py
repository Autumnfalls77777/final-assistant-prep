"""Run the backend with validated, loopback-only host and port settings."""

from __future__ import annotations

import uvicorn

from .config import get_settings


def main() -> None:
    """Start Uvicorn using the validated application configuration."""

    settings = get_settings()
    uvicorn.run(
        "jarvis.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        access_log=True,
    )


if __name__ == "__main__":
    main()
