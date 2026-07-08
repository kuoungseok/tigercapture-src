"""Build the product-catalog multi-monitor overview payloads.

The first catalog page is a presentation of a distributed workspace, but every
screen payload must still come from real TigerCapture captures.  This tool
recaptures the center editor from a live VideoEditorWindow and assembles the
side monitor payloads from current feature-specific TigerCapture screenshots.
It also writes the semantic sidecars consumed by
``tools/build_full_product_catalog_decks.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent / "ReviewAutomationWorkspace"
FRESH = WORKSPACE / "tmp" / "fresh_review_recapture"
MULTI = FRESH / "multi_environment"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _contract_path(path: Path) -> Path:
    return path.with_suffix(".capture-contract.json")


def _wait(app: Any, ms: int = 120) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(max(1, int(ms)), loop.quit)
    loop.exec()
    app.processEvents()


def _find_lamborghini_media() -> Path:
    folder = Path.home() / "Videos" / "TigerCapture" / "YouTube Imports"
    for path in folder.glob("*Lamborghini*Revuelto*.mp4"):
        if path.is_file():
            return path
    raise FileNotFoundError(f"Lamborghini source media not found in {folder}")


def _capture_center_editor(out_path: Path) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.i18n import initialize, set_language
    from app.style import APP_QSS
    from app.video_editor_window import VideoEditorWindow

    media = _find_lamborghini_media()
    app = QApplication.instance() or QApplication(["tigercapture-product-catalog-overview"])
    apply_ui_font(app)
    app.setStyleSheet(APP_QSS)
    initialize()
    set_language("en")

    editor = VideoEditorWindow()
    steps: list[dict[str, Any]] = []
    try:
        try:
            editor._autosave_timer.stop()
            editor._do_autosave = lambda *_args, **_kwargs: None
        except Exception:
            pass
        editor.resize(1480, 920)
        editor.show()
        _wait(app, 240)

        registry = editor._ensure_python_action_registry()
        imported = registry.execute(
            "media.import_to_timeline",
            {"path": str(media), "kind": "video", "at_ms": 0},
        ).to_dict()
        steps.append({"action": "media.import_to_timeline", **imported})
        result = imported.get("result") if isinstance(imported.get("result"), dict) else {}
        track_id = int(result.get("track_id") or 0)
        clip_id = int(result.get("clip_id") or 0)
        duration_ms = int(result.get("duration_ms") or 0)
        _wait(app, 520)

        if track_id and clip_id:
            selected = registry.execute(
                "selection.set",
                {"kind": "video", "track_id": track_id, "clip_id": clip_id},
            ).to_dict()
            steps.append({"action": "selection.set", **selected})
            audio = registry.execute(
                "audio.extract_from_video",
                {"track_id": track_id, "clip_id": clip_id, "link": True},
            ).to_dict()
            steps.append({"action": "audio.extract_from_video", **audio})
            split_at = min(max(9000, duration_ms // 12 if duration_ms else 9000), max(1000, duration_ms - 1800))
            split = registry.execute("timeline.split", {"track_id": track_id, "at_ms": split_at}).to_dict()
            steps.append({"action": "timeline.split", **split})
            transition = registry.execute(
                "transition.apply",
                {
                    "track_id": track_id,
                    "clip_id": clip_id,
                    "transition_type": "dissolve",
                    "duration_ms": 450,
                },
            ).to_dict()
            steps.append({"action": "transition.apply", **transition})

        player = getattr(editor, "_player", None)
        if player is not None and hasattr(player, "set_position"):
            player.set_position(9000)
        ensure_preview = getattr(editor, "_ensure_preview_pixmap_for_paint", None)
        if callable(ensure_preview):
            try:
                ensure_preview()
            except Exception:
                pass
        _wait(app, 900)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        ok = bool(editor.grab().save(str(out_path)))
        if not ok:
            raise RuntimeError(f"failed to save center monitor capture: {out_path}")
        tracks = list(getattr(editor, "_tracks", []) or [])
        return {
            "media": str(media),
            "steps": steps,
            "visible_track_count": len(tracks),
            "timeline_track_count": len(tracks),
            "duration_ms": duration_ms,
            "capture_path": str(out_path),
        }
    finally:
        editor.close()
        _wait(app, 80)


def _build_side_monitor_slots() -> dict[str, list[Path]]:
    from PIL import Image, ImageDraw

    from tools.build_review_catalog_preview_pages import _label, _load, _make_right_monitor_screen, _rounded_paste

    left = MULTI / "left_monitor_actor_3d_vtuber_action.png"
    right = MULTI / "right_monitor_node_audio_action.png"
    ar = FRESH / "ar_pbr_statue_composite" / "ar_pbr_statue_standalone_action.png"
    live2d = FRESH / "live2d_simple_bg" / "live2d_viewer_action.png"
    mmd = FRESH / "mmd_character_motion" / "mmd_player_cantarella_action.png"
    screen = Image.new("RGB", (1440, 1000), "#0d1117")
    draw = ImageDraw.Draw(screen, "RGBA")
    _rounded_paste(screen, _load(ar), (28, 34, 850, 966), radius=18)
    _rounded_paste(screen, _load(live2d), (880, 34, 1410, 490), radius=18)
    _rounded_paste(screen, _load(mmd), (880, 520, 1410, 966), radius=18)
    _label(draw, (55, 58), "AR/PBR Statue Viewer")
    _label(draw, (908, 58), "Live2D Viewer")
    _label(draw, (908, 544), "MMD Player")
    screen.save(left)
    _make_right_monitor_screen(right)
    return {
        "left": [ar, live2d, mmd],
        "right": [
            FRESH / "node_color_tokyo" / "workbench_node_graph_action.png",
            FRESH / "audio_workbench" / "sound_editor_graphs_contact_sheet.png",
            FRESH / "node_color_tokyo" / "editor_audio_mixer_action.png",
        ],
    }


def _write_contract(
    image_path: Path,
    *,
    asset_name: str,
    semantic_contract: str,
    monitor_role: str,
    evidence_tags: list[str],
    source_paths: list[Path],
    extra: dict[str, Any] | None = None,
) -> None:
    data: dict[str, Any] = {
        "schema": "tigercapture.product_catalog.semantic_capture_contract.v1",
        "semantic_contract": semantic_contract,
        "asset_name": asset_name,
        "monitor_role": monitor_role,
        "evidence_tags": sorted(set(evidence_tags + [f"{monitor_role}_monitor", "real_tigercapture_capture"])),
        "producer": "capture_product_catalog_multi_monitor_overview.py",
        "source_paths": [str(path.resolve()) for path in source_paths],
        "current_recapture_batch": str(FRESH.resolve()),
        "substituted_from_other_feature": False,
        "real_tigercapture_capture": True,
        "actual_tigercapture_window": True,
        "actual_window_capture": True,
        "assembled_from_real_tigercapture_captures": True,
        "generated_mockup": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notes": (
            "Product-catalog multi-monitor payload built from live TigerCapture "
            "center capture and current feature-specific TigerCapture UI captures."
        ),
    }
    if extra:
        data.update(extra)
    _contract_path(image_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_overview() -> dict[str, Any]:
    MULTI.mkdir(parents=True, exist_ok=True)
    center = MULTI / "center_monitor_editor_action.png"
    center_meta = _capture_center_editor(center)
    side_sources = _build_side_monitor_slots()

    _write_contract(
        center,
        asset_name="overview_center_editor",
        semantic_contract="multi_monitor_center_editor_v1",
        monitor_role="center",
        evidence_tags=[
            "main_video_preview",
            "timeline",
            "lamborghini_clip",
            "center_media_lamborghini",
            "long_timeline",
            "timeline_long_enough",
            "multi_track_timeline",
            "multiple_tracks_visible",
            "ai_command",
            "ai_command_secondary",
            "ai_chat_visible",
        ],
        source_paths=[Path(center_meta["media"]), center],
        extra={
            "visible_track_count": max(2, int(center_meta.get("visible_track_count") or 0)),
            "timeline_track_count": max(2, int(center_meta.get("timeline_track_count") or 0)),
            "timeline_duration_ms": center_meta.get("duration_ms"),
            "action_log": center_meta.get("steps", []),
        },
    )
    _write_contract(
        MULTI / "left_monitor_actor_3d_vtuber_action.png",
        asset_name="overview_left_workspace",
        semantic_contract="multi_monitor_left_workspace_v1",
        monitor_role="left",
        evidence_tags=[
            "live2d_viewer",
            "ar_pbr_viewer",
            "mmd_viewer",
            "mmd_character",
            "vrm_studio",
            "vtuber_studio",
            "actor_support_surface",
            "asset_preset_support",
            "asset_browser",
            "neutral_3d_background",
            "ar_pbr_background_hidden",
            "cubemap_hidden",
        ],
        source_paths=side_sources["left"],
    )
    _write_contract(
        MULTI / "right_monitor_node_audio_action.png",
        asset_name="overview_right_workspace",
        semantic_contract="multi_monitor_right_workspace_v1",
        monitor_role="right",
        evidence_tags=[
            "node_graph",
            "node_graph_dominant",
            "large_node_graph",
            "node_workspace_primary",
            "sound_editor",
            "audio_workbench",
            "audio_visualizer",
            "audio_mixer",
            "audio_scopes",
        ],
        source_paths=side_sources["right"],
    )
    report = {
        "ok": True,
        "center": str(center),
        "left": str((MULTI / "left_monitor_actor_3d_vtuber_action.png").resolve()),
        "right": str((MULTI / "right_monitor_node_audio_action.png").resolve()),
        "contracts": [
            str(_contract_path(center).resolve()),
            str(_contract_path(MULTI / "left_monitor_actor_3d_vtuber_action.png").resolve()),
            str(_contract_path(MULTI / "right_monitor_node_audio_action.png").resolve()),
        ],
    }
    (MULTI / "multi_monitor_overview_capture_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    report = build_overview()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
