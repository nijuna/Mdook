"""Tests for the verified in-place update installer."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from mdook.cli import run_cli
from mdook.core.updater.checker import UpdateInfo
from mdook.core.updater.installer import (
    compute_sha256,
    download_file,
    find_platform_asset,
    install_update,
    parse_checksum_manifest,
)
from mdook.gui.worker import InstallWorker

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_compute_sha256(tmp_path: Path) -> None:
    """Verify SHA-256 calculation matches expected hash."""
    test_file = tmp_path / "sample.bin"
    content = b"Mdook test binary content for hashing"
    test_file.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest().lower()
    actual = compute_sha256(test_file)
    assert actual == expected


def test_parse_checksum_manifest() -> None:
    """Verify parsing standard SHA256SUMS.txt format."""
    manifest = """
# SHA256 Checksums
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  empty.file
ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad *Mdook-Setup-x64.exe
cb8379ac2098aa165029e3938a51da0bcecfc008fd6795f401178647f96c5b34  mdook_2.1.0_amd64.deb
"""
    parsed = parse_checksum_manifest(manifest)
    empty_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    exe_hash = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    deb_hash = "cb8379ac2098aa165029e3938a51da0bcecfc008fd6795f401178647f96c5b34"
    assert parsed["empty.file"] == empty_hash
    assert parsed["Mdook-Setup-x64.exe"] == exe_hash
    assert parsed["mdook_2.1.0_amd64.deb"] == deb_hash



def test_find_platform_asset() -> None:
    """Verify platform asset selection for Windows, macOS, and Linux."""
    assets = [
        {"name": "Mdook-Setup-x64.exe", "download_url": "https://example.com/win"},
        {"name": "Mdook-2.1.0.dmg", "download_url": "https://example.com/mac"},
        {"name": "mdook_2.1.0_amd64.deb", "download_url": "https://example.com/deb"},
        {"name": "mdook-linux-x86_64.tar.gz", "download_url": "https://example.com/linux"},
        {"name": "SHA256SUMS.txt", "download_url": "https://example.com/sums"},
    ]

    win_asset = find_platform_asset(assets, target_platform="win32")
    assert win_asset is not None
    assert win_asset["name"] == "Mdook-Setup-x64.exe"

    mac_asset = find_platform_asset(assets, target_platform="darwin")
    assert mac_asset is not None
    assert mac_asset["name"] == "Mdook-2.1.0.dmg"

    linux_asset = find_platform_asset(assets, target_platform="linux")
    assert linux_asset is not None
    assert linux_asset["name"] == "mdook_2.1.0_amd64.deb"


def test_download_file(tmp_path: Path) -> None:
    """Verify streaming file download with progress tracking."""
    dest = tmp_path / "downloaded.bin"
    payload = b"Sample streamed download content"

    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Length": str(len(payload))}
    mock_resp.read.side_effect = [payload, b""]
    mock_resp.__enter__.return_value = mock_resp

    progress_calls = []

    def on_prog(downloaded: int, total: int) -> None:
        progress_calls.append((downloaded, total))

    with patch("urllib.request.urlopen", return_value=mock_resp):
        download_file("https://example.com/test", dest, on_progress=on_prog)

    assert dest.exists()
    assert dest.read_bytes() == payload
    assert len(progress_calls) > 0
    assert progress_calls[-1] == (len(payload), len(payload))


def test_install_update_checksum_mismatch(tmp_path: Path) -> None:
    """Verify corrupted / tampered download is rejected when checksum does not match."""
    payload = b"Tampered content"
    wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    info = UpdateInfo(
        current_version="2.0.1",
        latest_version="2.1.0",
        has_update=True,
        assets=[
            {
                "name": "mdook-linux-x86_64.tar.gz",
                "download_url": "https://example.com/bin",
            },
            {
                "name": "SHA256SUMS.txt",
                "download_url": "https://example.com/sums",
            },
        ],
    )

    manifest_content = f"{wrong_hash}  mdook-linux-x86_64.tar.gz\n"

    def mock_urlopen(req, timeout=10.0):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        resp = MagicMock()
        if "sums" in url:
            resp.read.return_value = manifest_content.encode("utf-8")
        else:
            resp.headers = {"Content-Length": str(len(payload))}
            resp.read.side_effect = [payload, b""]
        resp.__enter__.return_value = resp
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        success, msg = install_update(info, target_platform="linux")

    assert success is False
    assert "Checksum validation failed" in msg


def test_install_update_success(tmp_path: Path) -> None:
    """Verify successful download, verification, and apply lifecycle."""
    payload = b"Valid update binary content"
    valid_hash = hashlib.sha256(payload).hexdigest().lower()

    info = UpdateInfo(
        current_version="2.0.1",
        latest_version="2.1.0",
        has_update=True,
        assets=[
            {
                "name": "mdook-linux-x86_64.tar.gz",
                "download_url": "https://example.com/bin",
            },
            {
                "name": "SHA256SUMS.txt",
                "download_url": "https://example.com/sums",
            },
        ],
    )

    manifest_content = f"{valid_hash}  mdook-linux-x86_64.tar.gz\n"

    def mock_urlopen(req, timeout=10.0):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        resp = MagicMock()
        if "sums" in url:
            resp.read.return_value = manifest_content.encode("utf-8")
        else:
            resp.headers = {"Content-Length": str(len(payload))}
            resp.read.side_effect = [payload, b""]
        resp.__enter__.return_value = resp
        return resp

    statuses = []

    def on_status(msg: str, pct: int) -> None:
        statuses.append((msg, pct))

    with (
        patch("urllib.request.urlopen", side_effect=mock_urlopen),
        patch("mdook.core.updater.installer.apply_update", return_value=(True, "Applied")),
    ):
        success, msg = install_update(info, on_status=on_status, target_platform="linux")

    assert success is True
    assert msg == "Applied"
    assert len(statuses) > 0


def test_cli_update_install_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI interactive prompt approves and executes installation."""
    test_console = Console(record=True)
    info = UpdateInfo(
        current_version="2.0.1",
        latest_version="2.1.0",
        has_update=True,
        assets=[{"name": "mdook_2.1.0_amd64.deb", "download_url": "https://example.com/deb"}],
    )

    with (
        patch("mdook.core.updater.checker.check_for_updates", return_value=info),
        patch(
            "mdook.core.updater.installer.install_update",
            return_value=(True, "Installed package successfully"),
        ) as mock_install,
    ):
        exit_code = run_cli(
            ["update"],
            console=test_console,
            input_fn=lambda _: "y",
        )

    assert exit_code == 0
    mock_install.assert_called_once()
    out = test_console.export_text()
    assert "Update complete" in out


