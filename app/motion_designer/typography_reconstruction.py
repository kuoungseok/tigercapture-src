"""Conservative OCR-to-native-typography reconstruction for Motion Designer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TypographyRegion:
    text: str
    bbox: tuple[int, int, int, int]
    confidence: float
    role: str
    native_eligible: bool
    language: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "bbox": list(self.bbox),
            "confidence": float(self.confidence),
            "role": self.role,
            "native_eligible": bool(self.native_eligible),
            "language": self.language,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class TypographyAnalysis:
    regions: list[TypographyRegion]
    provider: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "regions": [item.to_dict() for item in self.regions],
            "native_region_count": sum(1 for item in self.regions if item.native_eligible),
            "raster_region_count": sum(1 for item in self.regions if not item.native_eligible),
            "warnings": list(self.warnings),
        }


def _role_for_region(
    bbox: tuple[int, int, int, int],
    *,
    canvas_width: int,
    canvas_height: int,
) -> str:
    x, y, width, height = bbox
    del x
    height_ratio = float(height) / float(max(1, canvas_height))
    width_ratio = float(width) / float(max(1, canvas_width))
    center_y = float(y + height * 0.5) / float(max(1, canvas_height))
    if height_ratio >= 0.07 or width_ratio >= 0.42:
        return "headline"
    if center_y >= 0.72:
        return "cta"
    return "body"


def analyze_typography(
    rgb,
    *,
    minimum_confidence: float = 0.45,
    native_threshold: float = 0.78,
) -> TypographyAnalysis:
    try:
        import pytesseract
        from pytesseract import Output
    except Exception:
        return TypographyAnalysis(
            regions=[],
            provider="unavailable",
            warnings=["Local OCR is unavailable; raster text remains inside image layers."],
        )
    try:
        data = pytesseract.image_to_data(rgb, output_type=Output.DICT)
    except Exception as exc:
        return TypographyAnalysis(
            regions=[],
            provider="unavailable",
            warnings=[f"Local OCR failed; raster text was preserved: {exc}"],
        )

    grouped: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
    count = len(data.get("text") or [])
    for index in range(count):
        text = str(data["text"][index] or "").strip()
        try:
            confidence = float(data["conf"][index]) / 100.0
        except (TypeError, ValueError):
            confidence = -1.0
        width = int(data["width"][index])
        height = int(data["height"][index])
        if not text or confidence < minimum_confidence or width < 4 or height < 4:
            continue
        key = (
            int((data.get("block_num") or [0] * count)[index]),
            int((data.get("par_num") or [0] * count)[index]),
            int((data.get("line_num") or [index] * count)[index]),
        )
        grouped.setdefault(key, []).append({
            "text": text,
            "confidence": confidence,
            "left": int(data["left"][index]),
            "top": int(data["top"][index]),
            "width": width,
            "height": height,
        })

    canvas_height, canvas_width = rgb.shape[:2]
    regions: list[TypographyRegion] = []
    for words in grouped.values():
        words.sort(key=lambda item: (item["left"], item["top"]))
        x0 = min(item["left"] for item in words)
        y0 = min(item["top"] for item in words)
        x1 = max(item["left"] + item["width"] for item in words)
        y1 = max(item["top"] + item["height"] for item in words)
        confidence = sum(
            float(item["confidence"]) * max(1, len(item["text"]))
            for item in words
        ) / float(sum(max(1, len(item["text"])) for item in words))
        bbox = (x0, y0, max(1, x1 - x0), max(1, y1 - y0))
        regions.append(TypographyRegion(
            text=" ".join(item["text"] for item in words),
            bbox=bbox,
            confidence=confidence,
            role=_role_for_region(
                bbox,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
            ),
            native_eligible=confidence >= native_threshold,
            metadata={"word_count": len(words), "provider": "pytesseract"},
        ))
    regions.sort(key=lambda item: (item.bbox[1], item.bbox[0]))
    warnings: list[str] = []
    raster_count = sum(1 for item in regions if not item.native_eligible)
    if raster_count:
        warnings.append(
            f"{raster_count} OCR region(s) stayed raster because confidence was below the native-text threshold."
        )
    return TypographyAnalysis(regions=regions, provider="pytesseract", warnings=warnings)


def native_typography_mask(
    width: int,
    height: int,
    regions: list[TypographyRegion],
):
    import cv2
    import numpy as np

    mask = np.zeros((height, width), dtype=np.uint8)
    for region in regions:
        if not region.native_eligible:
            continue
        x, y, box_width, box_height = region.bbox
        margin = max(1, int(round(box_height * 0.16)))
        cv2.rectangle(
            mask,
            (max(0, x - margin), max(0, y - margin)),
            (
                min(width - 1, x + box_width + margin),
                min(height - 1, y + box_height + margin),
            ),
            255,
            thickness=-1,
        )
    return mask


def typography_source_params(region: TypographyRegion) -> dict[str, Any]:
    _, _, width, height = region.bbox
    weight = 800 if region.role == "headline" else 700 if region.role == "cta" else 500
    return {
        "text": region.text,
        "font_family": "Segoe UI",
        "font_size": max(14, int(round(height * 0.78))),
        "font_weight": weight,
        "fill": "#ffffff",
        "stroke": "#101318cc",
        "stroke_width": 1.0,
        "alignment": "center",
        "width": max(32, width),
        "height": max(24, int(round(height * 1.35))),
        "line_height": 1.0,
    }


__all__ = [
    "TypographyAnalysis",
    "TypographyRegion",
    "analyze_typography",
    "native_typography_mask",
    "typography_source_params",
]
