# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the macOS .app bundle.

Layout assumption: run from the repository root, so `main.py` refers
to `mac/main.py` and data paths are relative to the repo root.

Build:
    pyinstaller --noconfirm mac/Bitdam-mac.spec
"""
from pathlib import Path

project_root = Path(SPECPATH).resolve().parent  # = repo root

a = Analysis(
    [str(project_root / 'mac' / 'main.py')],
    pathex=[
        str(project_root),
        str(project_root / 'mac'),
    ],
    binaries=[],
    datas=[
        # Shared locales and resources ride along so the overlaid
        # `app` package can find them exactly as on Windows.
        (str(project_root / 'app' / 'locales' / '*.py'), 'app/locales'),
        (str(project_root / 'resources' / 'bitdam.ico'), 'resources'),
    ],
    hiddenimports=[
        'app.locales.ko',
        'app.locales.en',
        'app.locales.ja',
        'app.locales.de',
        # ScreenCaptureKit + supporting frameworks. PyInstaller can't
        # statically discover pyobjc's dynamic bundle-loading, so each
        # framework module referenced at runtime must be listed here
        # or the frozen app fails with ModuleNotFoundError.
        'objc',
        'Foundation',
        'AppKit',
        'Quartz',                  # also covers CoreVideo, CoreGraphics,
                                   # CoreImage — they're subframeworks of
                                   # pyobjc-framework-Quartz, not separate.
        'CoreMedia',
        'ApplicationServices',     # AX* accessibility API
        'ScreenCaptureKit',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'test',
        'pydoc',
        'windows_capture',   # Windows-only; must never enter a Mac build
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Bitdam',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,   # inherit current arch; build per host (arm64 / x86_64)
    codesign_identity=None,
    entitlements_file=str(project_root / 'mac' / 'entitlements.plist'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Bitdam',
)

app = BUNDLE(
    coll,
    name='Bitdam.app',
    icon=str(project_root / 'mac' / 'resources' / 'bitdam.icns'),
    bundle_identifier='com.artmouse.bitdam',
    info_plist=str(project_root / 'mac' / 'Info.plist'),
)
