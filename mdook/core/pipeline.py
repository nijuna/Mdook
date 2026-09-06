"""Pipeline orchestrator — runs Stage 1 -> 5 in sequence.

Sprint 4: all five stages are real. `convert()` reads a PDF, builds the
document tree, writes an actual Obsidian vault to `output_dir / {title}/`,
and validates what it wrote. `ConversionResult.output_dir` reports that
`{title}/` subfolder -- the vault's actual location -- not the raw
`output_dir` the caller passed in.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from mdook.core.llm import LLMConfig
from mdook.core.models import ConversionResult
from mdook.core.stages.extraction import run_extraction
from mdook.core.stages.intake import run_intake
from mdook.core.stages.rendering import render_vault
from mdook.core.stages.semantic import run_semantic
from mdook.core.stages.validation import run_validation

ProgressCallback = Callable[[int, str], None]


def convert(
    pdf_path: Path,
    output_dir: Path,
    profile: str = "auto",
    on_progress: ProgressCallback | None = None,
    llm_config: LLMConfig | None = None,
    llm_client: Any | None = None,
) -> ConversionResult:
    """Convert a PDF book into an Obsidian vault, writing it to `output_dir`."""

    def report(percent: int, message: str) -> None:
        if on_progress is not None:
            on_progress(percent, message)

    effective_llm_config = llm_config if llm_config is not None else LLMConfig.from_env()

    started_at = time.monotonic()

    report(5, "Reading document metadata...")
    manifest = run_intake(pdf_path, profile_override=profile)
    report(10, f"Profile: {manifest.profile}")

    report(25, "Extracting text and images...")

    def on_page_extracted(done: int, total: int) -> None:
        # Spread across the 25-50% band reserved for extraction, rather than
        # one flat "25%" for however long extraction takes -- a scanned
        # book's per-page OCR pass (Phase 3) can otherwise look frozen for
        # minutes on end.
        percent = 25 + int(25 * done / total) if total else 25
        report(percent, f"Extracting text and images... (page {done}/{total})")

    pages = run_extraction(manifest, on_page_extracted=on_page_extracted)

    if effective_llm_config.enabled:
        report(50, "Analyzing document structure (with AI review)...")
    else:
        report(50, "Analyzing document structure...")
    tree = run_semantic(manifest, pages, llm_config=effective_llm_config, llm_client=llm_client)

    report(75, "Writing Markdown files...")
    render_result = render_vault(tree, manifest, output_dir)

    report(90, "Validating output...")
    processing_time = time.monotonic() - started_at
    validation_report = run_validation(
        tree, manifest, render_result, pages=pages, processing_time_seconds=processing_time
    )

    report(100, "Done")

    llm_review_meta = tree.metadata.extra.get("llm_review") if tree.metadata else None
    llm_review_applied = bool(isinstance(llm_review_meta, dict) and llm_review_meta.get("success"))

    return ConversionResult(
        success=True,
        output_dir=render_result.vault_dir,
        manifest=manifest,
        validation_report=validation_report,
        pages=manifest.total_pages,
        chapters=len(tree.chapters),
        footnotes=validation_report.total_footnotes,
        images=validation_report.total_images,
        llm_review_applied=llm_review_applied,
    )
