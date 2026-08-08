from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import wave

import numpy as np
from PIL import Image

from app.actions.registry import ActionRegistry
from app.motion_designer.ai_continuity import (
    motion_ai_audit_report,
    validate_motion_continuity,
)
from app.motion_designer.ai_generation import (
    apply_motion_ai_patch,
    generate_motion_ai_patch,
    generate_motion_ai_proposal,
)
from app.motion_designer.ai_workspace import (
    MotionAIReference,
    apply_motion_ai_proposal,
    reference_from_path,
)
from app.motion_designer.reference_analysis import (
    analyze_motion_references,
    apply_video_motion_reference,
)
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.semantic_segmentation import normalize_object_hints


def _write_click_track(path: Path) -> None:
    sample_rate = 16_000
    samples = np.zeros(sample_rate * 2, dtype=np.float32)
    for start in (0, 4_000, 8_000, 12_000, 16_000, 24_000):
        end = min(samples.size, start + 180)
        samples[start:end] = np.hanning(max(1, end - start)).astype(np.float32)
    pcm = np.clip(samples * 24_000, -32_768, 32_767).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(pcm.tobytes())


def test_audio_reference_is_admitted_and_creates_timing_markers(
    tmp_path: Path,
) -> None:
    source = tmp_path / "beat.wav"
    _write_click_track(source)
    reference = reference_from_path(source)

    assert reference.kind == "audio"
    provenance = reference.metadata["provenance"]
    assert provenance["fingerprint"]
    assert provenance["c2pa_signed"] is False

    analysis = analyze_motion_references([reference], duration_ms=2_000)
    assert analysis["audio"]
    assert analysis["beat_markers_ms"]
    assert analysis["audio"][0]["provider"] == "wav_or_ffmpeg"


def test_image_reference_exposes_palette_and_tone_scope(
    tmp_path: Path,
) -> None:
    source = tmp_path / "style.png"
    image = Image.new("RGB", (120, 80), "#162b42")
    for x in range(60, 120):
        for y in range(80):
            image.putpixel((x, y), (225, 92, 52))
    image.save(source)
    reference = reference_from_path(source)
    analysis = analyze_motion_references([reference], duration_ms=1_000)

    assert analysis["image_style"][0]["palette"]
    assert analysis["image_style"][0]["scope"] == "palette_and_tone_reference"
    assert analysis["image_style"][0]["identity_transfer"] is False


def test_video_motion_reference_becomes_editable_source_curves() -> None:
    layer = MotionLayer(
        layer_type="image",
        source=SourceRef(kind="image", uri="hero.png"),
        in_ms=0,
        out_ms=2_000,
    )
    changed = apply_video_motion_reference([layer], {
        "provider": "test_flow",
        "source_path": "motion.mp4",
        "scope": "camera_and_layer_motion_reference",
        "samples": [
            {"time_ratio": 0.0, "dx": 0.01, "dy": -0.02, "intensity": 0.2},
            {"time_ratio": 1.0, "dx": -0.02, "dy": 0.01, "intensity": 0.7},
        ],
    })

    assert changed == 1
    assert len(layer.source.params["tilt_x"]["keyframes"]) == 2
    assert len(layer.source.params["tilt_y"]["keyframes"]) == 2
    assert layer.source.params["perspective"]["metadata"]["motion_reference"] == "video"
    assert layer.metadata["motion_reference"]["pose_transfer"] is False


def test_object_hint_part_rig_metadata_is_preserved() -> None:
    hints = normalize_object_hints([
        {
            "id": "character",
            "label": "character",
            "bbox": [0.1, 0.05, 0.5, 0.9],
            "pivot": [0.35, 0.75],
        },
        {
            "id": "arm",
            "label": "arm",
            "part": "left_arm",
            "parent_id": "character",
            "rigid": True,
            "bbox": [0.45, 0.2, 0.2, 0.5],
            "pivot": [0.48, 0.25],
        },
    ])

    assert hints[1].parent_id == "character"
    assert hints[1].part == "left_arm"
    assert hints[1].pivot == (0.48, 0.25)
    assert hints[1].to_dict()["rigid"] is True


def test_conversational_patch_preserves_identity_and_records_audit() -> None:
    composition = MotionComposition(duration_ms=2_000)
    reference = MotionAIReference(
        kind="image",
        id="ref_hero",
        name="hero.png",
        uri="C:/missing/hero.png",
    )
    proposal = generate_motion_ai_proposal(
        composition,
        'clean "Hero"',
        [reference],
        provider_id="rule_based",
        decompose_images=False,
    )
    applied = apply_motion_ai_proposal(composition, proposal)
    image_layer = next(item for item in applied.layers if item.layer_type == "image")
    patch = generate_motion_ai_patch(
        applied,
        "tilt right",
        [image_layer.id],
        provider_id="rule_based",
    )
    changed = apply_motion_ai_patch(applied, patch)

    updated = next(item for item in changed.layers if item.id == image_layer.id)
    assert updated.source.uri == image_layer.source.uri
    assert updated.source.params["tilt_y"] == 5.0
    continuity = validate_motion_continuity(applied, changed)
    assert continuity["ok"] is True
    audit = motion_ai_audit_report(changed)
    assert [item["event_type"] for item in audit["history"]] == [
        "proposal_apply",
        "patch_apply",
    ]
    assert audit["c2pa_signed"] is False


def test_image_curve_and_ai_audit_actions_share_the_composition() -> None:
    class Owner:
        def __init__(self) -> None:
            image = MotionLayer(
                id="hero",
                layer_type="image",
                source=SourceRef(kind="image", uri="hero.png"),
                out_ms=2_000,
            )
            self._motion_compositions = {
                "comp": MotionComposition(
                    id="comp",
                    duration_ms=2_000,
                    layers=[image],
                ),
            }
            self._motion_clips = []
            self._player = SimpleNamespace(refresh_current_frame=lambda: None)

        def _sync_motion_state_to_player(self) -> None:
            return None

        def _rebuild_motion_lanes(self) -> None:
            return None

    owner = Owner()
    registry = ActionRegistry(owner)
    keyed = registry.execute("motion.image.param.keyframe.set", {
        "composition_id": "comp",
        "layer_id": "hero",
        "parameter_name": "tilt_y",
        "keyframe": {"time_ms": 600, "value": 4.5},
    })
    assert keyed.ok
    changed = registry.execute("motion.image.param.set", {
        "composition_id": "comp",
        "layer_id": "hero",
        "parameter_name": "tilt_y",
        "value": 1.5,
    })
    assert changed.ok
    value = owner._motion_compositions["comp"].layers[0].source.params["tilt_y"]
    assert value["default"] == 1.5
    assert value["keyframes"][0]["value"] == 4.5

    continuity = registry.execute("motion.ai.continuity.validate", {
        "composition_id": "comp",
    })
    provenance = registry.execute("motion.ai.provenance.inspect", {
        "composition_id": "comp",
    })
    assert continuity.ok and continuity.result["ok"] is True
    assert provenance.ok and provenance.result["c2pa_signed"] is False
