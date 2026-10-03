"""Tests verifying cross-platform packaging configurations and installer manifests."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def test_windows_inno_setup_manifest() -> None:
    """Verify Inno Setup script structure, sections, and binary targets."""
    repo_root = Path(__file__).resolve().parent.parent
    iss_file = repo_root / "packaging" / "windows" / "mdook-setup.iss"

    assert iss_file.exists(), "packaging/windows/mdook-setup.iss missing"
    content = iss_file.read_text(encoding="utf-8")

    assert "[Setup]" in content
    assert "[Files]" in content
    assert "[Icons]" in content
    assert "[Tasks]" in content
    assert "[Registry]" in content
    assert 'MyAppName "Mdook"' in content
    assert "Mdook.exe" in content
    assert "mdook-cli.exe" in content
    assert "addtopath" in content


def test_linux_installer_scripts() -> None:
    """Verify Linux 1-click install script and desktop integration."""
    repo_root = Path(__file__).resolve().parent.parent
    install_sh = repo_root / "packaging" / "linux" / "install.sh"
    desktop_file = repo_root / "packaging" / "linux" / "mdook.desktop"
    build_deb = repo_root / "packaging" / "linux" / "build-deb.sh"

    assert install_sh.exists(), "packaging/linux/install.sh missing"
    assert desktop_file.exists(), "packaging/linux/mdook.desktop missing"
    assert build_deb.exists(), "packaging/linux/build-deb.sh missing"

    install_content = install_sh.read_text(encoding="utf-8")
    assert "set -euo pipefail" in install_content
    assert "mdook.desktop" in install_content
    assert "Mdook" in install_content
    assert "mdook-cli" in install_content

    desktop_content = desktop_file.read_text(encoding="utf-8")
    assert "[Desktop Entry]" in desktop_content
    assert "Type=Application" in desktop_content
    assert "Name=Mdook" in desktop_content
    assert "Icon=mdook" in desktop_content

    deb_content = build_deb.read_text(encoding="utf-8")
    assert "dpkg-deb --build" in deb_content


def test_macos_bundle_and_dmg_configuration() -> None:
    """Verify macOS Info.plist and build-dmg.sh bundle scripts."""
    repo_root = Path(__file__).resolve().parent.parent
    info_plist = repo_root / "packaging" / "macos" / "Info.plist"
    build_dmg = repo_root / "packaging" / "macos" / "build-dmg.sh"

    assert info_plist.exists(), "packaging/macos/Info.plist missing"
    assert build_dmg.exists(), "packaging/macos/build-dmg.sh missing"

    # Validate plist XML structure
    tree = ET.parse(info_plist)
    root = tree.getroot()
    assert root.tag == "plist"

    plist_text = info_plist.read_text(encoding="utf-8")
    assert "CFBundleName" in plist_text
    assert "Mdook" in plist_text
    assert "CFBundleExecutable" in plist_text
    assert "dev.mdook.app" in plist_text

    dmg_text = build_dmg.read_text(encoding="utf-8")
    assert "Mdook.app" in dmg_text
    assert "Contents/MacOS" in dmg_text
