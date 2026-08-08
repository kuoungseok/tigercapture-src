"""Local object-box proposals for editable Motion image decomposition.

The module never downloads a model. A user-installed Ultralytics-compatible
checkpoint provides semantic labels when available; the packaged fallback
returns unlabeled foreground regions that remain reviewable before Apply.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Iterable, Sequence


OBJECT_DETECTION_SCHEMA = "tigerstudio.motion.object_detection.v1"
OBJECT_DETECTOR_MODEL_ENV = "TIGERSTUDIO_OBJECT_DETECTOR_MODEL"


@dataclass(frozen=True, slots=True)
class DetectedObject:
    id: str
    label: str
    bbox: tuple[float, float, float, float]
    confidence: float
    provider: str
    semantic: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_hint(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "bbox": list(self.bbox),
            "confidence": float(self.confidence),
            "provider": self.provider,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.to_hint(),
            "semantic": bool(self.semantic),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ObjectDetectionResult:
    objects: list[DetectedObject]
    provider: str
    semantic: bool
    warnings: list[str] = field(default_factory=list)
    schema: str = OBJECT_DETECTION_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "provider": self.provider,
            "semantic": bool(self.semantic),
            "object_count": len(self.objects),
            "objects": [item.to_dict() for item in self.objects],
            "warnings": list(self.warnings),
        }


def _module_available(name: str) -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def object_detection_capabilities(
    model_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    configured = Path(
        str(model_path or os.environ.get(OBJECT_DETECTOR_MODEL_ENV) or "")
    ).expanduser()
    local_model = bool(str(configured)) and configured.is_file()
    return {
        "ultralytics_local": {
            "available": bool(local_model and _module_available("ultralytics")),
            "semantic_labels": True,
            "model_path": str(configured) if local_model else "",
            "downloads_models": False,
        },
        "opencv_foreground_regions": {
            "available": _module_available("cv2"),
            "semantic_labels": False,
            "downloads_models": False,
        },
    }


def _normalized_bbox(
    bbox: Sequence[float],
    width: int,
    height: int,
    *,
    padding: float = 0.025,
) -> tuple[float, float, float, float]:
    x, y, box_width, box_height = [float(item) for item in bbox[:4]]
    pad_x = width * max(0.0, float(padding))
    pad_y = height * max(0.0, float(padding))
    left = max(0.0, x - pad_x)
    top = max(0.0, y - pad_y)
    right = min(float(width), x + box_width + pad_x)
    bottom = min(float(height), y + box_height + pad_y)
    return (
        left / max(1.0, float(width)),
        top / max(1.0, float(height)),
        max(2.0, right - left) / max(1.0, float(width)),
        max(2.0, bottom - top) / max(1.0, float(height)),
    )


def _ultralytics_objects(
    rgb,
    *,
    model_path: Path,
    max_objects: int,
    label_filter: set[str],
) -> list[DetectedObject]:
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    prediction = model.predict(
        source=rgb,
        verbose=False,
        conf=0.2,
        max_det=max(1, int(max_objects)),
    )
    if not prediction:
        return []
    result = prediction[0]
    names = getattr(result, "names", {}) or {}
    height, width = rgb.shape[:2]
    objects: list[DetectedObject] = []
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return objects
    for index, box in enumerate(boxes):
        coords = box.xyxy[0].tolist()
        left, top, right, bottom = [float(value) for value in coords[:4]]
        class_id = int(float(box.cls[0]))
        label = str(names.get(class_id, f"class_{class_id}"))
        if label_filter and label.casefold() not in label_filter:
            continue
        confidence = float(box.conf[0])
        objects.append(DetectedObject(
            id=f"{label}_{index + 1:02d}",
            label=label,
            bbox=_normalized_bbox(
                (left, top, right - left, bottom - top),
                width,
                height,
            ),
            confidence=max(0.0, min(1.0, confidence)),
            provider="ultralytics_local",
            semantic=True,
            metadata={"class_id": class_id},
        ))
    return objects[:max_objects]


def _foreground_objects(
    rgb,
    alpha,
    *,
    max_objects: int,
    requested_labels: Sequence[str],
) -> list[DetectedObject]:
    from .semantic_segmentation import segment_image

    result = segment_image(
        rgb,
        alpha,
        mode="basic",
        max_elements=max_objects,
    )
    height, width = rgb.shape[:2]
    objects: list[DetectedObject] = []
    for index, candidate in enumerate(result.candidates[:max_objects]):
        requested = (
            str(requested_labels[index]).strip()
            if index < len(requested_labels)
            else ""
        )
        label = f"object_{index + 1:02d}"
        objects.append(DetectedObject(
            id=f"detected_{index + 1:02d}",
            label=label,
            bbox=_normalized_bbox(candidate.bbox, width, height),
            confidence=float(candidate.confidence),
            provider="opencv_foreground_regions",
            semantic=False,
            metadata={
                "source_provider": result.provider,
                "requested_label": requested,
            },
        ))
    return objects


def detect_image_objects(
    rgb,
    alpha,
    *,
    max_objects: int = 8,
    requested_labels: Iterable[str] = (),
    model_path: str | Path | None = None,
) -> ObjectDetectionResult:
    """Return reviewable normalized object boxes for one fitted RGB canvas."""
    max_objects = max(1, min(24, int(max_objects)))
    labels = [
        str(item).strip()
        for item in requested_labels
        if str(item).strip()
    ]
    configured = Path(
        str(model_path or os.environ.get(OBJECT_DETECTOR_MODEL_ENV) or "")
    ).expanduser()
    warnings: list[str] = []
    if bool(str(configured)) and configured.is_file() and _module_available("ultralytics"):
        try:
            objects = _ultralytics_objects(
                rgb,
                model_path=configured,
                max_objects=max_objects,
                label_filter={item.casefold() for item in labels},
            )
            if objects:
                return ObjectDetectionResult(
                    objects=objects,
                    provider="ultralytics_local",
                    semantic=True,
                )
            warnings.append("The configured detector returned no matching objects.")
        except Exception as exc:
            warnings.append(f"Local semantic detector failed: {exc}")
    elif bool(str(configured)) and configured.is_file():
        warnings.append(
            "A detector model is configured but the optional ultralytics package is unavailable."
        )
    else:
        warnings.append(
            "No local semantic detector model is configured; unlabeled foreground regions were proposed."
        )

    objects = _foreground_objects(
        rgb,
        alpha,
        max_objects=max_objects,
        requested_labels=labels,
    )
    return ObjectDetectionResult(
        objects=objects,
        provider="opencv_foreground_regions",
        semantic=False,
        warnings=warnings,
    )


__all__ = [
    "OBJECT_DETECTION_SCHEMA",
    "OBJECT_DETECTOR_MODEL_ENV",
    "DetectedObject",
    "ObjectDetectionResult",
    "detect_image_objects",
    "object_detection_capabilities",
]
