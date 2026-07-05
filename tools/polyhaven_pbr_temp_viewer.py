"""Temporary Poly Haven PBR sample viewer.

This launches the app-facing AR/PBR preview window with the local CC0 sample
pack under sample_assets/pbr_blender_scenes/polyhaven.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from app.ar_pbr.preview_window import ArPbrAssetPreviewWindow


SAMPLE_ROOT = ROOT / "sample_assets" / "pbr_blender_scenes" / "polyhaven"
DEFAULT_ASSET = SAMPLE_ROOT / "models" / "Camera_01" / "Camera_01_1k.gltf"
DEFAULT_HDRI = SAMPLE_ROOT / "hdris" / "wooden_studio_17" / "wooden_studio_17_1k.hdr"


def _configure_gl() -> None:
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)


def main() -> int:
    parser = argparse.ArgumentParser(description="Open the temporary Poly Haven PBR sample viewer.")
    parser.add_argument("--asset", default=str(DEFAULT_ASSET), help="GLTF/FBX/VRM asset path")
    parser.add_argument("--hdri", default=str(DEFAULT_HDRI), help="HDR/EXR environment path")
    parser.add_argument("--max-triangles", type=int, default=250_000)
    parser.add_argument("--texture-max-size", type=int, default=1024)
    args = parser.parse_args()

    asset = Path(args.asset).expanduser()
    hdri = Path(args.hdri).expanduser() if str(args.hdri or "").strip() else None
    if not asset.is_absolute():
        asset = (ROOT / asset).resolve()
    if hdri is not None and not hdri.is_absolute():
        hdri = (ROOT / hdri).resolve()

    _configure_gl()
    app = QApplication(sys.argv)
    window = ArPbrAssetPreviewWindow(
        asset,
        initial_lighting={
            "hdri_path": str(hdri) if hdri is not None else "",
            "render_profile": "marmoset_pbr",
            "ibl_exposure": 1.18,
            "direct_intensity": 0.36,
            "shadow_strength": 0.42,
            "self_shadow_strength": 0.45,
        },
        track_label="Poly Haven temporary scene",
        max_triangles=max(1_000, int(args.max_triangles)),
        texture_max_size=max(64, int(args.texture_max_size)),
    )
    window.setWindowTitle("Tiger Studio - Poly Haven PBR Temp Viewer")
    window.resize(1180, 760)
    window.move(80, 60)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
