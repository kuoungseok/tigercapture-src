import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _mime_with_data(mime_type: str, payload: str):
    from PySide6.QtCore import QMimeData

    mime = QMimeData()
    mime.setData(mime_type, payload.encode("utf-8"))
    return mime


def test_timeline_drop_payloads_parse_speed_v2():
    from app.effect_cards import SPEED_MIME_TYPE
    from app.timeline_drop_payloads import speed_payload_from_mime

    mime = _mime_with_data(SPEED_MIME_TYPE, "0.5|2400|1|optical_flow")

    assert speed_payload_from_mime(
        mime,
        default_speed=1.0,
        default_duration_ms=1800,
    ) == {
        "speed": 0.5,
        "duration_ms": 2400,
        "frame_blend": True,
        "blend_mode": "optical_flow",
    }


def test_timeline_drop_payloads_transition_falls_back_on_bad_json():
    from app.timeline_drop_payloads import transition_payload_from_mime
    from app.video_editor_preset_cards import TRANSITION_MIME_TYPE

    mime = _mime_with_data(TRANSITION_MIME_TYPE, "{not-json")

    assert transition_payload_from_mime(mime) == {
        "type": "dissolve",
        "duration_ms": 500,
        "raw": {},
    }


def test_timeline_drop_payloads_reject_invalid_preset_json():
    from app.timeline_drop_payloads import (
        editor_preset_from_mime,
        effect_preset_from_mime,
        title_preset_from_mime,
    )
    from app.video_editor_preset_cards import (
        EDITOR_PRESET_MIME_TYPE,
        EFFECT_PRESET_MIME_TYPE,
        TITLE_PRESET_MIME_TYPE,
    )

    assert title_preset_from_mime(_mime_with_data(TITLE_PRESET_MIME_TYPE, "[")) is None
    assert effect_preset_from_mime(_mime_with_data(EFFECT_PRESET_MIME_TYPE, "[")) is None
    assert editor_preset_from_mime(_mime_with_data(EDITOR_PRESET_MIME_TYPE, "[")) is None
