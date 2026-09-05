"""Data models for OpenAI-compatible LLM structure review."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Configuration for OpenAI-compatible LLM structure review."""

    enabled: bool = False
    base_url: str = "https://api.openai.com/v1"
    api_key: str | None = None
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 30.0
    temperature: float = 0.0
    max_tokens: int = 1000
    extra_headers: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_env(cls, **overrides: Any) -> LLMConfig:
        """Create configuration with environment variable fallbacks."""
        enabled_str = os.environ.get("MDOOK_LLM_ENABLED", "").lower().strip()
        enabled = enabled_str in ("1", "true", "yes", "on")

        base_url = os.environ.get(
            "MDOOK_LLM_BASE_URL",
            os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        api_key = os.environ.get(
            "MDOOK_LLM_API_KEY",
            os.environ.get("OPENAI_API_KEY"),
        )
        model = os.environ.get("MDOOK_LLM_MODEL", "gpt-4o-mini")

        timeout_env = os.environ.get("MDOOK_LLM_TIMEOUT")
        timeout_seconds = float(timeout_env) if timeout_env else 30.0

        data: dict[str, Any] = {
            "enabled": enabled,
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "timeout_seconds": timeout_seconds,
        }
        data.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**data)


class SkeletonItem(BaseModel):
    """A single candidate heading and its immediate context in the skeleton."""

    id: int
    level: int
    page_number: int
    title: str
    first_body_snippet: str | None = None


CorrectionAction = Literal["demote_to_body", "set_level", "set_part", "keep"]


class HeadingCorrection(BaseModel):
    """A suggested correction from the LLM reviewer."""

    id: int
    action: CorrectionAction
    new_level: int | None = None
    reason: str | None = None


class StructureReviewResult(BaseModel):
    """Result of an AI structure review pass."""

    attempted: bool = False
    success: bool = False
    corrections_applied: list[HeadingCorrection] = Field(default_factory=list)
    raw_response: str | None = None
    error_message: str | None = None
