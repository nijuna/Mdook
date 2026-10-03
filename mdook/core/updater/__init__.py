"""Update checker and packaging subsystem for Mdook."""

from __future__ import annotations

from mdook.core.updater.checker import UpdateInfo, check_for_updates, parse_semver
from mdook.core.updater.installer import (
    compute_sha256,
    download_file,
    find_platform_asset,
    install_update,
)

__all__ = [
    "UpdateInfo",
    "check_for_updates",
    "compute_sha256",
    "download_file",
    "find_platform_asset",
    "install_update",
    "parse_semver",
]

