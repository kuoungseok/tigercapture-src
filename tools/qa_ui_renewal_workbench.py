from __future__ import annotations

import json
import os
import sys
import argparse
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


YOUTUBE_IMPORTS = Path(r"C:\Users\artmouse\Videos\TigerCapture\YouTube Imports")


def _sample_media_path() -> str:
    if YOUTUBE_IMPORTS.exists():
        try:
            files = [
                p
                for p in YOUTUBE_IMPORTS.iterdir()
                if p.is_file()
                and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
                and ".part" not in p.name.lower()
            ]
            files.sort(key=lambda p: p.stat().st_size)
            if files:
                return str(files[0])
        except Exception:
            pass
    fallback = ROOT / "qa_corpus" / "review_demos" / "media" / "overview_screen_demo.mp4"
    return str(fallback)


def _track_and_clip() -> tuple[SimpleNamespace, SimpleNamespace]:
    media = _sample_media_path()
    clip = SimpleNamespace(
        timeline_in_ms=1200,
        timeline_out_ms=8200,
        video_filters={"enabled": True, "contrast": 0.18, "vignette": 0.22},
        chroma_key={"enabled": True, "spill": 0.18},
        bg_removal=None,
        disabled_video_filters=None,
        disabled_chroma_key=None,
        disabled_bg_removal=None,
        transition_out_type="dissolve",
        transition_out_ms=450,
    )
    graph = {
        "output_node": "out",
        "cache_policy": "preview_export_locked",
        "nodes": [
            {"id": "media", "kind": "media_in", "inputs": [], "params": {"source": Path(media).name}},
            {"id": "key", "kind": "chroma_key", "inputs": ["media"], "params": {"spill": 0.18}},
            {"id": "blur", "kind": "b_spline_roto", "inputs": ["key"], "params": {"feather": 24}},
            {"id": "grade", "kind": "color_grade", "inputs": ["blur"], "params": {"look": "cool night"}},
            {"id": "merge", "kind": "merge", "inputs": ["grade"], "params": {"mode": "over"}},
            {"id": "out", "kind": "output", "inputs": ["merge"], "params": {}},
        ],
    }
    view_graph = {
        "next_id": 6,
        "io_positions": {
            "IN": [-350.0, -13.0],
            "OUT": [340.0, -13.0],
        },
        "nodes": [
            {"id": "E1", "kind": "curves", "label": "Color Grade", "x": -245.0, "y": -55.0},
            {"id": "B2", "kind": "blur", "label": "Blur", "x": -105.0, "y": -18.0},
            {"id": "E3", "kind": "glow", "label": "Glow", "x": 35.0, "y": -55.0},
            {"id": "E4", "kind": "vignette", "label": "Vignette", "x": 175.0, "y": -18.0},
        ],
        "connections": [
            {"src_node": "IN", "src_port": "rgb_out", "dst_node": "E1", "dst_port": "rgb_in"},
            {"src_node": "E1", "src_port": "rgb_out", "dst_node": "B2", "dst_port": "rgb_in"},
            {"src_node": "B2", "src_port": "rgb_out", "dst_node": "E3", "dst_port": "rgb_in"},
            {"src_node": "E3", "src_port": "rgb_out", "dst_node": "E4", "dst_port": "rgb_in"},
            {"src_node": "E4", "src_port": "rgb_out", "dst_node": "OUT", "dst_port": "rgb_in"},
        ],
    }
    track = SimpleNamespace(
        id=1,
        label="Video 1",
        source_path=media,
        duration_ms=9800,
        offset_ms=0,
        speed_segments=[],
        fades=[],
        typography_actors=[SimpleNamespace(start_ms=1500, end_ms=3600)],
        zoom_actors=[SimpleNamespace(start_ms=3800, end_ms=7200)],
        vfx_node_graph=graph,
        vfx_node_graphs=[graph],
        node_graph_view_data=view_graph,
    )
    return track, clip


def run_workbench_qa(
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_workbench_round",
) -> dict:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

    from app.font_fallback import apply_ui_font
    from app.style import APP_QSS
    from app.workbench_panel import WorkbenchPanel

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    app.setStyleSheet(APP_QSS)

    out = Path(out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    track, clip = _track_and_clip()
    host = QWidget()
    host.setObjectName("WorkbenchRenewalQA")
    host.setStyleSheet("QWidget#WorkbenchRenewalQA{background:#0E1014;border:1px solid #20252B;}")
    layout = QHBoxLayout(host)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    clip_panel = WorkbenchPanel(host)
    clip_panel.setFixedSize(340, 610)
    clip_panel.set_video_track(track, selected_clip=clip)
    layout.addWidget(clip_panel)

    fx_panel = WorkbenchPanel(host)
    fx_panel.setFixedSize(560, 610)
    fx_panel.set_video_track(track, selected_clip=clip)
    fx_panel._set_inspector_tab("fx")
    layout.addWidget(fx_panel)

    host.resize(924, 626)
    host.show()
    app.processEvents()
    try:
        fx_panel._node_graph_widget.fit_all()
    except Exception:
        pass
    app.processEvents()

    png = out / "workbench_clip_and_node.png"
    ok = bool(host.grab().save(str(png)))
    host.close()
    host.deleteLater()
    app.processEvents()

    report = {
        "ok": ok,
        "artifact": str(png.resolve()),
        "media": str(getattr(track, "source_path", "")),
    }
    (out / "ui_renewal_workbench_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "ui_renewal_workbench_round"))
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    report = run_workbench_qa(args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
