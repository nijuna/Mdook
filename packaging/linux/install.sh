#!/usr/bin/env bash
# install.sh - 1-Line Native Linux Installer for Mdook
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/nijuna/Mdook/main/packaging/linux/install.sh | bash
#
# Installs desktop launcher, user binaries, and environment pathing in under 60 seconds.

set -euo pipefail

BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/512x512/apps"

mkdir -p "${BIN_DIR}" "${APP_DIR}" "${ICON_DIR}"

echo "=========================================================="
echo " Mdook Linux 1-Click Installer"
echo "=========================================================="

# 1. Installation Method Discovery
INSTALLED=false

# Method A: Local repo checkout
if [[ -f "./pyproject.toml" && -f "./mdook/__main__.py" ]]; then
    echo "Found local Mdook repository clone. Installing in editable/user mode..."
    if command -v uv >/dev/null 2>&1; then
        uv tool install --force . || pip install --user .
    elif command -v pipx >/dev/null 2>&1; then
        pipx install --force .
    else
        python3 -m pip install --user .
    fi
    INSTALLED=true
fi

# Method B: Standalone binary download from GitHub Releases
if [[ "${INSTALLED}" == "false" ]]; then
    echo "Fetching latest release binary from GitHub..."
    LATEST_JSON=$(curl -sSL "https://api.github.com/repos/nijuna/Mdook/releases/latest" 2>/dev/null || true)
    DOWNLOAD_URL=$(echo "${LATEST_JSON}" | grep -o 'https://[^"]*mdook-linux-x86_64[^"]*' | head -n 1 || true)

    if [[ -n "${DOWNLOAD_URL}" ]]; then
        echo "Downloading Mdook binary: ${DOWNLOAD_URL}"
        TMP_BIN=$(mktemp)
        curl -sSL "${DOWNLOAD_URL}" -o "${TMP_BIN}"
        chmod +x "${TMP_BIN}"
        mv "${TMP_BIN}" "${BIN_DIR}/mdook"
        ln -sf "${BIN_DIR}/mdook" "${BIN_DIR}/Mdook"
        ln -sf "${BIN_DIR}/mdook" "${BIN_DIR}/mdook-cli"
        INSTALLED=true
    fi
fi

# Method C: pipx / uv tool install fallback
if [[ "${INSTALLED}" == "false" ]]; then
    echo "Installing via Python package manager..."
    if command -v uv >/dev/null 2>&1; then
        uv tool install mdook || true
    elif command -v pipx >/dev/null 2>&1; then
        pipx install mdook || true
    else
        python3 -m pip install --user mdook || true
    fi
    INSTALLED=true
fi

# 2. Desktop Launcher & Icon Setup
echo "Configuring desktop integration and launcher..."
ICON_URL="https://raw.githubusercontent.com/nijuna/Mdook/main/assets/icons/icon-512.png"
if [[ -f "./assets/icons/icon-512.png" ]]; then
    cp "./assets/icons/icon-512.png" "${ICON_DIR}/mdook.png"
else
    curl -sSL "${ICON_URL}" -o "${ICON_DIR}/mdook.png" 2>/dev/null || true
fi

cat << 'EOF' > "${APP_DIR}/mdook.desktop"
[Desktop Entry]
Type=Application
Name=Mdook
GenericName=Book to Markdown Converter
Comment=Convert PDF, EPUB, and DOCX publications into structured Markdown libraries and single documents
Exec=Mdook %F
Icon=mdook
Terminal=false
Categories=Office;Publishing;Utility;
MimeType=application/pdf;application/epub+zip;application/vnd.openxmlformats-officedocument.wordprocessingml.document;
StartupNotify=true
EOF

chmod 644 "${APP_DIR}/mdook.desktop"

# 3. Update system desktop database if utility is available
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
fi

# 4. Ensure ~/.local/bin is in PATH
SHELL_RC=""
if [[ -n "${ZSH_VERSION:-}" || "${SHELL:-}" == *"zsh"* ]]; then
    SHELL_RC="${HOME}/.zshrc"
elif [[ -f "${HOME}/.bashrc" ]]; then
    SHELL_RC="${HOME}/.bashrc"
fi

if [[ -n "${SHELL_RC}" && -f "${SHELL_RC}" ]]; then
    if ! grep -q 'PATH.*\.local/bin' "${SHELL_RC}"; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "${SHELL_RC}"
    fi
fi

echo ""
echo "=========================================================="
echo " Mdook Installation Complete!"
echo "=========================================================="
echo "You can now run:"
echo "  Mdook       -> Launches the desktop graphical user interface"
echo "  mdook-cli   -> Runs headless terminal commands and conversions"
echo "  mdook       -> Universal command (auto-detects environment)"
echo ""
echo "Desktop launcher installed. You can also launch Mdook from"
echo "your applications menu."
echo "=========================================================="
