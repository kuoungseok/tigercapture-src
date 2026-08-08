from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage

from app.motion_designer.actor_source import (
    LIVE2D_SOURCE_KIND,
    SPINE_SOURCE_KIND,
    create_actor_layer,
    evaluate_actor_frame,
)
from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.validation import validate_composition


ROOT = Path(__file__).resolve().parents[1]
LIVE2D = ROOT / "resources/live2d_samples/CubismWebSamples/Samples/Resources/Hiyori/Hiyori.model3.json"
SPINE = ROOT / "resources/spine_samples/celestial-circus/export/celestial-circus-pro.skel"


def test_actor_sources_are_serializable_and_select_real_animation_metadata() -> None:
    live2d = create_actor_layer(
        LIVE2D_SOURCE_KIND, LIVE2D, width=640, height=360, duration_ms=3000,
    )
    spine = create_actor_layer(
        SPINE_SOURCE_KIND, SPINE, width=640, height=360, duration_ms=3000,
    )
    composition = MotionComposition(width=640, height=360, duration_ms=3000, layers=[live2d, spine])

    assert live2d.source.params["playback"]["motion_group"] == "Idle"
    assert live2d.source.params["catalog"]["motions"]
    assert spine.source.params["playback"]["animation"]
    assert spine.source.params["asset"]["atlas_path"].endswith("celestial-circus-pma.atlas")
    assert validate_composition(composition).ok
    restored = MotionComposition.from_dict(composition.to_dict())
    assert restored.to_dict() == composition.to_dict()


def test_live2d_voice_cues_evaluate_as_timeline_mouth_parameters() -> None:
    layer = create_actor_layer(
        LIVE2D_SOURCE_KIND, LIVE2D, width=640, height=360, duration_ms=3000,
    )
    layer.metadata["voice_timing_source_id"] = "voice_1"
    layer.metadata["lip_sync_cues"] = [{"start_ms": 400, "end_ms": 800, "text": "Tiger"}]

    closed = evaluate_actor_frame(layer, 200, composition_time_ms=200)
    open_frame = evaluate_actor_frame(layer, 600, composition_time_ms=600)

    assert closed.mouth_open == 0
    assert open_frame.mouth_open > .7
    assert open_frame.diagnostics["voice_timing_source_id"] == "voice_1"


def test_spine_adapter_uses_one_shared_preview_export_renderer(monkeypatch) -> None:
    from app.motion_designer.adapters import spine as adapter
    from app.spine_editor import actor_track

    layer = create_actor_layer(
        SPINE_SOURCE_KIND, SPINE, width=64, height=64, duration_ms=1000,
    )
    composition = MotionComposition(width=64, height=64, duration_ms=1000, layers=[layer])
    calls: list[tuple[int, bool]] = []

    def fake_render(self, width, height, pos_ms, animated=True, fast_preview=False, use_gl=True):
        calls.append((int(pos_ms), bool(use_gl)))
        image = QImage(width, height, QImage.Format_RGBA8888)
        image.fill(0xFF205080)
        return image

    monkeypatch.setattr(actor_track.SpineActorClip, "render_frame", fake_render)
    adapter.clear_spine_cache()
    preview = adapter.render_spine(layer, 500, composition=composition, quality="preview", viewport_size=(64, 64))
    exported = adapter.render_spine(layer, 500, composition=composition, quality="export", viewport_size=(64, 64))

    assert not preview.isNull() and not exported.isNull()
    assert calls == [(500, False), (500, False)]
    assert adapter.spine_diagnostics(layer.id)["renderer"] == "spine_shared_cpu_parity"


def test_live2d_adapter_resets_and_steps_forward_for_arbitrary_seek(monkeypatch) -> None:
    from app.motion_designer.adapters import live2d as adapter

    layer = create_actor_layer(
        LIVE2D_SOURCE_KIND, LIVE2D, width=32, height=32, duration_ms=1000,
    )
    composition = MotionComposition(width=32, height=32, duration_ms=1000, layers=[layer])
    rendered: list[int] = []

    class FakeClip:
        model_path = str(LIVE2D)
        motion_group = ""
        motion_idx = 0
        expression_id = ""
        pos_x = pos_y = .5
        scale = opacity = 1.0
        parameter_keyframes = {}
        mocap_parameter_keyframes = {}

        def render_frame(self, width, height, pos_ms):
            rendered.append(int(pos_ms))
            image = QImage(width, height, QImage.Format_RGBA8888)
            image.fill(0xFF803020)
            return image

    monkeypatch.setattr(adapter, "_new_clip", lambda *_args, **_kwargs: FakeClip())
    monkeypatch.setattr(adapter, "_evict", lambda _clip: None)
    adapter.clear_live2d_cache()
    first = adapter.render_live2d(layer, 100, composition=composition, quality="preview", viewport_size=(32, 32))
    second = adapter.render_live2d(layer, 33, composition=composition, quality="preview", viewport_size=(32, 32))

    assert not first.isNull() and not second.isNull()
    assert rendered[:4] == [0, 33, 67, 100]
    assert rendered[-2:] == [0, 33]
    assert adapter.live2d_diagnostics(layer.id)["arbitrary_seek_policy"].startswith("reset")
