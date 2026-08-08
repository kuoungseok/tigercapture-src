import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _mime_with_data(mime_type: str, payload: str):
    from PySide6.QtCore import QMimeData

    mime = QMimeData()
    mime.setData(mime_type, payload.encode("utf-8"))
    return mime


def _mime_for_path(path: Path):
    from PySide6.QtCore import QMimeData, QUrl

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    return mime


def test_timeline_drop_guide_reports_ar_pbr_assets(tmp_path):
    from app.timeline_drop_guides import (
        drop_guide_segments_for_mime,
        drop_guide_text,
        drop_guide_width_for_mime,
    )

    asset = tmp_path / "prop.obj"
    mime = _mime_for_path(asset)

    assert drop_guide_text(mime) == "3D"
    assert drop_guide_width_for_mime(mime, px_per_sec=100.0) == 360
    assert drop_guide_segments_for_mime(mime) == [{
        "kind": "3d",
        "label": "3D",
        "start_ms": 0,
        "duration_ms": 10_000,
        "color": "#5B8CFF",
    }]


def test_timeline_drop_guide_reports_motion_actor_duration(tmp_path):
    from app.motion_designer.project_io import save_motion_project
    from app.motion_designer.schema import MotionComposition
    from app.timeline_drop_guides import (
        drop_guide_segments_for_mime,
        drop_guide_text,
        drop_guide_width_for_mime,
    )

    asset = save_motion_project(
        MotionComposition(name="UI Reveal", duration_ms=4200),
        tmp_path / "ui-reveal.tgmotion",
    )
    mime = _mime_for_path(asset)

    assert drop_guide_text(mime) == "Motion Actor"
    assert drop_guide_width_for_mime(mime, px_per_sec=100.0) == 420
    assert drop_guide_segments_for_mime(mime) == [{
        "kind": "motion_actor",
        "label": "Motion Actor",
        "start_ms": 0,
        "duration_ms": 4200,
        "color": "#27C2A0",
    }]


def test_timeline_drop_guide_effect_detail_uses_preset_metadata():
    from app.timeline_drop_guides import drop_guide_detail_for_mime, effect_preset_drag_label
    from app.video_editor_preset_cards import EFFECT_PRESET_MIME_TYPE

    mime = _mime_with_data(
        EFFECT_PRESET_MIME_TYPE,
        json.dumps({"__preset_meta": {"name": "Glow Punch"}}),
    )

    assert effect_preset_drag_label(mime, default="FX") == "Glow Punch"
    assert drop_guide_detail_for_mime(mime, effect_default_label="FX") == "clip FX / Glow Punch"


def test_timeline_drop_guide_editor_sequence_segments():
    from app.timeline_drop_guides import drop_guide_segments_for_mime, drop_guide_width_for_mime
    from app.video_editor_preset_cards import EDITOR_PRESET_MIME_TYPE

    mime = _mime_with_data(
        EDITOR_PRESET_MIME_TYPE,
        json.dumps({
            "kind": "template",
            "name": "Creator Beat",
            "payload": {
                "sequence": [
                    {"kind": "effect", "preset_id": "soft-glow", "at_ms": 0, "duration_ms": 900},
                    {"kind": "title", "preset_id": "lower-third", "at_ms": 1800, "duration_ms": 1200},
                ],
            },
        }),
    )

    assert drop_guide_width_for_mime(mime, px_per_sec=100.0) == 360
    assert drop_guide_segments_for_mime(mime) == [
        {
            "kind": "effect",
            "label": "Soft Glow",
            "start_ms": 0,
            "duration_ms": 900,
            "color": "#8A8F98",
        },
        {
            "kind": "title",
            "label": "Lower Third",
            "start_ms": 1800,
            "duration_ms": 1200,
            "color": "#A692A8",
        },
    ]
