# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for Mdook standalone application."""

import sys
from pathlib import Path

block_cipher = None

repo_root = Path('.').resolve()
icon_file = str(repo_root / 'assets' / 'icons' / ('mdook.ico' if sys.platform == 'win32' else 'icon-512.png'))

datas = [
    ('mdook/assets', 'mdook/assets'),
    ('assets/icons', 'assets/icons'),
]

hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'fitz',
    'pymupdf',
    'pdfplumber',
    'pymupdf4llm',
    'pytesseract',
    'PIL',
    'PIL.Image',
    'ebooklib',
    'ebooklib.epub',
    'bs4',
    'docx',
    'rich',
    'rich.console',
    'rich.table',
    'rich.panel',
    'rich.progress',
    'rich.prompt',
    'rich.box',
]

a = Analysis(
    ['mdook/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='mdook',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
