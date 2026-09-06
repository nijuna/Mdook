"""Mdook Command-Line Interface (CLI).

Provides headless terminal commands for converting PDF books into Obsidian vaults,
checking versions, and launching the desktop GUI.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from mdook import __version__
from mdook.core.errors import MdookError
from mdook.core.llm import LLMConfig
from mdook.core.pipeline import convert


def is_gui_available() -> bool:
    """Returns True if a graphical windowing display environment is detected."""
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def build_parser() -> argparse.ArgumentParser:
    """Constructs the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="mdook",
        description="Convert PDF books into structured, readable Obsidian vaults.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  mdook convert book.pdf -o ./vaults/
  mdook convert book1.pdf book2.pdf --profile technical
  mdook convert book.pdf --ai --ai-model gpt-4o-mini
  mdook gui
""",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"Mdook v{__version__}",
        help="Show program version and exit.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # `convert` subcommand
    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert one or more PDF books into an Obsidian vault.",
        description="Convert one or more PDF books into an Obsidian vault.",
    )
    convert_parser.add_argument(
        "pdf",
        nargs="+",
        type=Path,
        help="Path to one or more input PDF files.",
    )
    convert_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("./"),
        help="Directory where the Obsidian vault folder will be created "
        "(default: current directory).",
    )
    convert_parser.add_argument(
        "-p",
        "--profile",
        choices=["auto", "literature", "technical"],
        default="auto",
        help="Book profile: 'auto' (default: auto-detect), 'literature', or 'technical'.",
    )
    convert_parser.add_argument(
        "--ai",
        action="store_true",
        default=None,
        help="Enable AI structure review via OpenAI-compatible API.",
    )
    convert_parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Explicitly disable AI structure review.",
    )
    convert_parser.add_argument(
        "--ai-model",
        type=str,
        default=None,
        help="Model name for AI structure review (e.g. gpt-4o-mini, llama3.2).",
    )
    convert_parser.add_argument(
        "--ai-base-url",
        type=str,
        default=None,
        help="Base URL for OpenAI-compatible endpoint (e.g. http://localhost:11434/v1).",
    )
    convert_parser.add_argument(
        "--ai-api-key",
        type=str,
        default=None,
        help="API key for AI structure review (or set MDOOK_LLM_API_KEY / OPENAI_API_KEY).",
    )
    convert_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress bars and non-error output.",
    )

    # `gui` subcommand
    subparsers.add_parser(
        "gui",
        help="Launch the PySide6 graphical user interface.",
        description="Launch the PySide6 graphical user interface.",
    )

    # `version` subcommand
    subparsers.add_parser(
        "version",
        help="Display Mdook version.",
    )

    return parser


def run_convert(args: argparse.Namespace, console: Console) -> int:
    """Executes the headless conversion for specified PDF files."""
    # Prepare LLMConfig overrides
    llm_overrides: dict[str, object] = {}
    if args.no_ai:
        llm_overrides["enabled"] = False
    elif args.ai:
        llm_overrides["enabled"] = True

    if args.ai_model:
        llm_overrides["model"] = args.ai_model
    if args.ai_base_url:
        llm_overrides["base_url"] = args.ai_base_url
    if args.ai_api_key:
        llm_overrides["api_key"] = args.ai_api_key

    llm_config = LLMConfig.from_env(**llm_overrides)

    overall_exit_code = 0
    pdf_files: list[Path] = args.pdf

    for pdf_path in pdf_files:
        if not pdf_path.exists():
            console.print(f"[bold red]Error:[/bold red] File not found: '{pdf_path}'")
            overall_exit_code = 1
            continue
        if not pdf_path.is_file():
            console.print(f"[bold red]Error:[/bold red] Path is not a file: '{pdf_path}'")
            overall_exit_code = 1
            continue

        if not args.quiet:
            console.print(
                Panel.fit(
                    f"[bold cyan]Mdook[/bold cyan] v{__version__} — "
                    f"Converting [bold white]{pdf_path.name}[/bold white]\n"
                    f"Profile: [green]{args.profile}[/green] | Output: [green]{args.output}[/green]"
                    + (f" | AI: [cyan]{llm_config.model}[/cyan]" if llm_config.enabled else ""),
                    border_style="cyan",
                )
            )

        try:
            if args.quiet:
                res = convert(
                    pdf_path=pdf_path,
                    output_dir=args.output,
                    profile=args.profile,
                    on_progress=None,
                    llm_config=llm_config,
                )
            else:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold cyan]{task.description}[/bold cyan]"),
                    BarColumn(bar_width=32),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task("Initializing...", total=100)

                    def on_progress(percent: int, message: str) -> None:
                        progress.update(task, completed=percent, description=message)

                    res = convert(
                        pdf_path=pdf_path,
                        output_dir=args.output,
                        profile=args.profile,
                        on_progress=on_progress,
                        llm_config=llm_config,
                    )

            if not args.quiet:
                table = Table(
                    title=f"Vault Generated: {res.manifest.title}",
                    show_header=True,
                    header_style="bold magenta",
                )
                table.add_column("Metric", style="dim")
                table.add_column("Value", style="bold")
                table.add_row("Vault Directory", str(res.output_dir))
                table.add_row(
                    "Pages",
                    f"{res.pages}"
                    + (
                        f" ({res.validation_report.ocr_pages} OCR'd)"
                        if res.validation_report.ocr_pages
                        else ""
                    ),
                )
                table.add_row("Chapters", str(res.chapters))
                table.add_row("Footnotes / Endnotes", str(res.footnotes))
                table.add_row("Images Extracted", str(res.images))
                if res.llm_review_applied:
                    table.add_row(
                        "AI Review",
                        f"Applied ({res.validation_report.llm_corrections} corrections)",
                    )
                table.add_row(
                    "Processing Time",
                    f"{res.validation_report.processing_time_seconds:.2f}s",
                )
                console.print(table)

            # Surface warnings
            if res.validation_report.warnings and not args.quiet:
                for warning in res.validation_report.warnings:
                    console.print(f"[yellow]⚠ Warning:[/yellow] {warning}")

            # Surface errors from validation
            if res.validation_report.errors:
                for err in res.validation_report.errors:
                    console.print(f"[red]✖ Error:[/red] {err}")
                overall_exit_code = 1

        except MdookError as e:
            console.print(f"[bold red]Error converting '{pdf_path.name}':[/bold red] {e}")
            overall_exit_code = 1
        except Exception as e:
            console.print(
                f"[bold red]Unexpected error converting '{pdf_path.name}':[/bold red] {e}"
            )
            overall_exit_code = 1

    return overall_exit_code


def launch_gui(console: Console | None = None) -> int:
    """Launches the PySide6 desktop GUI."""
    try:
        from PySide6.QtWidgets import QApplication

        from mdook.gui.window import MainWindow

        app = QApplication(sys.argv[:1])
        app.setApplicationName("Mdook")
        window = MainWindow()
        window.show()
        return app.exec()
    except Exception as e:
        c = console or Console(stderr=True)
        c.print(f"[bold red]Could not launch desktop GUI:[/bold red] {e}")
        return 1


def run_cli(argv: list[str] | None = None, console: Console | None = None) -> int:
    """Main CLI dispatch entry point.

    Handles argument pre-processing (e.g. shorthand `mdook book.pdf` -> `mdook convert book.pdf`),
    subcommand execution, and automatic GUI launching when invoked with no arguments on a desktop.
    """
    c = console or Console()
    args_list = list(sys.argv[1:] if argv is None else argv)

    # Shorthand rule: if user runs `mdook book.pdf ...`, auto-prepend `convert`
    if args_list and not args_list[0].startswith("-"):
        first_token = args_list[0]
        if first_token not in ("convert", "gui", "version", "help"):
            candidate = Path(first_token)
            if candidate.suffix.lower() == ".pdf" or candidate.exists():
                args_list.insert(0, "convert")

    # If no arguments provided:
    if not args_list:
        if is_gui_available():
            return launch_gui(c)
        parser = build_parser()
        parser.print_help()
        return 0

    parser = build_parser()
    try:
        parsed_args = parser.parse_args(args_list)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1

    if parsed_args.subcommand == "convert":
        return run_convert(parsed_args, c)
    if parsed_args.subcommand == "gui":
        return launch_gui(c)
    if parsed_args.subcommand == "version":
        c.print(f"Mdook v{__version__}")
        return 0

    # Default fallback
    parser.print_help()
    return 0


def main() -> int:
    """Entry point for console scripts (`mdook = 'mdook.cli:main'`)."""
    sys.exit(run_cli())
