"""Non-blocking update checker querying GitHub Releases API.

Supports 24-hour rate throttling, semver comparison, and release asset discovery.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from mdook import __version__

DEFAULT_REPO = "nijuna/Mdook"
CACHE_EXPIRY_SECONDS = 86400  # 24 hours


@dataclass
class UpdateInfo:
    """Encapsulates release information discovered from GitHub Releases."""

    current_version: str
    latest_version: str
    has_update: bool
    release_notes: str = ""
    release_url: str = ""
    published_at: str = ""
    assets: list[dict[str, Any]] = field(default_factory=list)


def parse_semver(version_str: str) -> tuple[int, ...]:
    """Parses a semantic version string into a tuple of integers for comparison.

    Strips any leading 'v', removes pre-release / build metadata identifiers,
    and extracts integer numeric components. For example:
    'v2.0.1' -> (2, 0, 1)
    '2.1.0-beta.1' -> (2, 1, 0)
    """
    clean = version_str.strip().lstrip("v")
    base_part = clean.split("-")[0].split("+")[0]
    segments = re.findall(r"\d+", base_part)
    if not segments:
        return (0, 0, 0)
    return tuple(int(seg) for seg in segments)


def get_default_cache_path() -> Path:
    """Returns the default path to the update check cache file."""
    cache_dir = Path.home() / ".config" / "mdook"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "update_cache.json"


def read_cached_update(cache_path: Path) -> tuple[float, UpdateInfo | None]:
    """Reads previously cached update check result if valid."""
    if not cache_path.exists():
        return 0.0, None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        timestamp = float(data.get("timestamp", 0.0))
        cached_info = data.get("info")
        if cached_info and isinstance(cached_info, dict):
            info = UpdateInfo(**cached_info)
            return timestamp, info
        return timestamp, None
    except Exception:
        return 0.0, None


def write_cached_update(cache_path: Path, info: UpdateInfo | None) -> None:
    """Persists update check result and timestamp to disk cache."""
    try:
        data = {
            "timestamp": time.time(),
            "info": asdict(info) if info is not None else None,
        }
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def check_for_updates(
    repo: str = DEFAULT_REPO,
    current_version: str = __version__,
    timeout: float = 5.0,
    force: bool = False,
    cache_path: Path | None = None,
) -> UpdateInfo | None:
    """Checks GitHub Releases for available software updates.

    Throttles network requests to once every 24 hours unless force=True.
    Returns UpdateInfo if an update is available or checked, or None on failure.
    """
    resolved_cache = cache_path or get_default_cache_path()

    if not force:
        timestamp, cached = read_cached_update(resolved_cache)
        if (time.time() - timestamp) < CACHE_EXPIRY_SECONDS:
            if cached is not None:
                # Update current_version in cached object in case local version changed
                cached.current_version = current_version
                cached.has_update = parse_semver(cached.latest_version) > parse_semver(
                    current_version
                )
                return cached

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "User-Agent": f"Mdook/{current_version}",
        "Accept": "application/vnd.github.v3+json",
    }
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        # Network, timeout, or rate-limit error: return cached result if available
        _, cached = read_cached_update(resolved_cache)
        return cached

    tag_name = payload.get("tag_name", "").strip()
    latest_version = tag_name.lstrip("v")
    if not latest_version:
        return None

    current_tuple = parse_semver(current_version)
    latest_tuple = parse_semver(latest_version)
    has_update = latest_tuple > current_tuple

    raw_assets = payload.get("assets", [])
    assets = [
        {
            "name": asset.get("name", ""),
            "size": asset.get("size", 0),
            "download_url": asset.get("browser_download_url", ""),
            "content_type": asset.get("content_type", ""),
        }
        for asset in raw_assets
        if isinstance(asset, dict)
    ]

    info = UpdateInfo(
        current_version=current_version,
        latest_version=latest_version,
        has_update=has_update,
        release_notes=payload.get("body", "") or "",
        release_url=payload.get("html_url", "") or "",
        published_at=payload.get("published_at", "") or "",
        assets=assets,
    )

    write_cached_update(resolved_cache, info)
    return info
