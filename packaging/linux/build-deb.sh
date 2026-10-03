#!/usr/bin/env bash
# build-deb.sh - Builds Debian/Ubuntu .deb package for Mdook

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

VERSION="${1:-2.0.1}"
ARCH="amd64"
PKG_DIR="${REPO_ROOT}/dist/deb-build/mdook_${VERSION}_${ARCH}"

echo "Building Debian package: mdook_${VERSION}_${ARCH}.deb"

rm -rf "${PKG_DIR}"
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/bin"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/512x512/apps"

# 1. DEBIAN/control
cat << EOF > "${PKG_DIR}/DEBIAN/control"
Package: mdook
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: Mdook Contributors <info@mdook.dev>
Description: Convert publications (PDF, EPUB, DOCX) into Markdown libraries and single documents.
 Comprehensive publication parsing suite featuring semantic typography detection,
 PySide6 desktop graphical interface, and headless terminal CLI.
EOF

# 2. Binaries
if [[ -f "${REPO_ROOT}/dist/Mdook" ]]; then
    install -m 755 "${REPO_ROOT}/dist/Mdook" "${PKG_DIR}/usr/bin/Mdook"
elif [[ -f "${REPO_ROOT}/dist/mdook" ]]; then
    install -m 755 "${REPO_ROOT}/dist/mdook" "${PKG_DIR}/usr/bin/Mdook"
fi

if [[ -f "${REPO_ROOT}/dist/mdook-cli" ]]; then
    install -m 755 "${REPO_ROOT}/dist/mdook-cli" "${PKG_DIR}/usr/bin/mdook-cli"
else
    ln -sf "Mdook" "${PKG_DIR}/usr/bin/mdook-cli"
fi

if [[ -f "${REPO_ROOT}/dist/mdook" ]]; then
    install -m 755 "${REPO_ROOT}/dist/mdook" "${PKG_DIR}/usr/bin/mdook"
else
    ln -sf "Mdook" "${PKG_DIR}/usr/bin/mdook"
fi

# 3. Desktop Entry and Icons
install -m 644 "${SCRIPT_DIR}/mdook.desktop" "${PKG_DIR}/usr/share/applications/mdook.desktop"
if [[ -f "${REPO_ROOT}/assets/icons/icon-512.png" ]]; then
    install -m 644 "${REPO_ROOT}/assets/icons/icon-512.png" "${PKG_DIR}/usr/share/icons/hicolor/512x512/apps/mdook.png"
fi

# 4. Build .deb package
mkdir -p "${REPO_ROOT}/dist"
dpkg-deb --build --root-owner-group "${PKG_DIR}" "${REPO_ROOT}/dist/mdook_${VERSION}_${ARCH}.deb"
echo "Package created at: ${REPO_ROOT}/dist/mdook_${VERSION}_${ARCH}.deb"
