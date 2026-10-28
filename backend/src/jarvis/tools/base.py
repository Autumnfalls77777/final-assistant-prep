"""Tool interface definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from .policy import RiskLevel


class BaseTool(ABC):
    """Base interface for every independently executable tool.

    Tools receive a validated Pydantic input model and return a Pydantic output
    model. The registry validates both sides, enforces the timeout, applies the
    permission policy, and writes an audit record.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    input_model: ClassVar[type[BaseModel]]
    output_model: ClassVar[type[BaseModel]]
    risk_level: ClassVar[RiskLevel]
    timeout_seconds: ClassVar[float] = 10.0

    @abstractmethod
    async def execute(self, params: BaseModel) -> BaseModel:
        """Execute the tool with already-validated parameters."""
