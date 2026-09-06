"""Prompt templates and skeleton serialization for AI structure review."""

from __future__ import annotations

from mdook.core.llm.models import SkeletonItem

SYSTEM_PROMPT = """You are an expert bibliographer and document structure reviewer.
Your job is to validate and correct candidate headings extracted from a PDF book
by an automated layout parser.

Analyze the provided outline skeleton. Look specifically for:
1. OCR artifacts or fragmented prose mistakenly tagged as headings
   (e.g. mid-sentence text, broken words).
2. Leaked running headers or page numbers that slipped through.
3. Level inconsistencies (e.g. "Chapter 2" tagged as L2 while "Chapter 1" is L1).
4. Major divisions: distinguish "Part / Book / Volume" divisions from regular Chapters.

CRITICAL INSTRUCTIONS:
- You are a REVIEWER, NOT a generator. Do NOT write summaries, explanations, or book content.
- Respond ONLY with a valid JSON object matching the schema below.
- If the detected structure is already correct, return: {"corrections": []}.
- Only suggest corrections for clear errors. When uncertain, keep the existing classification.

Allowed actions:
- "demote_to_body": Reject this heading; it is ordinary body text, OCR debris, or running header.
- "set_level": Change heading tier (specify "new_level": 1 for chapters, 2 for subheadings, etc.).
- "set_part": Mark as a Part/Book/Volume division above the chapter tier.

JSON Schema:
{
  "corrections": [
    {
      "id": <integer ID from the skeleton>,
      "action": "demote_to_body" | "set_level" | "set_part",
      "new_level": <integer, required if action is set_level>,
      "reason": "<brief justification>"
    }
  ]
}
"""


def format_skeleton(
    items: list[SkeletonItem],
    book_title: str | None = None,
    author: str | None = None,
) -> str:
    """Serialize heading candidates into a compact, token-efficient text skeleton."""
    lines: list[str] = []
    if book_title:
        lines.append(f"Book Title: {book_title}")
    if author:
        lines.append(f"Author: {author}")
    lines.append("\nDetected Heading Skeleton:")

    for item in items:
        prefix = "  " * max(0, item.level - 1)
        loc = f"[ID {item.id}] L{item.level} (p. {item.page_number})"
        lines.append(f'{prefix}{loc}: "{item.title}"')
        if item.first_body_snippet:
            snippet = item.first_body_snippet.replace("\n", " ").strip()
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            lines.append(f'{prefix}  > "{snippet}"')

    lines.append(
        "\nReturn your review as a JSON object with 'corrections'. "
        "Output JSON only, no markdown commentary."
    )
    return "\n".join(lines)
