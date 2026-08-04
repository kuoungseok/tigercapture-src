# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the macOS .app bundle.

Layout assumption: run from the repository root, so `main.py` refers
to `mac/main.py` and data paths are relative to the repo root.

Build:
    pyinstaller --noconfirm mac/TigerCapture-mac.spec
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

project_root = Path(SPECPATH).resolve().parent  # = repo root
worker_release = (
    project_root / 'native' / 'tigercapture_worker' / 'target' / 'release' /
    'tigercapture-worker'
)
native_binaries = []
if worker_release.exists():
    native_binaries.append((str(worker_release), 'bundled/native'))
ocio_datas, ocio_binaries, ocio_hiddenimports = collect_all('PyOpenColorIO')

a = Analysis(
    [str(project_root / 'mac' / 'main.py')],
    pathex=[
        str(project_root),
        str(project_root / 'mac'),
    ],
    binaries=native_binaries + ocio_binaries,
    datas=[
        # Shared locales and resources ride along so the overlaid
        # `app` package can find them exactly as on Windows.
        (str(project_root / 'app' / 'locales' / '*.py'), 'app/locales'),
        (str(project_root / 'resources' / 'tigercapture.ico'), 'resources'),
        (str(project_root / 'resources' / 'fonts' / '*.ttf'), 'resources/fonts'),
        (str(project_root / 'resources' / 'fonts' / '*.txt'), 'resources/fonts'),
        (str(project_root / 'resources' / 'fonts' / '*.md'), 'resources/fonts'),
        (str(project_root / 'resources' / 'luts' / '*.cube'), 'resources/luts'),
        (str(project_root / 'resources' / 'ui' / 'sound_editor' / '*.png'), 'resources/ui/sound_editor'),
    ] + copy_metadata('imageio_ffmpeg') + ocio_datas,
    hiddenimports=[
        'app.locales.ko',
        'app.locales.en',
        'app.locales.ja',
        'app.locales.de',
        'app.locales.fr',
        'app.locales.zh',
        'app.color_grading',
        'PyOpenColorIO',
        'app.tier',
        'app.typography',
        'app.typo_animations',
        'app.typo_presets',
        'app.typo_render',
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
    ] + ocio_hiddenimports,
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
    name='TigerCapture',
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
    name='TigerCapture',
)

app = BUNDLE(
    coll,
    name='TigerCapture.app',
    icon=str(project_root / 'mac' / 'resources' / 'tigercapture.icns'),
    bundle_identifier='com.artmouse.tigercapture',
    info_plist=str(project_root / 'mac' / 'Info.plist'),
)
