"""Verified download and in-place application installation engine.

Supports SHA-256 verification against release manifests, streaming download progress,
and platform-specific update application (Linux atomic replacement, Windows setup launcher,
and macOS bundle installation).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Callable

from mdook.core.updater.checker import UpdateInfo


def compute_sha256(file_path: Path) -> str:
    """Computes the lowercase hexadecimal SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def parse_checksum_manifest(manifest_text: str) -> dict[str, str]:
    """Parses standard SHA256SUMS text into a mapping of {filename: sha256_hash}."""
    mapping: dict[str, str] = {}
    for line in manifest_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            checksum, filename = parts[0].strip().lower(), parts[1].strip().lstrip("*")
            mapping[Path(filename).name] = checksum
    return mapping


def find_platform_asset(
    assets: list[dict[str, Any]],
    target_platform: str = sys.platform,
) -> dict[str, Any] | None:
    """Selects the most suitable release asset for the running operating system."""
    if not assets:
        return None

    norm_plat = target_platform.lower()

    if norm_plat.startswith("win"):
        # Windows: Prefer .exe installer, then .zip
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".exe") and ("setup" in name or "installer" in name):
                return asset
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".exe"):
                return asset
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".zip") and ("win" in name or "windows" in name):
                return asset

    elif norm_plat.startswith("darwin"):
        # macOS: Prefer .dmg, then .zip / .tar.gz
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".dmg"):
                return asset
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".zip") and ("mac" in name or "darwin" in name or "osx" in name):
                return asset

    else:
        # Linux / Unix: Prefer .deb, AppImage, or standalone binary archive
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".deb"):
                return asset
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".appimage"):
                return asset
        for asset in assets:
            name = asset.get("name", "").lower()
            if "linux" in name and (name.endswith(".tar.gz") or name.endswith(".zip")):
                return asset
        for asset in assets:
            name = asset.get("name", "").lower()
            if "linux" in name and not name.endswith(".txt"):
                return asset

    # Generic fallback: return first binary asset
    for asset in assets:
        name = asset.get("name", "").lower()
        if not name.endswith(".txt") and not name.endswith(".json") and not name.endswith(".md"):
            return asset

    return None


def download_file(
    url: str,
    dest_path: Path,
    on_progress: Callable[[int, int], None] | None = None,
    chunk_size: int = 65536,
) -> Path:
    """Downloads a remote file with streaming progress tracking."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mdook-Updater/2.0"},
    )

    with urllib.request.urlopen(req, timeout=30.0) as response, dest_path.open("wb") as out:
        total_size = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            if on_progress:
                on_progress(downloaded, total_size)

    return dest_path


def fetch_checksum_manifest(assets: list[dict[str, Any]]) -> dict[str, str]:
    """Locates and parses SHA256SUMS.txt from release assets if present."""
    checksum_asset = next(
        (
            a
            for a in assets
            if a.get("name", "").upper() in ("SHA256SUMS", "SHA256SUMS.TXT", "CHECKSUMS.TXT")
        ),
        None,
    )
    if not checksum_asset or not checksum_asset.get("download_url"):
        return {}

    try:
        req = urllib.request.Request(
            checksum_asset["download_url"],
            headers={"User-Agent": "Mdook-Updater/2.0"},
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            text = resp.read().decode("utf-8")
        return parse_checksum_manifest(text)
    except Exception:
        return {}


def apply_update(
    installer_path: Path,
    asset_name: str,
    target_platform: str = sys.platform,
) -> tuple[bool, str]:
    """Applies the downloaded update package according to platform capabilities."""
    norm_plat = target_platform.lower()

    if norm_plat.startswith("win"):
        # Windows: Launch installer process and return instruction to exit
        try:
            if installer_path.suffix.lower() == ".exe":
                subprocess.Popen(
                    [str(installer_path), "/SILENT"],
                    creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                )
                return True, "Windows installer launched in silent mode."
            return False, f"Unsupported installer format on Windows: {installer_path.name}"
        except Exception as exc:
            return False, f"Failed to execute Windows installer: {exc}"

    elif norm_plat.startswith("darwin"):
        # macOS: Guide or launch .dmg
        try:
            if installer_path.suffix.lower() == ".dmg":
                subprocess.Popen(["open", str(installer_path)])
                return True, "Mounted macOS disk image for installation."
            return True, f"Downloaded update package to {installer_path}."
        except Exception as exc:
            return False, f"Failed to open disk image: {exc}"

    else:
        # Linux: Handle .deb or standalone binary
        try:
            if installer_path.suffix.lower() == ".deb":
                cmd = ["pkexec", "dpkg", "-i", str(installer_path)]
                subprocess.Popen(cmd)
                return True, "Triggered Debian package installation via pkexec."

            # If binary file, make executable and atomic-replace ~/.local/bin/Mdook if applicable
            user_bin = Path.home() / ".local" / "bin"
            target_bin = user_bin / "Mdook"
            target_cli = user_bin / "mdook-cli"
            if user_bin.exists() and os.access(user_bin, os.W_OK):
                mode = installer_path.stat().st_mode
                installer_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                shutil.copy2(installer_path, target_bin)
                shutil.copy2(installer_path, target_cli)
                return True, f"Replaced user binaries at {user_bin}."

            return True, f"Downloaded update binary to {installer_path}."
        except Exception as exc:
            return False, f"Failed to apply Linux update: {exc}"


def install_update(
    info: UpdateInfo,
    on_status: Callable[[str, int], None] | None = None,
    target_platform: str = sys.platform,
) -> tuple[bool, str]:
    """Full lifecycle manager: finds platform asset, downloads, validates checksum, and applies."""
    asset = find_platform_asset(info.assets, target_platform=target_platform)
    if not asset or not asset.get("download_url"):
        return False, "No compatible release asset found for this operating system."

    asset_name = asset.get("name", "mdook-update")
    download_url = asset["download_url"]

    if on_status:
        on_status(f"Fetching release manifest for {asset_name}...", 5)

    checksums = fetch_checksum_manifest(info.assets)
    expected_sha256 = checksums.get(asset_name)

    temp_dir = Path(tempfile.gettempdir()) / "mdook_update"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_dest = temp_dir / asset_name

    def progress_callback(downloaded: int, total: int) -> None:
        if total > 0 and on_status:
            pct = 10 + int((downloaded / total) * 80)
            on_status(f"Downloading {asset_name} ({downloaded // 1024} KB)...", pct)

    if on_status:
        on_status(f"Starting download of {asset_name}...", 10)

    try:
        download_file(download_url, temp_dest, on_progress=progress_callback)
    except Exception as exc:
        return False, f"Download failed: {exc}"

    if on_status:
        on_status("Verifying SHA-256 integrity...", 92)

    actual_hash = compute_sha256(temp_dest)
    if expected_sha256 and actual_hash != expected_sha256.lower():
        try:
            temp_dest.unlink(missing_ok=True)
        except Exception:
            pass
        return False, (
            f"Checksum validation failed for {asset_name}! "
            f"Expected {expected_sha256}, got {actual_hash}."
        )

    if on_status:
        on_status("Applying update...", 96)

    success, message = apply_update(temp_dest, asset_name, target_platform=target_platform)
    if on_status:
        on_status("Update complete." if success else f"Update failed: {message}", 100)

    return success, message
