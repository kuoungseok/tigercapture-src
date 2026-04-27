# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

project_root = Path(".").resolve()

# imageio_ffmpeg ships ffmpeg.exe as a wheel; modern imageio.v2.get_writer
# probes the dist's metadata at runtime, so the .dist-info directory has
# to land in the bundle. Without copy_metadata, MP4 export crashes with
# 'No package metadata was found for imageio'.
extra_datas = copy_metadata('imageio_ffmpeg')

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        ('app/locales/*.py', 'app/locales'),
        ('resources/bitdam.ico', 'resources'),
    ] + extra_datas,
    hiddenimports=[
        # Locales are loaded dynamically from a string lookup, so each
        # one needs to be declared here for PyInstaller to bundle it.
        'app.locales.ko',
        'app.locales.en',
        'app.locales.ja',
        'app.locales.de',
        'app.locales.fr',
        'app.locales.zh',
        # New 1.0 modules — most are imported through editor code paths
        # that PyInstaller can analyse, but list them defensively in
        # case any get pulled in via lazy/late imports.
        'app.color_grading',
        'app.tier',
        'app.typography',
        'app.typo_animations',
        'app.typo_presets',
        'app.typo_render',
        'windows_capture',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'test',
        'pydoc',
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
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/bitdam.ico',
    version='version_info.txt',
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
