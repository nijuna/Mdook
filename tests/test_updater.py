"""Tests for the GitHub Releases update checker and notification system."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console

from mdook.cli import run_cli
from mdook.core.updater.checker import (
    UpdateInfo,
    check_for_updates,
    parse_semver,
    read_cached_update,
    write_cached_update,
)
from mdook.gui.worker import UpdateCheckWorker

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_parse_semver() -> None:
    """Verify semantic version parsing across different version formats."""
    assert parse_semver("2.0.1") == (2, 0, 1)
    assert parse_semver("v2.0.2") == (2, 0, 2)
    assert parse_semver("v3.0.0-rc.1") == (3, 0, 0)
    assert parse_semver("1.9.9+build123") == (1, 9, 9)
    assert parse_semver("invalid") == (0, 0, 0)
    assert parse_semver("v2.1.0") > parse_semver("v2.0.1")
    assert parse_semver("2.0.1") == parse_semver("v2.0.1")


def test_write_and_read_cached_update(tmp_path: Path) -> None:
    """Verify writing and reading cached update data to disk."""
    cache_file = tmp_path / "cache.json"
    assert read_cached_update(cache_file) == (0.0, None)

    info = UpdateInfo(
        current_version="2.0.1",
        latest_version="2.1.0",
        has_update=True,
        release_notes="New features",
        release_url="https://github.com/nijuna/Mdook/releases/tag/v2.1.0",
    )
    write_cached_update(cache_file, info)
    timestamp, loaded = read_cached_update(cache_file)

    assert timestamp > 0
    assert loaded is not None
    assert loaded.latest_version == "2.1.0"
    assert loaded.has_update is True
    assert loaded.release_notes == "New features"


def test_check_for_updates_available(tmp_path: Path) -> None:
    """Verify check_for_updates detects available update from mock API response."""
    cache_file = tmp_path / "cache.json"
    mock_payload = {
        "tag_name": "v2.1.0",
        "html_url": "https://github.com/nijuna/Mdook/releases/tag/v2.1.0",
        "published_at": "2026-10-01T12:00:00Z",
        "body": "Major improvements and bugfixes.",
        "assets": [
            {
                "name": "Mdook-Setup-x64.exe",
                "size": 52428800,
                "browser_download_url": "https://github.com/nijuna/Mdook/releases/download/v2.1.0/Mdook-Setup-x64.exe",
                "content_type": "application/x-msdownload",
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        info = check_for_updates(
            current_version="2.0.1",
            cache_path=cache_file,
            force=True,
        )

    assert info is not None
    assert info.current_version == "2.0.1"
    assert info.latest_version == "2.1.0"
    assert info.has_update is True
    assert len(info.assets) == 1
    assert info.assets[0]["name"] == "Mdook-Setup-x64.exe"


def test_check_for_updates_up_to_date(tmp_path: Path) -> None:
    """Verify check_for_updates flags has_update=False when current is latest."""
    cache_file = tmp_path / "cache.json"
    mock_payload = {
        "tag_name": "v2.0.1",
        "html_url": "https://github.com/nijuna/Mdook/releases/tag/v2.0.1",
        "published_at": "2026-09-20T12:00:00Z",
        "body": "Current release.",
        "assets": [],
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        info = check_for_updates(
            current_version="2.0.1",
            cache_path=cache_file,
            force=True,
        )

    assert info is not None
    assert info.has_update is False


def test_check_for_updates_throttling(tmp_path: Path) -> None:
    """Verify subsequent check uses cache and does not make network request within 24h."""
    cache_file = tmp_path / "cache.json"
    cached_info = UpdateInfo(
        current_version="2.0.1",
        latest_version="2.0.5",
        has_update=True,
        release_notes="Cached notes",
    )
    write_cached_update(cache_file, cached_info)

    with patch("urllib.request.urlopen") as mock_url:
        info = check_for_updates(
            current_version="2.0.1",
            cache_path=cache_file,
            force=False,
        )
        mock_url.assert_not_called()
        assert info is not None
        assert info.latest_version == "2.0.5"


def test_check_for_updates_network_failure_fallback(tmp_path: Path) -> None:
    """Verify network exception falls back gracefully to cached update if available."""
    cache_file = tmp_path / "cache.json"
    cached_info = UpdateInfo(
        current_version="2.0.1",
        latest_version="2.0.2",
        has_update=True,
    )
    write_cached_update(cache_file, cached_info)

    with patch("urllib.request.urlopen", side_effect=OSError("Network unreachable")):
        info = check_for_updates(
            current_version="2.0.1",
            cache_path=cache_file,
            force=True,
        )
        assert info is not None
        assert info.latest_version == "2.0.2"


def test_update_check_worker_signals() -> None:
    """Verify UpdateCheckWorker emits appropriate Qt signals."""
    worker = UpdateCheckWorker(force=True)

    found_events: list[UpdateInfo] = []
    worker.update_found.connect(found_events.append)

    test_info = UpdateInfo(
        current_version="2.0.1",
        latest_version="2.1.0",
        has_update=True,
    )

    with patch("mdook.core.updater.checker.check_for_updates", return_value=test_info):
        worker.run()

    assert len(found_events) == 1
    assert found_events[0].latest_version == "2.1.0"


def test_cli_update_command_output() -> None:
    """Verify mdook update --check output via Rich console."""
    test_console = Console(record=True)
    test_info = UpdateInfo(
        current_version="2.0.1",
        latest_version="2.2.0",
        has_update=True,
        release_notes="Super fast conversion pipeline",
        release_url="https://github.com/nijuna/Mdook/releases/tag/v2.2.0",
    )

    with patch("mdook.core.updater.checker.check_for_updates", return_value=test_info):
        exit_code = run_cli(["update", "--check"], console=test_console)

    assert exit_code == 0
    output = test_console.export_text()
    assert "Update Available" in output
    assert "v2.2.0" in output
    assert "Super fast conversion pipeline" in output


def test_cli_update_command_up_to_date() -> None:
    """Verify mdook update output when already on latest version."""
    test_console = Console(record=True)
    test_info = UpdateInfo(
        current_version="2.0.1",
        latest_version="2.0.1",
        has_update=False,
    )

    with patch("mdook.core.updater.checker.check_for_updates", return_value=test_info):
        exit_code = run_cli(["update"], console=test_console)

    assert exit_code == 0
    output = test_console.export_text()
    assert "Mdook is up to date" in output
