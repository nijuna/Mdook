"""OpenAI-compatible LLM structure review package."""

from mdook.core.llm.client import (
    LLMClientError,
    OpenAICompatibleClient,
    normalize_models_endpoint,
)
from mdook.core.llm.models import (
    HeadingCorrection,
    LLMConfig,
    SkeletonItem,
    StructureReviewResult,
)
from mdook.core.llm.review import (
    build_skeleton,
    extract_json_payload,
    parse_corrections,
    run_structure_review,
    validate_corrections,
)

__all__ = [
    "LLMClientError",
    "OpenAICompatibleClient",
    "normalize_models_endpoint",
    "LLMConfig",
    "SkeletonItem",
    "HeadingCorrection",
    "StructureReviewResult",
    "build_skeleton",
    "extract_json_payload",
    "parse_corrections",
    "run_structure_review",
    "validate_corrections",
]
