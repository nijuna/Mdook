"""Mdook Command-Line Interface (CLI).

Provides headless terminal commands for converting publications into
chapter-split Markdown libraries or single documents, scanning directories,
checking versions, and launching the desktop GUI.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable

from rich import box
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
from mdook.cli_wizard import interactive_wizard
from mdook.core.errors import MdookError
from mdook.core.llm import LLMConfig
from mdook.core.pipeline import convert
from mdook.core.scanner import format_file_size, scan_directory


def is_gui_available() -> bool:
    """Returns True if a graphical windowing display environment is detected."""
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def build_parser() -> argparse.ArgumentParser:
    """Constructs the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="mdook",
        description=(
            "Convert books (PDF, EPUB, DOCX) into structured, interlinked "
            "Markdown libraries and reading documents."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  mdook scan
  mdook scan /path/to/books -r
  mdook interactive
  mdook convert book.pdf -o ./output/
  mdook convert novel.epub --single-file
  mdook convert textbook.pdf --profile technical
  mdook convert manuscript.docx --ai --ai-model gemini-2.5-flash
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
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Launch the interactive terminal conversion wizard.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # `convert` subcommand
    convert_parser = subparsers.add_parser(
        "convert",
        help=(
            "Convert books (PDF, EPUB, DOCX) into chapter-split "
            "Markdown libraries or single documents."
        ),
        description=(
            "Ingest publications (PDF, EPUB, DOCX), analyze layout and typography, "
            "and generate clean Markdown libraries or single continuous documents."
        ),
    )
    convert_parser.add_argument(
        "books",
        metavar="BOOK",
        nargs="+",
        type=Path,
        help="Path to one or more input book files or directories containing books.",
    )
    convert_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan any provided directories for supported books.",
    )
    convert_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("./"),
        help="Destination directory where the converted output will be created "
        "(default: current directory).",
    )
    convert_parser.add_argument(
        "-p",
        "--profile",
        choices=["auto", "literature", "technical"],
        default="auto",
        help="Semantic parsing profile: 'auto' (auto-detect), 'literature', or 'technical'.",
    )
    convert_parser.add_argument(
        "-s",
        "--single-file",
        action="store_true",
        help="Output a single continuous Markdown file instead of a chapter-split modular library.",
    )
    convert_parser.add_argument(
        "--ai",
        action="store_true",
        default=None,
        help="Enable token-efficient AI structure review via OpenAI-compatible API.",
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
        help="Model name for AI structure review (e.g. gemini-2.5-flash, gpt-4o-mini, llama3.2).",
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
        help="Suppress progress bars, banners, and non-error output.",
    )

    # `scan` subcommand
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a directory for supported publications (.pdf, .epub, .docx).",
        description=(
            "Discover supported publications in a directory and display their "
            "metadata, format, and file size in a structured table."
        ),
    )
    scan_parser.add_argument(
        "directory",
        nargs="?",
        default=Path("."),
        type=Path,
        help="Directory to scan (defaults to current working directory).",
    )
    scan_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan subdirectories, ignoring cache and hidden folders.",
    )
    scan_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output scanned publication metadata in JSON format.",
    )

    # `interactive` subcommand
    interactive_parser = subparsers.add_parser(
        "interactive",
        help="Launch the interactive terminal conversion wizard.",
        description=(
            "Guided step-by-step terminal wizard for discovering publications, "
            "selecting output structures, setting parsing profiles, and configuring AI review."
        ),
    )
    interactive_parser.add_argument(
        "directory",
        nargs="?",
        default=Path("."),
        type=Path,
        help="Directory to scan for publications (defaults to current working directory).",
    )

    # `gui` subcommand
    subparsers.add_parser(
        "gui",
        help="Launch the desktop graphical user interface.",
        description="Launch the typography-first PySide6 desktop interface.",
    )

    # `version` subcommand
    subparsers.add_parser(
        "version",
        help="Display installed Mdook version.",
    )

    return parser


def print_brand_header(console: Console) -> None:
    """Prints the typographic Mdook brand emblem and metadata banner."""
    brand = (
        f"[bold #f59e0b] ╭───╮   ╭───╮[/]   [bold white]Mdook[/] [dim]v{__version__}[/]\n"
        f"[bold #f59e0b] │ ≡ ╰─┬─╯ ≡ │[/]   [dim]Convert publications into structured Markdown[/]\n"
        f"[bold #f59e0b] ╰─────┴─────╯[/]   "
        "[cyan]PDF[/] [dim]·[/] [cyan]EPUB[/] [dim]·[/] [cyan]DOCX[/]"
    )
    console.print(brand)


