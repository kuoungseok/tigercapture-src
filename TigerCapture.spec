# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

project_root = Path(".").resolve()
worker_exe_name = "tigercapture-worker.exe"
worker_release = (
    project_root / "native" / "tigercapture_worker" / "target" / "release" /
    worker_exe_name
)
native_binaries = []
if worker_release.exists():
    native_binaries.append((str(worker_release), "bundled/native"))

# imageio_ffmpeg ships ffmpeg.exe as a wheel; modern imageio.v2.get_writer
# probes the dist's metadata at runtime, so the .dist-info directory has
# to land in the bundle. Without copy_metadata, MP4 export crashes with
# 'No package metadata was found for imageio'.
extra_datas = copy_metadata('imageio_ffmpeg')

a = Analysis(
    ['main.py', 'studio_main.py'],
    pathex=[str(project_root)],
    binaries=native_binaries,
    datas=[
        ('app/locales/*.py', 'app/locales'),
        ('resources/tigercapture.ico', 'resources'),
        ('resources/luts/*.cube', 'resources/luts'),
        ('resources/ui/sound_editor/*.png', 'resources/ui/sound_editor'),
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
        'test',
        # NOTE: ``pydoc`` and ``unittest`` are NOT excluded — pyqtgraph
        # (used for the audio-mixer scopes) lazy-imports ``pydoc`` on
        # ``import pyqtgraph``, and parts of its plotting code reach
        # for ``unittest.mock``. Removing either causes Setup-1.4.0
        # builds to fail at startup with "No module named 'pydoc'".
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

capture_scripts = [script for script in a.scripts if Path(script[1]).name == 'main.py'] or [a.scripts[0]]
studio_scripts = [script for script in a.scripts if Path(script[1]).name == 'studio_main.py'] or [a.scripts[-1]]

exe = EXE(
    pyz,
    capture_scripts,
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

studio_exe = EXE(
    pyz,
    studio_scripts,
    [],
    exclude_binaries=True,
    name='TigerStudio',
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
    studio_exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TigerCapture',
)
