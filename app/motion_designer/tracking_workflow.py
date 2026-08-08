"""Provider-neutral tracking assets and transform application for Motion."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from math import cos, radians, sin
from pathlib import Path
from typing import Any
from uuid import uuid4

from .mask_tracking import MotionTrackingCache
from .schema import AnimatedProperty, Keyframe, MotionLayer


TRACK_ASSET_SCHEMA = "tigerstudio.motion.track_asset.v1"
TRACK_KINDS = ("point", "multi_point", "planar", "mask", "face")


def source_revision_for_path(path: str | Path) -> str:
    source = Path(path).expanduser().resolve(strict=False)
    if not source.is_file():
        return ""
    stat = source.stat()
    digest = sha256()
    digest.update(f"{source}|{stat.st_size}|{stat.st_mtime_ns}".encode("utf-8"))
    with source.open("rb") as handle:
        digest.update(handle.read(65536))
        if stat.st_size > 65536:
            handle.seek(max(0, stat.st_size - 65536))
            digest.update(handle.read(65536))
    return digest.hexdigest()


def face_tracking_cache_from_video(
    video_path: str | Path,
    *,
    backend: str = "auto",
    max_fps: float = 15.0,
    max_frames: int | None = None,
) -> MotionTrackingCache:
    from app.vtuber.video_face_driver import VideoFaceMotionExtractor
    from .mask_tracking import MotionTrackSample

    source = str(video_path)
    extraction = VideoFaceMotionExtractor(
        max_fps=float(max_fps),
        backend=str(backend or "auto"),
    ).extract(source, max_frames=max_frames)
    if not extraction.ok or not extraction.frames:
        errors = extraction.diagnostics.get("errors", [])
        raise ValueError(
            "face video tracking failed: "
            + ", ".join(str(item) for item in errors or ["no face samples"])
        )
    reference_box = next(
        (frame.face_box for frame in extraction.frames if frame.face_box),
        None,
    )
    if reference_box is None:
        raise ValueError("face video tracking produced no visible face box")
    ref_x, ref_y, ref_w, ref_h = reference_box
    ref_center = (ref_x + ref_w * 0.5, ref_y + ref_h * 0.5)
    samples = []
    for frame in extraction.frames:
        x, y, width, height = frame.face_box or reference_box
        center = (x + width * 0.5, y + height * 0.5)
        samples.append(MotionTrackSample(
            time_ms=int(frame.time_ms),
            translate=(
                center[0] - ref_center[0],
                center[1] - ref_center[1],
            ),
            scale=(
                width / max(1.0, float(ref_w)),
                height / max(1.0, float(ref_h)),
            ),
            rotation=float(frame.roll_deg),
            confidence=float(frame.confidence),
        ))
    diagnostics = dict(extraction.diagnostics)
    diagnostics.update({
        "provider": extraction.diagnostics.get("selected_backend", "auto"),
        "source_uri": source,
        "source_motion_channels": ["face_center", "face_scale", "roll"],
    })
    return MotionTrackingCache(
        mode="planar",
        origin=ref_center,
        samples=samples,
        source_revision=source_revision_for_path(source),
        metadata=diagnostics,
    )


def retime_tracking_samples(
    samples: Sequence[Mapping[str, Any]],
    *,
    source_in_ms: int,
    timeline_in_ms: int,
    timeline_out_ms: int,
    time_scale: float,
) -> list[dict[str, Any]]:
    scale = max(1e-6, abs(float(time_scale or 1.0)))
    source_start = int(source_in_ms)
    source_end = source_start + int(
        round(max(0, int(timeline_out_ms) - int(timeline_in_ms)) * scale)
    )
    output = []
    for value in samples:
        source_time = int(value.get("time_ms", 0) or 0)
        if source_time < source_start or source_time > source_end:
            continue
        item = dict(value)
        item["time_ms"] = int(timeline_in_ms) + int(
            round((source_time - source_start) / scale)
        )
        output.append(item)
    return output


def face_tracking_cache_from_video(
    video_path: str | Path,
    *,
    backend: str = "auto",
    max_fps: float = 15.0,
    max_frames: int | None = None,
) -> MotionTrackingCache:
    from app.vtuber.video_face_driver import VideoFaceMotionExtractor
    from .mask_tracking import MotionTrackSample

    source = str(video_path)
    extraction = VideoFaceMotionExtractor(
        max_fps=float(max_fps),
        backend=str(backend or "auto"),
    ).extract(source, max_frames=max_frames)
    if not extraction.ok or not extraction.frames:
        errors = extraction.diagnostics.get("errors", [])
        raise ValueError(
            "face video tracking failed: "
            + ", ".join(str(item) for item in errors or ["no face samples"])
        )
    reference_box = next(
        (frame.face_box for frame in extraction.frames if frame.face_box),
        None,
    )
    if reference_box is None:
        raise ValueError("face video tracking produced no visible face box")
    ref_x, ref_y, ref_w, ref_h = reference_box
    ref_center = (ref_x + ref_w * 0.5, ref_y + ref_h * 0.5)
    samples = []
    for frame in extraction.frames:
        x, y, width, height = frame.face_box or reference_box
        center = (x + width * 0.5, y + height * 0.5)
        samples.append(MotionTrackSample(
            time_ms=int(frame.time_ms),
            translate=(
                center[0] - ref_center[0],
                center[1] - ref_center[1],
            ),
            scale=(
                width / max(1.0, float(ref_w)),
                height / max(1.0, float(ref_h)),
            ),
            rotation=float(frame.roll_deg),
            confidence=float(frame.confidence),
        ))
    diagnostics = dict(extraction.diagnostics)
    diagnostics.update({
        "provider": extraction.diagnostics.get("selected_backend", "auto"),
        "source_uri": source,
        "source_motion_channels": ["face_center", "face_scale", "roll"],
    })
    return MotionTrackingCache(
        mode="planar",
        origin=ref_center,
        samples=samples,
        source_revision=source_revision_for_path(source),
        metadata=diagnostics,
    )


def normalize_track_asset(data: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(data.get("kind") or "point").strip().lower()
    if kind not in TRACK_KINDS:
        raise ValueError(f"unsupported Motion track kind: {kind}")
    stored_cache = (
        dict(data.get("cache") or {})
        if isinstance(data.get("cache"), Mapping)
        else {}
    )
    cache = MotionTrackingCache.from_dict({
        "mode": "planar" if kind in {"planar", "multi_point", "face"} else "point",
        **stored_cache,
        "enabled": data.get("enabled", stored_cache.get("enabled", True)),
        "origin": data.get("origin", stored_cache.get("origin", (0.0, 0.0))),
        "samples": data.get("samples", stored_cache.get("samples", ())),
        "corrections": data.get(
            "corrections",
            stored_cache.get("corrections", ()),
        ),
        "frozen": data.get("frozen", stored_cache.get("frozen", False)),
        "source_revision": data.get(
            "source_revision",
            stored_cache.get("source_revision", ""),
        ),
        "metadata": data.get("metadata", stored_cache.get("metadata", {})),
    })
    if not cache.samples:
        raise ValueError("Motion track asset requires at least one sample")
    return {
        "schema": TRACK_ASSET_SCHEMA,
        "id": str(data.get("id") or f"track_{uuid4().hex}"),
        "name": str(data.get("name") or kind.replace("_", " ").title()),
        "kind": kind,
        "source_uri": str(data.get("source_uri") or ""),
        "source_revision": str(data.get("source_revision") or ""),
        "cache": cache.to_dict(),
        "metadata": dict(data.get("metadata") or {}),
    }


def tracking_assets(metadata: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    values = (metadata or {}).get("tracking_assets", [])
    return [
        normalize_track_asset(item)
        for item in values
        if isinstance(item, Mapping)
    ]


def track_asset_diagnostics(
    asset: Mapping[str, Any],
    *,
    current_source_revision: str = "",
) -> dict[str, Any]:
    normalized = normalize_track_asset(asset)
    cache = MotionTrackingCache.from_dict(normalized["cache"])
    confidences = [float(item.confidence) for item in cache.samples]
    low = [value < 0.15 for value in confidences]
    reacquire_count = sum(
        1 for previous, current in zip(low, low[1:]) if previous and not current
    )
    provider_reacquired = int(cache.metadata.get("reacquired_frames", 0) or 0)
    reacquire_count = max(reacquire_count, provider_reacquired)
    occlusion_spans: list[dict[str, int]] = []
    span_start: int | None = None
    for sample, occluded in zip(cache.samples, low):
        if occluded and span_start is None:
            span_start = sample.time_ms
        elif not occluded and span_start is not None:
            occlusion_spans.append({
                "start_ms": span_start,
                "end_ms": sample.time_ms,
            })
            span_start = None
    if span_start is not None:
        occlusion_spans.append({
            "start_ms": span_start,
            "end_ms": cache.samples[-1].time_ms,
        })
    steps = []
    for previous, current in zip(cache.samples, cache.samples[1:]):
        dx = current.translate[0] - previous.translate[0]
        dy = current.translate[1] - previous.translate[1]
        steps.append((dx * dx + dy * dy) ** 0.5)
    expected_revision = normalized["source_revision"]
    revision_matches = (
        not expected_revision
        or not current_source_revision
        or expected_revision == current_source_revision
    )
    mean_confidence = sum(confidences) / max(1, len(confidences))
    occlusion_ratio = sum(low) / max(1, len(low))
    maximum_step = max(steps, default=0.0)
    target_width = float(cache.metadata.get("target_width", 0) or 0)
    target_height = float(cache.metadata.get("target_height", 0) or 0)
    target_diagonal = (target_width * target_width + target_height * target_height) ** 0.5
    maximum_step_ratio = maximum_step / target_diagonal if target_diagonal > 0 else 0.0
    review_reasons = []
    if mean_confidence < 0.35:
        review_reasons.append("low_confidence")
    if occlusion_ratio > 0.25:
        review_reasons.append("frequent_occlusion")
    if maximum_step_ratio > 0.12:
        review_reasons.append("large_frame_step")
    if not revision_matches:
        review_reasons.append("source_revision_mismatch")
    quality_state = (
        "relink_required"
        if not revision_matches
        else "review" if review_reasons else "good"
    )
    return {
        "schema": TRACK_ASSET_SCHEMA,
        "track_id": normalized["id"],
        "kind": normalized["kind"],
        "sample_count": len(cache.samples),
        "start_ms": cache.samples[0].time_ms,
        "end_ms": cache.samples[-1].time_ms,
        "mean_confidence": mean_confidence,
        "minimum_confidence": min(confidences),
        "occluded_sample_count": sum(low),
        "occlusion_ratio": occlusion_ratio,
        "reacquire_count": reacquire_count,
        "predicted_sample_count": int(cache.metadata.get("predicted_frames", 0) or 0),
        "motion_outlier_count": int(
            cache.metadata.get("motion_outlier_frames", 0) or 0
        ),
        "occlusion_spans": occlusion_spans,
        "maximum_step_px": maximum_step,
        "maximum_step_ratio": maximum_step_ratio,
        "source_revision": expected_revision,
        "current_source_revision": str(current_source_revision or ""),
        "source_revision_matches": revision_matches,
        "frozen": cache.frozen,
        "quality_state": quality_state,
        "review_reasons": review_reasons,
    }


def _pair(value: Any, default: Sequence[float]) -> tuple[float, float]:
    values = list(value) if isinstance(value, (list, tuple)) else list(default)
    if len(values) < 2:
        values = list(default)
    return float(values[0]), float(values[1])


def apply_track_to_layer(
    layer: MotionLayer,
    asset: Mapping[str, Any],
    *,
    stabilize: bool = False,
    channels: Sequence[str] = ("position", "scale", "rotation"),
) -> dict[str, Any]:
    normalized = normalize_track_asset(asset)
    cache = MotionTrackingCache.from_dict(normalized["cache"])
    selected = {str(item) for item in channels}
    sign = -1.0 if stabilize else 1.0
    base_position = _pair(layer.transform.position.default, (0.0, 0.0))
    base_scale = _pair(layer.transform.scale.default, (1.0, 1.0))
    base_rotation = float(layer.transform.rotation.default or 0.0)

    if "position" in selected:
        layer.transform.position = AnimatedProperty(
            value_type="vector2",
            default=list(base_position),
            keyframes=[
                Keyframe(
                    time_ms=sample.time_ms,
                    value=[
                        base_position[0] + sample.translate[0] * sign,
                        base_position[1] + sample.translate[1] * sign,
                    ],
                    metadata={"track_id": normalized["id"]},
                )
                for sample in cache.samples
            ],
        )
    if "scale" in selected and cache.mode == "planar":
        layer.transform.scale = AnimatedProperty(
            value_type="vector2",
            default=list(base_scale),
            keyframes=[
                Keyframe(
                    time_ms=sample.time_ms,
                    value=[
                        base_scale[0] * (
                            (1.0 / max(1e-6, sample.scale[0]))
                            if stabilize else sample.scale[0]
                        ),
                        base_scale[1] * (
                            (1.0 / max(1e-6, sample.scale[1]))
                            if stabilize else sample.scale[1]
                        ),
                    ],
                    metadata={"track_id": normalized["id"]},
                )
                for sample in cache.samples
            ],
        )
    if "rotation" in selected and cache.mode == "planar":
        layer.transform.rotation = AnimatedProperty(
            value_type="scalar",
            default=base_rotation,
            keyframes=[
                Keyframe(
                    time_ms=sample.time_ms,
                    value=base_rotation + sample.rotation * sign,
                    metadata={"track_id": normalized["id"]},
                )
                for sample in cache.samples
            ],
        )
    layer.transform.metadata["tracking"] = {
        "schema": TRACK_ASSET_SCHEMA,
        "track_id": normalized["id"],
        "mode": "stabilize" if stabilize else "attach",
        "channels": sorted(selected),
    }
    return {
        "track_id": normalized["id"],
        "layer_id": layer.id,
        "mode": "stabilize" if stabilize else "attach",
        "keyframe_count": len(cache.samples),
        "channels": sorted(selected),
    }


def apply_track_to_effect_point(
    layer: MotionLayer,
    asset: Mapping[str, Any],
    *,
    effect_id: str,
    parameter: str,
) -> dict[str, Any]:
    normalized = normalize_track_asset(asset)
    cache = MotionTrackingCache.from_dict(normalized["cache"])
    effect = next(
        (item for item in layer.effects if item.id == str(effect_id)),
        None,
    )
    if effect is None:
        raise ValueError(f"Motion effect not found: {effect_id}")
    prop = effect.params.get(str(parameter))
    base = _pair(prop.default if prop is not None else (0.0, 0.0), (0.0, 0.0))
    effect.params[str(parameter)] = AnimatedProperty(
        value_type="vector2",
        default=list(base),
        keyframes=[
            Keyframe(
                time_ms=sample.time_ms,
                value=[
                    base[0] + sample.translate[0],
                    base[1] + sample.translate[1],
                ],
                metadata={"track_id": normalized["id"]},
            )
            for sample in cache.samples
        ],
        metadata={"tracking": {"track_id": normalized["id"]}},
    )
    return {
        "track_id": normalized["id"],
        "layer_id": layer.id,
        "effect_id": effect.id,
        "parameter": str(parameter),
        "mode": "effect_point",
        "keyframe_count": len(cache.samples),
    }


def apply_planar_track_to_corner_pin(
    layer: MotionLayer,
    asset: Mapping[str, Any],
    *,
    effect_id: str,
    target_size: Sequence[float],
) -> dict[str, Any]:
    normalized = normalize_track_asset(asset)
    cache = MotionTrackingCache.from_dict(normalized["cache"])
    if cache.mode != "planar":
        raise ValueError("corner-pin tracking requires a planar track")
    effect = next(
        (item for item in layer.effects if item.id == str(effect_id)),
        None,
    )
    if effect is None:
        raise ValueError(f"Motion effect not found: {effect_id}")
    if str(effect.kind or "").lower() != "corner_pin":
        raise ValueError("corner-pin tracking target must be a Corner Pin effect")

    size = list(target_size)
    width = max(1.0, float(size[0] if len(size) > 0 else 1.0))
    height = max(1.0, float(size[1] if len(size) > 1 else 1.0))
    corners = {
        "top_left": (0.0, 0.0),
        "top_right": (width - 1.0, 0.0),
        "bottom_right": (width - 1.0, height - 1.0),
        "bottom_left": (0.0, height - 1.0),
    }
    origin_x, origin_y = cache.origin
    for parameter, (corner_x, corner_y) in corners.items():
        existing = effect.params.get(parameter)
        base = _pair(
            existing.default if existing is not None else (0.0, 0.0),
            (0.0, 0.0),
        )
        keyframes = []
        for sample in cache.samples:
            angle = radians(sample.rotation)
            scaled_x = (corner_x - origin_x) * sample.scale[0]
            scaled_y = (corner_y - origin_y) * sample.scale[1]
            transformed_x = (
                origin_x
                + scaled_x * cos(angle)
                - scaled_y * sin(angle)
                + sample.translate[0]
            )
            transformed_y = (
                origin_y
                + scaled_x * sin(angle)
                + scaled_y * cos(angle)
                + sample.translate[1]
            )
            keyframes.append(Keyframe(
                time_ms=sample.time_ms,
                value=[
                    base[0] + transformed_x - corner_x,
                    base[1] + transformed_y - corner_y,
                ],
                metadata={"track_id": normalized["id"]},
            ))
        effect.params[parameter] = AnimatedProperty(
            value_type="vector2",
            default=list(base),
            keyframes=keyframes,
            metadata={"tracking": {"track_id": normalized["id"]}},
        )
    effect.metadata["tracking"] = {
        "schema": TRACK_ASSET_SCHEMA,
        "track_id": normalized["id"],
        "mode": "planar_affine_corner_pin",
    }
    return {
        "track_id": normalized["id"],
        "layer_id": layer.id,
        "effect_id": effect.id,
        "mode": "corner_pin",
        "keyframe_count": len(cache.samples),
        "parameters": list(corners),
    }


def apply_track_to_puppet_pin(
    layer: MotionLayer,
    asset: Mapping[str, Any],
    *,
    pin_id: str,
    target_size: Sequence[float],
) -> dict[str, Any]:
    from .puppet_mesh import layer_puppet_mesh, set_layer_puppet_mesh

    normalized = normalize_track_asset(asset)
    cache = MotionTrackingCache.from_dict(normalized["cache"])
    mesh = layer_puppet_mesh(layer)
    if mesh is None:
        raise ValueError("target layer has no Puppet mesh")
    pin = next((item for item in mesh.pins if item.id == str(pin_id)), None)
    if pin is None:
        raise ValueError(f"Puppet pin not found: {pin_id}")
    size = list(target_size)
    width = max(1.0, float(size[0] if len(size) > 0 else 1.0))
    height = max(1.0, float(size[1] if len(size) > 1 else 1.0))
    base = _pair(pin.position.default, pin.rest_position)
    pin.position = AnimatedProperty(
        value_type="vector2",
        default=list(base),
        keyframes=[
            Keyframe(
                time_ms=sample.time_ms,
                value=[
                    base[0] + sample.translate[0] / width,
                    base[1] + sample.translate[1] / height,
                ],
                metadata={"track_id": normalized["id"]},
            )
            for sample in cache.samples
        ],
        metadata={"tracking": {"track_id": normalized["id"]}},
    )
    if cache.mode == "planar":
        base_rotation = float(pin.rotation.default or 0.0)
        pin.rotation = AnimatedProperty(
            value_type="scalar",
            default=base_rotation,
            keyframes=[
                Keyframe(
                    time_ms=sample.time_ms,
                    value=base_rotation + sample.rotation,
                    metadata={"track_id": normalized["id"]},
                )
                for sample in cache.samples
            ],
            metadata={"tracking": {"track_id": normalized["id"]}},
        )
    set_layer_puppet_mesh(layer, mesh)
    return {
        "track_id": normalized["id"],
        "layer_id": layer.id,
        "pin_id": pin.id,
        "mode": "puppet_pin",
        "keyframe_count": len(cache.samples),
    }


__all__ = [
    "TRACK_ASSET_SCHEMA",
    "TRACK_KINDS",
    "apply_planar_track_to_corner_pin",
    "apply_track_to_layer",
    "apply_track_to_effect_point",
    "apply_track_to_puppet_pin",
    "face_tracking_cache_from_video",
    "face_tracking_cache_from_video",
    "normalize_track_asset",
    "retime_tracking_samples",
    "source_revision_for_path",
    "track_asset_diagnostics",
    "tracking_assets",
]
