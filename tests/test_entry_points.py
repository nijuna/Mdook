"""Tests for Mdook and mdook-cli command separation and entry points."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from mdook.__main__ import main as dunder_main
from mdook.cli import run_cli, run_cli_entry


def test_pyproject_scripts_entry_points() -> None:
    """Verify that pyproject.toml registers Mdook, mdook-cli, and mdook console scripts."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject_path.exists()
    content = pyproject_path.read_text(encoding="utf-8")
    assert 'Mdook = "mdook.gui.window:launch_gui_entry"' in content
    assert 'mdook-cli = "mdook.cli:run_cli_entry"' in content
    assert 'mdook = "mdook.__main__:main"' in content


def test_run_cli_entry_never_launches_gui(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify mdook-cli entry point runs headlessly and never invokes GUI when args are empty."""
    monkeypatch.setattr(sys, "argv", ["mdook-cli"])
    mock_launch_gui = MagicMock()
    monkeypatch.setattr("mdook.cli.launch_gui", mock_launch_gui)
    monkeypatch.setattr("mdook.cli.is_gui_available", lambda: True)

    test_console = Console(record=True)
    code = run_cli([], console=test_console, allow_gui=False)

    assert code == 0
    mock_launch_gui.assert_not_called()
    output = test_console.export_text()
    assert "Mdook" in output


def test_run_cli_entry_function_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run_cli_entry delegates to run_cli with allow_gui=False."""
    monkeypatch.setattr(sys, "argv", ["mdook-cli", "--help"])
    with patch("mdook.cli.run_cli", return_value=0) as mock_run:
        exit_code = run_cli_entry()
        assert exit_code == 0
        mock_run.assert_called_once_with(["--help"], allow_gui=False)


def test_launch_gui_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify launch_gui_entry initializes QApplication, MainWindow, and executes app."""
    from mdook.gui.window import launch_gui_entry

    mock_app = MagicMock()
    mock_app.exec.return_value = 0
    mock_window = MagicMock()

    with (
        patch("mdook.gui.window.QApplication", return_value=mock_app) as mock_qapp_cls,
        patch("mdook.gui.window.MainWindow", return_value=mock_window),
        patch("mdook.gui.window.QIcon"),
    ):
        mock_qapp_cls.instance.return_value = None
        code = launch_gui_entry(["Mdook"])
        assert code == 0
        mock_app.setApplicationName.assert_called_with("Mdook")
        mock_window.show.assert_called_once()
        mock_app.exec.assert_called_once()



def test_main_dispatch_mdook_gui(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify __main__.main launches GUI when invoked as Mdook."""
    monkeypatch.setattr(sys, "argv", ["/usr/local/bin/Mdook"])
    with patch("mdook.gui.window.launch_gui_entry", return_value=0) as mock_gui:
        with pytest.raises(SystemExit) as exc:
            dunder_main()
        assert exc.value.code == 0
        mock_gui.assert_called_once()


def test_main_dispatch_mdook_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify __main__.main dispatches headlessly when invoked as mdook-cli."""
    monkeypatch.setattr(sys, "argv", ["/usr/local/bin/mdook-cli", "scan"])
    with patch("mdook.__main__.run_cli", return_value=0) as mock_run_cli:
        with pytest.raises(SystemExit) as exc:
            dunder_main()
        assert exc.value.code == 0
        mock_run_cli.assert_called_once_with(["scan"], allow_gui=False)


def test_main_dispatch_universal_mdook(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify __main__.main uses universal behavior with allow_gui=True for mdook."""
    monkeypatch.setattr(sys, "argv", ["/usr/local/bin/mdook", "scan"])
    with patch("mdook.__main__.run_cli", return_value=0) as mock_run_cli:
        with pytest.raises(SystemExit) as exc:
            dunder_main()
        assert exc.value.code == 0
        mock_run_cli.assert_called_once_with(["scan"], allow_gui=True)