def test_cli_update_install_declined() -> None:
    """Verify declining the CLI interactive update prompt aborts cleanly."""
    test_console = Console(record=True)
    info = UpdateInfo(
        current_version="2.0.1",
        latest_version="2.1.0",
        has_update=True,
        assets=[{"name": "mdook_2.1.0_amd64.deb", "download_url": "https://example.com/deb"}],
    )

    with (
        patch("mdook.core.updater.checker.check_for_updates", return_value=info),
        patch("mdook.core.updater.installer.install_update") as mock_install,
    ):
        exit_code = run_cli(
            ["update"],
            console=test_console,
            input_fn=lambda _: "n",
        )

    assert exit_code == 0
    mock_install.assert_not_called()
    out = test_console.export_text()
    assert "Update cancelled" not in out or "cancelled" in out.lower()


def test_install_worker_signals() -> None:
    """Verify InstallWorker emits progress and finished signals."""
    info = UpdateInfo(current_version="2.0.1", latest_version="2.1.0", has_update=True)
    worker = InstallWorker(info)

    status_events = []
    finished_events = []

    worker.status_updated.connect(lambda msg, pct: status_events.append((msg, pct)))
    worker.install_finished.connect(lambda ok, msg: finished_events.append((ok, msg)))

    with patch(
        "mdook.core.updater.installer.install_update",
        side_effect=lambda inf, on_status=None, **kw: (
            on_status("Extracting", 50) if on_status else None,
            (True, "Done"),
        )[1],
    ):
        worker.run()

    assert len(status_events) == 1
    assert status_events[0] == ("Extracting", 50)
    assert len(finished_events) == 1
    assert finished_events[0] == (True, "Done")