def run_convert(args: argparse.Namespace, console: Console) -> int:
    """Executes the headless conversion for specified book files."""
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
    raw_inputs: list[Path] = getattr(args, "books", None) or getattr(args, "pdf", [])
    book_files: list[Path] = []

    for item in raw_inputs:
        if not item.exists():
            console.print(f"[bold red]Error:[/bold red] Path not found: '{item}'")
            overall_exit_code = 1
            continue
        if item.is_file():
            if item.suffix.lower() in (".pdf", ".epub", ".docx"):
                book_files.append(item)
            else:
                console.print(
                    f"[bold yellow]Warning:[/bold yellow] Skipping unsupported file: '{item}'"
                )
        elif item.is_dir():
            recursive = getattr(args, "recursive", False)
            try:
                discovered = scan_directory(item, recursive=recursive)
                if not discovered:
                    console.print(
                        f"[bold yellow]Warning:[/bold yellow] No supported books found in: '{item}'"
                    )
                for book in discovered:
                    book_files.append(book.path)
            except Exception as e:
                console.print(f"[bold red]Error scanning directory '{item}':[/bold red] {e}")
                overall_exit_code = 1
                continue

    if not book_files and raw_inputs:
        console.print("[bold red]Error:[/bold red] No valid book files to process.")
        return 1

    for book_path in book_files:

        if not args.quiet:
            ai_status = (
                f" | AI: [cyan]{llm_config.model}[/cyan]" if llm_config.enabled else ""
            )
            mode_status = "Single Document" if args.single_file else "Modular Library"
            panel_text = (
                f"[bold #f59e0b] ╭───╮   ╭───╮[/]   [bold white]Mdook[/]  [dim]v{__version__}[/]\n"
                f"[bold #f59e0b] │ ≡ ╰─┬─╯ ≡ │[/]   Converting "
                f"[bold white]{book_path.name}[/bold white]\n"
                f"[bold #f59e0b] ╰─────┴─────╯[/]   Profile: [green]{args.profile}[/green] | "
                f"Mode: [green]{mode_status}[/green]{ai_status}"
            )
            console.print(Panel.fit(panel_text, border_style="dim"))

        try:
            if args.quiet:
                res = convert(
                    pdf_path=book_path,
                    output_dir=args.output,
                    profile=args.profile,
                    on_progress=None,
                    llm_config=llm_config,
                    single_file=args.single_file,
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
                        pdf_path=book_path,
                        output_dir=args.output,
                        profile=args.profile,
                        on_progress=on_progress,
                        llm_config=llm_config,
                        single_file=args.single_file,
                    )

            if not args.quiet:
                table_title = (
                    f"Document Generated: {res.manifest.title}"
                    if res.single_file
                    else f"Vault Generated: {res.manifest.title}"
                )
                table = Table(
                    title=table_title,
                    show_header=True,
                    header_style="bold magenta",
                )
                table.add_column("Metric", style="dim")
                table.add_column("Value", style="bold")
                if res.single_file:
                    table.add_row("Output Mode", "Single Document (.md)")
                    table.add_row("Output File", str(res.output_dir / f"{res.manifest.title}.md"))
                else:
                    table.add_row("Output Mode", "Modular Vault")
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
                    console.print(f"[yellow]Warning:[/yellow] {warning}")

            # Surface errors from validation
            if res.validation_report.errors:
                for err in res.validation_report.errors:
                    console.print(f"[red]Error:[/red] {err}")
                overall_exit_code = 1

        except MdookError as e:
            console.print(f"[bold red]Error converting '{book_path.name}':[/bold red] {e}")
            overall_exit_code = 1
        except Exception as e:
            console.print(
                f"[bold red]Unexpected error converting '{book_path.name}':[/bold red] {e}"
            )
            overall_exit_code = 1

    return overall_exit_code


