#!/usr/bin/env bash
# install-desktop.sh - Installs Mdook desktop entry and brand icons on Linux

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

PREFIX="${HOME}/.local"
if [[ "${1:-}" == "--system" ]]; then
    PREFIX="/usr/local"
    if [[ $EUID -ne 0 ]]; then
        echo "Error: --system install requires root privileges. Please run with sudo." >&2
        exit 1
    fi
fi

BIN_DIR="${PREFIX}/bin"
APPS_DIR="${PREFIX}/share/applications"
ICONS_BASE="${PREFIX}/share/icons/hicolor"

echo "Installing Mdook desktop assets to: ${PREFIX}"

mkdir -p "${BIN_DIR}" "${APPS_DIR}"

# 1. Install binary if present in dist/
if [[ -f "${REPO_ROOT}/dist/mdook" ]]; then
    echo "Installing binary: ${REPO_ROOT}/dist/mdook -> ${BIN_DIR}/mdook"
    install -m 755 "${REPO_ROOT}/dist/mdook" "${BIN_DIR}/mdook"
else
    echo "Notice: dist/mdook binary not found. You can build it with 'pyinstaller mdook.spec'."
fi

# 2. Install desktop entry
echo "Installing desktop entry -> ${APPS_DIR}/mdook.desktop"
install -m 644 "${SCRIPT_DIR}/mdook.desktop" "${APPS_DIR}/mdook.desktop"

# 3. Install multi-resolution icons
declare -A ICON_SIZES=(
    ["16"]="16x16"
    ["32"]="32x32"
    ["48"]="48x48"
    ["64"]="64x64"
    ["128"]="128x128"
    ["256"]="256x256"
    ["512"]="512x512"
)

for SIZE in "${!ICON_SIZES[@]}"; do
    SRC_ICON="${REPO_ROOT}/assets/icons/icon-${SIZE}.png"
    DEST_DIR="${ICONS_BASE}/${ICON_SIZES[$SIZE]}/apps"
    if [[ -f "${SRC_ICON}" ]]; then
        mkdir -p "${DEST_DIR}"
        install -m 644 "${SRC_ICON}" "${DEST_DIR}/mdook.png"
    fi
done

# 4. Update desktop and icon caches if utilities exist
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APPS_DIR}" || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${ICONS_BASE}" || true
fi

echo "Mdook desktop integration installed successfully."
