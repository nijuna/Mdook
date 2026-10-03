"""Entry point for `python -m mdook` and console commands."""

from __future__ import annotations

import sys
from pathlib import Path

from mdook.cli import run_cli


def main() -> None:
    prog = Path(sys.argv[0]).stem if sys.argv and sys.argv[0] else ""
    if prog.lower() == "mdook-cli":
        sys.exit(run_cli(sys.argv[1:], allow_gui=False))
    elif prog == "Mdook":
        from mdook.gui.window import launch_gui_entry

        sys.exit(launch_gui_entry(sys.argv[:1]))
    else:
        sys.exit(run_cli(sys.argv[1:], allow_gui=True))


if __name__ == "__main__":
    main()

