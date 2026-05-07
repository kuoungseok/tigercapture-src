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
        ('resources/tigercapture.ico', 'resources'),
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
        # Core modules
        'app.color_grading',
        'app.tier',
        'app.typography',
        'app.typo_animations',
        'app.typo_presets',
        'app.typo_render',
        'windows_capture',
        # v1.3+ new modules
        'app.audio_mixer_panel',
        'app.batch_export_dialog',
        'app.clip_effects_dialog',
        'app.color_page_window',
        'app.new_project_dialog',
        'app.video_filters',
        'app.chroma_key',
        'app.video_stabilizer',
        'app.background_removal',
        'app.video_decoder',
        'app.project_io',
        'app.timeline_ruler',
        'app.opengl_preview',
        'app.workbench_panel',
        'app.media_pool',
        'app.knob_widget',
        'app.jog_shuttle',
        'app.subtitles',
        'app.pg_scopes',
        'app.color_scopes',
        'app.hue_curve_widget',
        # Node graph
        'app.workbench.node_graph',
        'app.workbench.node_graph.scene',
        'app.workbench.node_graph.view',
        'app.workbench.node_graph.widget',
        'app.workbench.node_graph.items.node_item',
        'app.workbench.node_graph.items.blur_node_item',
        'app.workbench.node_graph.items.connection_item',
        'app.workbench.node_graph.items.port_item',
        'app.workbench.node_graph.items.io_node',
        'app.workbench.node_graph.items.parallel_mixer',
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
    name='TigerCapture',
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
    icon='resources/tigercapture.ico',
    version='version_info.txt',
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
