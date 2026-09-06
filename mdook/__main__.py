"""Entry point for `python -m mdook` and the `mdook` console command."""

from __future__ import annotations

import sys

from mdook.cli import run_cli


def main() -> None:
    sys.exit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()
