"""Editable raster-image decomposition for Motion Designer AI.

The service is intentionally Qt-free. It turns one raster reference into a
regenerable set of full-canvas RGBA layers, an inpainted background, and an
optional depth proxy. Heavy semantic models remain optional; the deterministic
baseline uses alpha, GrabCut, connected components, and the shared depth
provider so packaged builds keep a useful local fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .schema import Keyframe, MotionBehaviorRef, MotionComposition, MotionLayer, SourceRef


IMAGE_DECOMPOSITION_SCHEMA = "tigerstudio.motion.image_decomposition.v1"
IMAGE_DECOMPOSITION_ALGORITHM = "semantic_layer_graph_v5"


def _as_bbox(value: Iterable[Any]) -> tuple[int, int, int, int]:
    values = [int(item) for item in value]
    if len(values) < 4:
        raise ValueError("decomposition bbox must contain x, y, width, and height")
    return values[0], values[1], max(1, values[2]), max(1, values[3])


@dataclass(slots=True)
class DecomposedImageElement:
    id: str
    role: str
    label: str
    bbox: tuple[int, int, int, int]
    rgba_path: str
    mask_path: str
    area_ratio: float
    depth: float
    confidence: float
    motion_hint: str = "parallax"
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "label": self.label,
            "bbox": list(self.bbox),
            "rgba_path": self.rgba_path,
            "mask_path": self.mask_path,
            "area_ratio": float(self.area_ratio),
            "depth": float(self.depth),
            "confidence": float(self.confidence),
            "motion_hint": self.motion_hint,
            "text": self.text,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DecomposedImageElement":
        return cls(
            id=str(data.get("id") or ""),
            role=str(data.get("role") or "accent"),
            label=str(data.get("label") or "Element"),
            bbox=_as_bbox(data.get("bbox") or (0, 0, 1, 1)),
            rgba_path=str(data.get("rgba_path") or ""),
            mask_path=str(data.get("mask_path") or ""),
            area_ratio=float(data.get("area_ratio", 0.0) or 0.0),
            depth=float(data.get("depth", 0.5) or 0.5),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            motion_hint=str(data.get("motion_hint") or "parallax"),
            text=str(data.get("text") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class ImageDecompositionResult:
    source_path: str
    source_hash: str
    width: int
    height: int
    background_path: str
    depth_path: str = ""
    elements: list[DecomposedImageElement] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    schema: str = IMAGE_DECOMPOSITION_SCHEMA
    algorithm: str = IMAGE_DECOMPOSITION_ALGORITHM

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "algorithm": self.algorithm,
            "source_path": self.source_path,
            "source_hash": self.source_hash,
            "width": int(self.width),
            "height": int(self.height),
            "background_path": self.background_path,
            "depth_path": self.depth_path,
            "elements": [item.to_dict() for item in self.elements],
            "diagnostics": dict(self.diagnostics),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ImageDecompositionResult":
        if str(data.get("schema") or "") != IMAGE_DECOMPOSITION_SCHEMA:
            raise ValueError("unsupported Motion image decomposition schema")
        return cls(
            schema=str(data.get("schema") or IMAGE_DECOMPOSITION_SCHEMA),
            algorithm=str(data.get("algorithm") or ""),
            source_path=str(data.get("source_path") or ""),
            source_hash=str(data.get("source_hash") or ""),
            width=max(1, int(data.get("width", 1) or 1)),
            height=max(1, int(data.get("height", 1) or 1)),
            background_path=str(data.get("background_path") or ""),
            depth_path=str(data.get("depth_path") or ""),
            elements=[
                DecomposedImageElement.from_dict(item)
                for item in data.get("elements", [])
                if isinstance(item, Mapping)
            ],
            diagnostics=dict(data.get("diagnostics") or {}),
        )

    def assets_ready(self) -> bool:
        required = [self.background_path]
        required.extend(item.rgba_path for item in self.elements)
        required.extend(item.mask_path for item in self.elements)
        if self.depth_path:
            required.append(self.depth_path)
        return bool(self.elements) and all(Path(value).is_file() for value in required if value)


def _default_cache_root() -> Path:
    from app.paths import runtime_data_dir

    return runtime_data_dir() / "motion_ai" / "decompositions"


def _source_fingerprint(
    path: Path,
    width: int,
    height: int,
    max_elements: int,
    *,
    segmentation_mode: str,
    include_depth: bool,
    inpaint_mode: str,
    reconstruct_text: bool,
    ocr_native_threshold: float,
    hint_signature: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(IMAGE_DECOMPOSITION_ALGORITHM.encode("ascii"))
    digest.update(
        (
            f"|{int(width)}x{int(height)}|{int(max_elements)}"
            f"|seg={segmentation_mode}|depth={int(bool(include_depth))}"
            f"|inpaint={inpaint_mode}|text={int(bool(reconstruct_text))}"
            f"|ocr={float(ocr_native_threshold):.3f}|hints={hint_signature}|"
        ).encode("ascii")
    )
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _fit_rgba_canvas(source: Path, width: int, height: int):
    import numpy as np
    from PIL import Image, ImageOps

    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGBA")
    scale = max(float(width) / max(1, image.width), float(height) / max(1, image.height))
    resized = image.resize(
        (max(1, int(round(image.width * scale))), max(1, int(round(image.height * scale)))),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    canvas = resized.crop((left, top, left + width, top + height))
    rgba = np.asarray(canvas, dtype=np.uint8)
    return rgba[:, :, :3].copy(), rgba[:, :, 3].copy()


def _save_rgba(path: Path, rgb, mask) -> None:
    import cv2
    import numpy as np
    from PIL import Image

    radius = max(0.7, min(rgb.shape[:2]) * 0.0025)
    alpha = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), radius)
    alpha = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    rgba = np.dstack((rgb, alpha))
    Image.fromarray(rgba, "RGBA").save(path)


def _save_mask(path: Path, mask) -> None:
    from PIL import Image

    Image.fromarray(mask, "L").save(path)


def decompose_image(
    source_path: str | Path,
    *,
    width: int,
    height: int,
    cache_root: str | Path | None = None,
    max_elements: int = 5,
    include_depth: bool = True,
    segmentation_mode: str = "auto",
    point_hints: Iterable[tuple[float, float]] = (),
    object_hints: Iterable[Mapping[str, Any] | Sequence[Any]] = (),
    inpaint_mode: str = "auto",
    reconstruct_text: bool = True,
    ocr_native_threshold: float = 0.78,
    force: bool = False,
) -> ImageDecompositionResult:
    """Decompose an image into regenerable editable Motion assets."""
    import cv2
    import numpy as np
    from PIL import Image

    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"image reference not found: {source}")
    width = max(64, min(8192, int(width)))
    height = max(64, min(8192, int(height)))
    max_elements = max(1, min(12, int(max_elements)))
    segmentation_mode = str(segmentation_mode or "auto").strip().casefold()
    inpaint_mode = str(inpaint_mode or "auto").strip().casefold()
    ocr_native_threshold = max(0.5, min(0.98, float(ocr_native_threshold)))
    normalized_point_hints = [
        [float(x), float(y)]
        for x, y in point_hints
    ]
    normalized_object_hints = [
        dict(item) if isinstance(item, Mapping) else {"bbox": list(item)}
        for item in object_hints
    ]
    hint_signature = hashlib.sha256(json.dumps(
        {
            "points": normalized_point_hints,
            "objects": normalized_object_hints,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()[:16]
    fingerprint = _source_fingerprint(
        source,
        width,
        height,
        max_elements,
        segmentation_mode=segmentation_mode,
        include_depth=include_depth,
        inpaint_mode=inpaint_mode,
        reconstruct_text=reconstruct_text,
        ocr_native_threshold=ocr_native_threshold,
        hint_signature=hint_signature,
    )
    root = Path(cache_root) if cache_root else _default_cache_root()
    target = root / fingerprint[:20]
    manifest_path = target / "manifest.json"
    if manifest_path.is_file() and not force:
        try:
            cached = ImageDecompositionResult.from_dict(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
            if cached.algorithm == IMAGE_DECOMPOSITION_ALGORITHM and cached.assets_ready():
                cached.diagnostics["cache_hit"] = True
                return cached
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    target.mkdir(parents=True, exist_ok=True)
    rgb, alpha = _fit_rgba_canvas(source, width, height)
    from .semantic_segmentation import component_records, segment_image

    segmentation_result = segment_image(
        rgb,
        alpha,
        mode=segmentation_mode,
        max_elements=max_elements,
        point_hints=normalized_point_hints,
        object_hints=normalized_object_hints,
    )
    foreground = segmentation_result.foreground_mask
    segmentation = {
        "backend": segmentation_result.provider,
        "confidence": segmentation_result.confidence,
        "transparent_source": segmentation_result.transparent_source,
    }
    from .typography_reconstruction import (
        TypographyAnalysis,
        analyze_typography,
        native_typography_mask,
        typography_source_params,
    )

    typography = (
        analyze_typography(
            rgb,
            native_threshold=ocr_native_threshold,
        )
        if reconstruct_text
        else TypographyAnalysis(regions=[], provider="disabled")
    )
    text_mask = native_typography_mask(width, height, typography.regions)
    object_mask = cv2.bitwise_and(foreground, cv2.bitwise_not(text_mask))
    components: list[dict[str, Any]] = []
    for candidate in segmentation_result.candidates:
        candidate_mask = cv2.bitwise_and(
            candidate.mask,
            cv2.bitwise_not(text_mask),
        )
        records = component_records(candidate_mask, max_elements=1)
        if not records:
            continue
        record = records[0]
        record["semantic_label"] = candidate.semantic_label
        record["segmentation_confidence"] = candidate.confidence
        record["segmentation_metadata"] = dict(candidate.metadata)
        components.append(record)
    if not components:
        components = component_records(object_mask, max_elements=max_elements)
    components.sort(key=lambda item: (-float(item["score"]), -int(item["area"])))
    components = components[:max_elements]

    depth_path = ""
    depth_backend = "disabled"
    depth_warnings: list[str] = []
    if include_depth:
        try:
            from app.depth.providers import estimate_depth

            depth, depth_diagnostics = estimate_depth(
                rgb,
                source_id=f"motion-image:{fingerprint[:16]}",
                time_ms=0,
            )
            depth = np.asarray(depth, dtype=np.float32)
            depth_backend = str(depth_diagnostics.get("backend") or "")
            depth_warnings = [str(item) for item in depth_diagnostics.get("warnings", [])]
            depth_path_obj = target / "depth.png"
            Image.fromarray(np.clip(depth * 255.0, 0, 255).astype(np.uint8), "L").save(depth_path_obj)
            depth_path = str(depth_path_obj.resolve())
        except Exception as exc:
            depth = np.full((height, width), 0.5, dtype=np.float32)
            depth_backend = "unavailable"
            depth_warnings = [f"Depth analysis failed: {exc}"]
    else:
        depth = np.full((height, width), 0.5, dtype=np.float32)

    combined_mask = cv2.bitwise_or(foreground, text_mask)
    from .background_inpainting import inpaint_background

    inpaint = inpaint_background(
        rgb,
        combined_mask,
        transparent_source=bool(segmentation.get("transparent_source")),
        mode=inpaint_mode,
    )
    background_array = inpaint.image
    background_path_obj = target / "background.png"
    if background_array.shape[2] == 4:
        Image.fromarray(background_array, "RGBA").save(background_path_obj)
    else:
        Image.fromarray(background_array, "RGB").save(background_path_obj)

    elements: list[DecomposedImageElement] = []
    total_pixels = float(max(1, width * height))
    motion_locked_components = 0
    for index, record in enumerate(components):
        from .mask_integrity import analyze_mask_integrity, motion_lock_required

        mask = record["mask"]
        rgba_path = target / f"element_{index + 1:02d}.png"
        mask_path = target / f"element_{index + 1:02d}_mask.png"
        _save_rgba(rgba_path, rgb, mask)
        _save_mask(mask_path, mask)
        selected_depth = depth[mask > 0]
        depth_value = float(np.median(selected_depth)) if selected_depth.size else 0.5
        role = "primary_subject" if index == 0 else "secondary_element"
        integrity = analyze_mask_integrity(mask)
        motion_lock_to_background, motion_lock_reason = motion_lock_required(
            integrity,
            role=role,
        )
        if motion_lock_to_background:
            motion_locked_components += 1
        elements.append(DecomposedImageElement(
            id=f"element_{index + 1:02d}",
            role=role,
            label="Primary Subject" if index == 0 else f"Secondary Element {index}",
            bbox=_as_bbox(record["bbox"]),
            rgba_path=str(rgba_path.resolve()),
            mask_path=str(mask_path.resolve()),
            area_ratio=float(record["area"]) / total_pixels,
            depth=depth_value,
            confidence=float(segmentation.get("confidence", 0.5)),
            motion_hint="hero_parallax" if index == 0 else "staggered_parallax",
            metadata={
                **dict(record.get("segmentation_metadata") or {}),
                "semantic_label": str(record.get("semantic_label") or "subject"),
                "segmentation_provider": segmentation_result.provider,
                "segmentation_confidence": float(
                    record.get(
                        "segmentation_confidence",
                        segmentation_result.confidence,
                    )
                ),
                "mask_integrity": integrity.to_dict(),
                "mask_fill_ratio": integrity.mask_fill_ratio,
                "motion_lock_to_background": motion_lock_to_background,
                "motion_lock_reason": motion_lock_reason,
            },
        ))

    native_regions = [item for item in typography.regions if item.native_eligible]
    for index, region in enumerate(native_regions[:8]):
        x, y, box_width, box_height = _as_bbox(region.bbox)
        elements.append(DecomposedImageElement(
            id=f"text_{index + 1:02d}",
            role="text",
            label=f"Text: {region.text}",
            bbox=(x, y, box_width, box_height),
            rgba_path="",
            mask_path="",
            area_ratio=float(box_width * box_height) / total_pixels,
            depth=0.98,
            confidence=float(region.confidence),
            motion_hint="kinetic_text",
            text=str(region.text),
            metadata={
                "ocr_backend": typography.provider,
                "typography_role": region.role,
                "native_eligible": True,
                "typography_params": typography_source_params(region),
            },
        ))

    warnings = [*depth_warnings, *typography.warnings, *inpaint.warnings]
    warnings.extend(
        str(item)
        for item in segmentation_result.diagnostics.get("warnings", [])
    )
    foreground_coverage = float(np.count_nonzero(foreground)) / total_pixels
    if not components:
        warnings.append("No stable foreground component was found; use the original image layer.")
    if foreground_coverage > 0.82:
        warnings.append("Foreground covers most of the frame; background inpainting may need mask refinement.")
    if motion_locked_components:
        warnings.append(
            "Sparse or hollow primary masks are motion-locked to the background "
            "to preserve transparent-object integrity."
        )
    from .layer_graph import build_layer_graph

    layer_graph = build_layer_graph(elements, width=width, height=height)
    graph_by_id = layer_graph.by_id()
    for element in elements:
        node = graph_by_id.get(element.id)
        if node is None:
            continue
        element.metadata.update({
            "parent_id": node.parent_id,
            "motion_group_id": node.motion_group_id,
            "rigid": node.rigid,
            "pivot": [float(node.pivot[0]), float(node.pivot[1])],
            "z_order": node.z_order,
        })
    warnings.extend(layer_graph.warnings)
    result = ImageDecompositionResult(
        source_path=str(source),
        source_hash=fingerprint,
        width=width,
        height=height,
        background_path=str(background_path_obj.resolve()),
        depth_path=depth_path,
        elements=elements,
        diagnostics={
            "cache_hit": False,
            "segmentation_mode_requested": segmentation_mode,
            "segmentation_backend": str(segmentation.get("backend") or ""),
            "segmentation_confidence": float(segmentation.get("confidence", 0.0)),
            "segmentation": segmentation_result.summary(),
            "foreground_coverage": foreground_coverage,
            "component_count": len(components),
            "motion_locked_component_count": motion_locked_components,
            "text_region_count": len(typography.regions),
            "native_text_region_count": len(native_regions),
            "raster_text_region_count": len(typography.regions) - len(native_regions),
            "ocr_backend": typography.provider,
            "typography": typography.to_dict(),
            "depth_backend": depth_backend,
            "transparent_source": bool(segmentation.get("transparent_source")),
            "inpaint": inpaint.diagnostics(),
            "max_camera_travel_ratio": inpaint.max_camera_travel_ratio,
            "layer_graph": layer_graph.to_dict(),
            "warnings": warnings,
        },
    )
    from .image_motion_validation import validate_decomposition_result

    validation = validate_decomposition_result(result)
    result.diagnostics["validation"] = validation.to_dict()
    result.diagnostics["warnings"] = list(dict.fromkeys([
        *warnings,
        *validation.warnings,
        *[f"Validation error: {item}" for item in validation.errors],
    ]))
    manifest_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _animated_keyframes(prop, rows: list[tuple[int, Any]]) -> None:
    prop.keyframes = [
        Keyframe(
            time_ms=max(0, int(time_ms)),
            value=value,
            interpolation="bezier",
            out_tangent=(0.2, 0.0),
            in_tangent=(0.8, 1.0),
        )
        for time_ms, value in rows
    ]


def _decomposition_metadata(
    result: ImageDecompositionResult,
    *,
    reference_id: str,
    element: DecomposedImageElement | None,
) -> dict[str, Any]:
    data = {
        "schema": IMAGE_DECOMPOSITION_SCHEMA,
        "algorithm": result.algorithm,
        "source_hash": result.source_hash,
        "reference_id": reference_id,
        "depth_path": result.depth_path,
    }
    if element is not None:
        data.update({
            "element_id": element.id,
            "role": element.role,
            "bbox": list(element.bbox),
            "depth": element.depth,
            "confidence": element.confidence,
            "mask_path": element.mask_path,
            "parent_element_id": str(element.metadata.get("parent_id") or ""),
            "motion_group_id": str(element.metadata.get("motion_group_id") or ""),
            "rigid": bool(element.metadata.get("rigid")),
            "pivot": list(element.metadata.get("pivot") or []),
            "z_order": int(element.metadata.get("z_order", 0) or 0),
            "motion_lock_to_background": bool(
                element.metadata.get("motion_lock_to_background")
            ),
        })
    else:
        data["role"] = "background"
    return data


def compile_decomposition_layers(
    composition: MotionComposition,
    result: ImageDecompositionResult | Mapping[str, Any],
    *,
    reference_id: str,
    name: str,
    in_ms: int,
    out_ms: int,
    center: tuple[float, float],
    size: tuple[int, int],
    beat_id: str = "",
    motion_style: str = "pop",
    motion_variant: str = "auto",
    prompt: str = "",
    audio_hits_ms: Iterable[int] = (),
) -> list[MotionLayer]:
    """Compile decomposition assets into staggered editable 2.5D layers."""
    normalized = (
        result
        if isinstance(result, ImageDecompositionResult)
        else ImageDecompositionResult.from_dict(result)
    )
    if not normalized.elements:
        return []
    duration = max(1, int(out_ms) - int(in_ms))
    end_time = max(1, duration - 1)
    center_x, center_y = float(center[0]), float(center[1])
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    max_camera_travel_ratio = max(
        0.0,
        min(
            0.12,
            float(normalized.diagnostics.get("max_camera_travel_ratio", 0.04) or 0.04),
        ),
    )
    from .motion_choreography import plan_motion_choreography

    choreography = plan_motion_choreography(
        normalized.elements,
        duration_ms=duration,
        max_camera_travel_ratio=max_camera_travel_ratio,
        requested_variant=motion_variant,
        prompt=prompt,
        motion_style=motion_style,
        audio_hits_ms=tuple(int(value) for value in audio_hits_ms),
    )
    cues_by_id = choreography.by_element_id()
    common_metadata = {
        "ai_beat_id": beat_id,
        "ai_reference_id": reference_id,
    }
    layers: list[MotionLayer] = []

    background = MotionLayer(
        name=f"{name} / Background",
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=normalized.background_path,
            params={"width": width, "height": height, "fit": "contain"},
        ),
        in_ms=int(in_ms),
        out_ms=int(out_ms),
        metadata={
            **common_metadata,
            "image_decomposition": _decomposition_metadata(
                normalized, reference_id=reference_id, element=None,
            ),
            "motion_choreography": choreography.to_dict(),
        },
    )
    background.transform.position.default = [center_x, center_y]
    background_end_position = [
        center_x + width * choreography.camera.end_offset_ratio[0],
        center_y + height * choreography.camera.end_offset_ratio[1],
    ]
    _animated_keyframes(background.transform.position, [
        (0, [center_x, center_y]),
        (end_time, background_end_position),
    ])
    background_end_scale = choreography.camera.end_scale
    _animated_keyframes(background.transform.scale, [
        (0, [1.0, 1.0]),
        (end_time, [background_end_scale, background_end_scale]),
    ])
    layers.append(background)

    visual_elements = [
        item for item in normalized.elements
        if item.role != "text" and item.rgba_path
    ]
    visual_elements.sort(key=lambda item: (
        int(item.metadata.get("z_order", 0) or 0),
        float(item.depth),
        -float(item.area_ratio),
    ))
    layers_by_element_id: dict[str, MotionLayer] = {}
    for element in visual_elements:
        cue = cues_by_id.get(element.id)
        if cue is None:
            continue
        layer = MotionLayer(
            name=f"{name} / {element.label}",
            layer_type="image",
            source=SourceRef(
                kind="image",
                uri=element.rgba_path,
                params={"width": width, "height": height, "fit": "contain"},
            ),
            in_ms=int(in_ms),
            out_ms=int(out_ms),
            metadata={
                **common_metadata,
                "image_decomposition": _decomposition_metadata(
                    normalized, reference_id=reference_id, element=element,
                ),
                "motion_choreography": cue.to_dict(),
            },
        )
        pivot = list(element.metadata.get("pivot") or [
            normalized.width * 0.5,
            normalized.height * 0.5,
        ])
        anchor = [
            max(0.0, min(1.0, float(pivot[0]) / max(1, normalized.width))),
            max(0.0, min(1.0, float(pivot[1]) / max(1, normalized.height))),
        ]
        pivot_position = [
            center_x + (anchor[0] - 0.5) * width,
            center_y + (anchor[1] - 0.5) * height,
        ]
        layer.transform.position.default = list(pivot_position)
        if cue.lock_to_background:
            layer.transform.anchor.default = [0.5, 0.5]
            _animated_keyframes(layer.transform.position, [
                (0, [center_x, center_y]),
                (end_time, list(background_end_position)),
            ])
            _animated_keyframes(layer.transform.scale, [
                (0, [1.0, 1.0]),
                (end_time, [background_end_scale, background_end_scale]),
            ])
            _animated_keyframes(layer.transform.rotation, [
                (0, 0.0),
                (end_time, 0.0),
            ])
            layer.behaviors = []
        elif cue.lock_to_parent:
            layer.transform.anchor.default = anchor
            layer.transform.position.default = [0.0, 0.0]
            _animated_keyframes(layer.transform.position, [
                (0, [0.0, 0.0]),
                (end_time, [0.0, 0.0]),
            ])
            _animated_keyframes(layer.transform.scale, [
                (0, [1.0, 1.0]),
                (end_time, [1.0, 1.0]),
            ])
            _animated_keyframes(layer.transform.rotation, [
                (0, 0.0),
                (end_time, 0.0),
            ])
            layer.behaviors = []
        else:
            layer.transform.anchor.default = anchor
            _animated_keyframes(layer.transform.position, [
                (0, [
                    pivot_position[0] + width * cue.start_offset_ratio[0],
                    pivot_position[1] + height * cue.start_offset_ratio[1],
                ]),
                (end_time, [
                    pivot_position[0] + width * cue.end_offset_ratio[0],
                    pivot_position[1] + height * cue.end_offset_ratio[1],
                ]),
            ])
            _animated_keyframes(layer.transform.scale, [
                (0, [cue.start_scale, cue.start_scale]),
                (end_time, [cue.end_scale, cue.end_scale]),
            ])
            _animated_keyframes(layer.transform.rotation, [
                (0, cue.start_rotation),
                (end_time, cue.end_rotation),
            ])
            if cue.behavior == "pop":
                layer.behaviors = [
                    MotionBehaviorRef(
                        kind="pop",
                        start_ms=cue.start_ms,
                        end_ms=cue.settle_ms,
                        params=dict(cue.behavior_params),
                    ),
                ]
            if cue.fade_in:
                layer.behaviors.insert(0, MotionBehaviorRef(
                    kind="fade",
                    start_ms=cue.start_ms,
                    end_ms=min(end_time, cue.start_ms + 220),
                    params={"direction": "in", "hold_before": True, "hold_after": True},
                ))
        layers.append(layer)
        layers_by_element_id[element.id] = layer

    for element in visual_elements:
        parent_element_id = str(element.metadata.get("parent_id") or "")
        layer = layers_by_element_id.get(element.id)
        parent = layers_by_element_id.get(parent_element_id)
        if layer is not None and parent is not None:
            layer.parent_id = parent.id

    text_elements = [item for item in normalized.elements if item.role == "text" and item.text]
    for index, element in enumerate(text_elements):
        box_x, box_y, box_width, box_height = element.bbox
        text_step = 65 if choreography.variant == "collage" else 85
        delay = min(
            max(0, duration - 240),
            180 + len(visual_elements) * text_step + index * text_step,
        )
        typography_params = dict(element.metadata.get("typography_params") or {
            "text": element.text,
            "font_family": "Segoe UI",
            "font_size": max(14, int(round(box_height * 0.78))),
            "font_weight": 700,
            "fill": "#ffffff",
            "stroke": "#101318cc",
            "stroke_width": 1.0,
            "alignment": "center",
            "width": max(32, box_width),
            "height": max(24, int(round(box_height * 1.35))),
            "line_height": 1.0,
        })
        typography_params["typography_motion"] = {
            "animation_id": "scale_up",
            "selector_mode": "word",
            "stagger_ms": 45,
            "in_duration_ms": min(620, max(160, duration - delay)),
            "out_duration_ms": 0,
            "intensity": 1.15 if choreography.variant == "collage" else 0.9,
        }
        layer = MotionLayer(
            name=f"{name} / {element.label}",
            layer_type="text",
            source=SourceRef(kind="typography", params=typography_params),
            in_ms=int(in_ms),
            out_ms=int(out_ms),
            metadata={
                **common_metadata,
                "image_decomposition": _decomposition_metadata(
                    normalized, reference_id=reference_id, element=element,
                ),
                "motion_choreography_variant": choreography.variant,
            },
        )
        layer.transform.position.default = [
            center_x - width * 0.5 + box_x + box_width * 0.5,
            center_y - height * 0.5 + box_y + box_height * 0.5,
        ]
        layer.behaviors = [
            MotionBehaviorRef(
                kind="fade",
                start_ms=delay,
                end_ms=min(end_time, delay + 180),
                params={"direction": "in", "hold_before": True, "hold_after": True},
            ),
        ]
        layers.append(layer)
    from .image_motion_validation import validate_compiled_image_layers

    compiled_validation = validate_compiled_image_layers(layers)
    background.metadata["image_motion_validation"] = compiled_validation.to_dict()
    return layers


__all__ = [
    "DecomposedImageElement",
    "IMAGE_DECOMPOSITION_ALGORITHM",
    "IMAGE_DECOMPOSITION_SCHEMA",
    "ImageDecompositionResult",
    "compile_decomposition_layers",
    "decompose_image",
]
