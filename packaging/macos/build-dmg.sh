#!/usr/bin/env bash
# build-dmg.sh - Creates Mdook.app bundle and drag-and-drop .dmg disk image for macOS

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

VERSION="${1:-2.0.1}"
APP_NAME="Mdook.app"
APP_DIR="${REPO_ROOT}/dist/${APP_NAME}"
DMG_NAME="Mdook-${VERSION}.dmg"
DMG_PATH="${REPO_ROOT}/dist/${DMG_NAME}"

echo "Building macOS application bundle: ${APP_NAME}"

rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}/Contents/MacOS"
mkdir -p "${APP_DIR}/Contents/Resources"

# 1. Info.plist
cp "${SCRIPT_DIR}/Info.plist" "${APP_DIR}/Contents/Info.plist"

# 2. Executables
if [[ -f "${REPO_ROOT}/dist/Mdook" ]]; then
    cp "${REPO_ROOT}/dist/Mdook" "${APP_DIR}/Contents/MacOS/Mdook"
elif [[ -f "${REPO_ROOT}/dist/mdook" ]]; then
    cp "${REPO_ROOT}/dist/mdook" "${APP_DIR}/Contents/MacOS/Mdook"
fi
chmod +x "${APP_DIR}/Contents/MacOS/Mdook"

if [[ -f "${REPO_ROOT}/dist/mdook-cli" ]]; then
    cp "${REPO_ROOT}/dist/mdook-cli" "${APP_DIR}/Contents/MacOS/mdook-cli"
    chmod +x "${APP_DIR}/Contents/MacOS/mdook-cli"
fi

if [[ -f "${REPO_ROOT}/dist/mdook" ]]; then
    cp "${REPO_ROOT}/dist/mdook" "${APP_DIR}/Contents/MacOS/mdook"
    chmod +x "${APP_DIR}/Contents/MacOS/mdook"
fi

# 3. Resources (Icon)
if [[ -f "${REPO_ROOT}/assets/icons/icon.icns" ]]; then
    cp "${REPO_ROOT}/assets/icons/icon.icns" "${APP_DIR}/Contents/Resources/icon.icns"
elif [[ -f "${REPO_ROOT}/assets/icons/icon-512.png" ]]; then
    cp "${REPO_ROOT}/assets/icons/icon-512.png" "${APP_DIR}/Contents/Resources/icon-512.png"
fi

# 4. Generate DMG if hdiutil is present (macOS), otherwise create zip archive
if command -v hdiutil >/dev/null 2>&1; then
    echo "Creating disk image: ${DMG_PATH}"
    DMG_TMP="${REPO_ROOT}/dist/tmp_dmg"
    rm -rf "${DMG_TMP}" "${DMG_PATH}"
    mkdir -p "${DMG_TMP}"
    cp -r "${APP_DIR}" "${DMG_TMP}/"
    ln -s /Applications "${DMG_TMP}/Applications"
    hdiutil create -volname "Mdook" -srcfolder "${DMG_TMP}" -ov -format UDZO "${DMG_PATH}"
    rm -rf "${DMG_TMP}"
    echo "Disk image built at: ${DMG_PATH}"
else
    echo "hdiutil not found (running on non-macOS host). Creating .zip bundle archive..."
    (cd "${REPO_ROOT}/dist" && zip -r "Mdook-macos-${VERSION}.zip" "${APP_NAME}")
    echo "Bundle archive created at: ${REPO_ROOT}/dist/Mdook-macos-${VERSION}.zip"
fi