def run_scan(args: argparse.Namespace, console: Console) -> int:
    """Executes directory scanning and renders results as a Rich table or JSON."""
    target_dir: Path = args.directory
    try:
        books = scan_directory(target_dir, recursive=args.recursive)
    except (FileNotFoundError, NotADirectoryError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return 1
    except Exception as e:
        console.print(f"[bold red]Error scanning directory:[/bold red] {e}")
        return 1

    if getattr(args, "json_output", False):
        data = [
            {
                "path": str(b.path),
                "filename": b.filename,
                "format": b.format,
                "size_bytes": b.size_bytes,
                "formatted_size": b.formatted_size,
                "title": b.title,
                "author": b.author,
            }
            for b in books
        ]
        console.print(json.dumps(data, indent=2))
        return 0

    print_brand_header(console)
    console.print()

    resolved_path = target_dir.expanduser().resolve()
    if not books:
        console.print(
            f"[dim]No supported publications (.pdf, .epub, .docx) found in "
            f"[bold]{resolved_path}[/bold].[/dim]"
        )
        return 0

    table = Table(
        title=f"Discovered Publications ({len(books)})",
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="dim",
        show_lines=False,
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Format", justify="center", width=8)
    table.add_column("Filename", style="bold white")
    table.add_column("Size", justify="right", style="dim", width=10)
    table.add_column("Title", style="italic")
    table.add_column("Author", style="dim")

    format_styles = {
        "pdf": "[bold red]PDF[/bold red]",
        "epub": "[bold green]EPUB[/bold green]",
        "docx": "[bold blue]DOCX[/bold blue]",
    }

    total_bytes = 0
    for idx, b in enumerate(books, 1):
        total_bytes += b.size_bytes
        fmt_badge = format_styles.get(b.format.lower(), b.format.upper())
        table.add_row(
            str(idx),
            fmt_badge,
            b.filename,
            b.formatted_size,
            b.title,
            b.author,
        )

    console.print(table)
    console.print(
        f"[dim]Total: [bold]{len(books)}[/bold] publication(s), "
        f"[bold]{format_file_size(total_bytes)}[/bold] in [bold]{resolved_path}[/bold][/dim]"
    )
    return 0


def run_interactive(
    args: argparse.Namespace,
    console: Console,
    input_fn: Callable[[str], str] | None = None,
) -> int:
    """Launches the interactive conversion wizard and executes conversion on confirmation."""
    target_dir = getattr(args, "directory", None) or Path(".")
    cfg = interactive_wizard(console=console, start_dir=target_dir, input_fn=input_fn)
    if cfg is None:
        return 0

    convert_args = argparse.Namespace(
        books=cfg.books,
        output=cfg.output_dir,
        profile=cfg.profile,
        single_file=cfg.single_file,
        ai=cfg.ai_enabled,
        no_ai=not cfg.ai_enabled,
        ai_model=cfg.ai_model,
        ai_base_url=cfg.ai_base_url,
        ai_api_key=cfg.ai_api_key,
        quiet=False,
    )
    return run_convert(convert_args, console=console)


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


def run_cli(
    argv: list[str] | None = None,
    console: Console | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> int:
    """Main CLI dispatch entry point.

    Handles argument pre-processing (e.g. shorthand `mdook book.pdf` -> `mdook convert book.pdf`),
    subcommand execution, interactive wizard launches, and automatic GUI launching when
    invoked with no arguments on a desktop.
    """
    c = console or Console()
    args_list = list(sys.argv[1:] if argv is None else argv)

    # Shorthand rule: if user runs `mdook book.pdf ...`, auto-prepend `convert`
    if args_list and not args_list[0].startswith("-"):
        first_token = args_list[0]
        if first_token not in ("convert", "gui", "version", "help", "scan", "interactive"):
            candidate = Path(first_token)
            if candidate.suffix.lower() in (".pdf", ".epub", ".docx") or candidate.exists():
                args_list.insert(0, "convert")

    # If no arguments provided:
    if not args_list:
        if is_gui_available():
            return launch_gui(c)
        print_brand_header(c)
        c.print()
        try:
            discovered = scan_directory(Path("."), recursive=False)
        except Exception:
            discovered = []
        if discovered and (input_fn is not None or sys.stdin.isatty()):
            c.print(
                f"[bold cyan]Found {len(discovered)} supported publication(s) "
                f"in current directory.[/bold cyan]"
            )
            prompt_str = "Launch interactive conversion wizard? [Y/n]: "
            if input_fn is not None:
                c.print(prompt_str, end="")
                resp = input_fn(prompt_str).strip().lower()
                c.print(resp)
            else:
                resp = c.input(prompt_str).strip().lower()
            if resp in ("y", "yes", ""):
                return run_interactive(
                    argparse.Namespace(directory=Path(".")),
                    c,
                    input_fn=input_fn,
                )
        parser = build_parser()
        c.print(parser.format_help())
        return 0

    parser = build_parser()
    try:
        parsed_args = parser.parse_args(args_list)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1

    if getattr(parsed_args, "interactive", False) or parsed_args.subcommand == "interactive":
        return run_interactive(parsed_args, c, input_fn=input_fn)
    if parsed_args.subcommand == "convert":
        return run_convert(parsed_args, c)
    if parsed_args.subcommand == "scan":
        return run_scan(parsed_args, c)
    if parsed_args.subcommand == "gui":
        return launch_gui(c)
    if parsed_args.subcommand == "version":
        print_brand_header(c)
        return 0

    # Default fallback
    c.print(parser.format_help())
    return 0


def main() -> int:
    """Entry point for console scripts (`mdook = 'mdook.cli:main'`)."""
    sys.exit(run_cli())
