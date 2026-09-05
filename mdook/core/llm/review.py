"""Structure review orchestrator, skeleton builder, and guardrail validator."""

from __future__ import annotations

import json
import re
from typing import Any

from mdook.core.llm.client import OpenAICompatibleClient
from mdook.core.llm.models import HeadingCorrection, LLMConfig, SkeletonItem, StructureReviewResult
from mdook.core.llm.prompts import SYSTEM_PROMPT, format_skeleton
from mdook.core.models import BookManifest, PageData, TextBlock
from mdook.core.rules.headings import Heading


def build_skeleton(
    headings: list[Heading],
    pages: list[PageData],
) -> list[SkeletonItem]:
    """Build a compact skeleton of heading candidates with opening body snippets."""
    pages_by_number = {page.page_number: page for page in pages}
    items: list[SkeletonItem] = []

    for idx, heading in enumerate(headings):
        snippet: str | None = None
        if heading.block is not None:
            page = pages_by_number.get(heading.page_number)
            if page is not None:
                text_blocks = [b for b in page.blocks if isinstance(b, TextBlock)]
                target_block = heading.extra_block or heading.block
                match_idx = next(
                    (i for i, b in enumerate(text_blocks) if b is target_block), None
                )
                if match_idx is not None and match_idx + 1 < len(text_blocks):
                    candidate_body = text_blocks[match_idx + 1].text.strip()
                    if candidate_body:
                        snippet = candidate_body[:100]

        items.append(
            SkeletonItem(
                id=idx,
                level=heading.level,
                page_number=heading.page_number,
                title=heading.title.strip(),
                first_body_snippet=snippet,
            )
        )

    return items


def extract_json_payload(raw_text: str) -> str:
    """Extract a JSON object string from raw LLM output, handling markdown code fences."""
    text = raw_text.strip()

    # If wrapped in markdown code blocks like ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Or find the outermost { ... }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip()

    return text


def parse_corrections(response_text: str) -> list[HeadingCorrection]:
    """Parse and validate JSON response into a list of HeadingCorrection objects."""
    clean_json = extract_json_payload(response_text)
    parsed: dict[str, Any] = json.loads(clean_json)

    corrections_raw = parsed.get("corrections", [])
    if not isinstance(corrections_raw, list):
        return []

    corrections: list[HeadingCorrection] = []
    for item in corrections_raw:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        action = item.get("action")
        if item_id is None or action is None:
            continue
        try:
            correction = HeadingCorrection(
                id=int(item_id),
                action=str(action),
                new_level=int(item["new_level"]) if item.get("new_level") is not None else None,
                reason=str(item.get("reason", "")),
            )
            corrections.append(correction)
        except Exception:
            continue

    return corrections


def validate_corrections(
    corrections: list[HeadingCorrection],
    total_headings: int,
) -> list[HeadingCorrection]:
    """Filter out invalid corrections using strict guardrails."""
    valid: list[HeadingCorrection] = []
    seen_ids: set[int] = set()

    for c in corrections:
        if c.id < 0 or c.id >= total_headings:
            continue
        if c.id in seen_ids:
            continue
        if c.action not in ("demote_to_body", "set_level", "set_part", "keep"):
            continue
        if c.action == "set_level":
            if c.new_level is None or c.new_level < 1:
                continue
        seen_ids.add(c.id)
        valid.append(c)

    # Guardrail: Never allow demoting all headings (which would wipe out the book's structure)
    demotions = [c for c in valid if c.action == "demote_to_body"]
    if len(demotions) >= total_headings and total_headings > 0:
        # Discard demotions if they target every single heading
        valid = [c for c in valid if c.action != "demote_to_body"]

    return valid


def run_structure_review(
    headings: list[Heading],
    pages: list[PageData],
    manifest: BookManifest,
    config: LLMConfig,
    client: OpenAICompatibleClient | None = None,
) -> tuple[list[Heading], list[Heading], StructureReviewResult]:
    """Execute AI structure review pass.

    Returns:
    - cleaned_headings: updated list of headings
    - explicit_parts: any headings promoted to Part/Book/Volume status
    - result: review outcome report
    """
    if not config.enabled or not headings:
        return headings, [], StructureReviewResult(attempted=False)

    try:
        items = build_skeleton(headings, pages)
        user_prompt = format_skeleton(
            items,
            book_title=manifest.title,
            author=manifest.author,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        llm_client = client or OpenAICompatibleClient(config)
        raw_response = llm_client.chat_completion(messages)

        candidate_corrections = parse_corrections(raw_response)
        validated = validate_corrections(candidate_corrections, len(headings))

        corrections_by_id = {c.id: c for c in validated}
        cleaned_headings: list[Heading] = []
        explicit_parts: list[Heading] = []

        for idx, h in enumerate(headings):
            corr = corrections_by_id.get(idx)
            if corr is None or corr.action == "keep":
                cleaned_headings.append(h)
            elif corr.action == "demote_to_body":
                # Rejected as a heading; remains a normal TextBlock in PageData
                continue
            elif corr.action == "set_part":
                explicit_parts.append(h)
            elif corr.action == "set_level" and corr.new_level is not None:
                h.level = corr.new_level
                cleaned_headings.append(h)
            else:
                cleaned_headings.append(h)

        return (
            cleaned_headings,
            explicit_parts,
            StructureReviewResult(
                attempted=True,
                success=True,
                corrections_applied=validated,
                raw_response=raw_response,
            ),
        )

    except Exception as err:
        # Non-fatal: degrade gracefully and proceed with heuristic output
        return (
            headings,
            [],
            StructureReviewResult(
                attempted=True,
                success=False,
                error_message=str(err),
            ),
        )
