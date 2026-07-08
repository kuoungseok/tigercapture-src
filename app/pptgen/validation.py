"""Validation for generated user PPT decks."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec


ACTOR_KINDS = {"video_actor", "ar_pbr_actor", "vrm_actor", "mmd_actor", "audio_actor", "media_actor"}
POSTER_KEYS = ("poster_path", "thumbnail_path", "preview_path", "render_path")


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    slide_id: str = ""
    element_id: str = ""


def issue_payload(issue: ValidationIssue) -> dict[str, str]:
    return {
        "severity": issue.severity,
        "code": issue.code,
        "message": issue.message,
        "slide_id": issue.slide_id,
        "element_id": issue.element_id,
    }


def _element_has_visible_content(element: SlideElement) -> bool:
    if not element.visible or element.opacity <= 0.01:
        return False
    if element.kind in {"text", "callout", "typography_actor"}:
        return bool(element.text.strip())
    if element.kind in {
        "image",
        "video",
        "video_actor",
        "audio_actor",
        "ar_pbr_actor",
        "vrm_actor",
        "mmd_actor",
        "ar_pbr_render",
        "actor_render",
        "mmd_render",
        "live2d_render",
        "spine_render",
    }:
        return bool(element.source_path.strip()) or element.kind.endswith("_render")
    if element.kind in {"shape", "table", "chart", "line", "image_placeholder", "node_graph_diagram", "depth_visualization", "waveform", "device_mockup"}:
        return True
    return bool(element.text.strip() or element.source_path.strip() or element.metadata)


def _validate_element(slide: SlideSpec, element: SlideElement) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if element.x + element.w > 1.001 or element.y + element.h > 1.001:
        issues.append(
            ValidationIssue(
                "warning",
                "element_out_of_bounds",
                "Element extends outside the slide safe canvas.",
                slide.id,
                element.id,
            )
        )
    if element.w <= 0.005 or element.h <= 0.005:
        issues.append(ValidationIssue("error", "element_too_small", "Element has no useful size.", slide.id, element.id))
    if element.source_path:
        path = Path(element.source_path)
        if not path.exists():
            issues.append(ValidationIssue("warning", "missing_asset", f"Asset is missing: {path}", slide.id, element.id))
    if element.kind == "text" and element.text:
        # Deliberately rough: catches obviously cramped boxes without needing Qt font metrics.
        capacity = max(12, int(element.w * 80) * max(1, int(element.h * 12)))
        if len(element.text) > capacity:
            issues.append(ValidationIssue("warning", "text_overflow_risk", "Text may overflow its slide box.", slide.id, element.id))
    if element.kind in ACTOR_KINDS:
        poster_values = [str(element.metadata.get(key) or "").strip() for key in POSTER_KEYS]
        poster_paths = [Path(value) for value in poster_values if value]
        if not poster_paths:
            issues.append(ValidationIssue("info", "actor_poster_missing", "Actor has no cached poster yet.", slide.id, element.id))
        elif not any(path.exists() for path in poster_paths):
            issues.append(ValidationIssue("warning", "actor_poster_file_missing", "Actor poster metadata points to a missing file.", slide.id, element.id))
    return issues


def validate_deck(deck: DeckSpec) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not deck.slides:
        return [ValidationIssue("error", "empty_deck", "Deck has no slides.")]
    seen_slide_ids: set[str] = set()
    for slide in deck.slides:
        if slide.id in seen_slide_ids:
            issues.append(ValidationIssue("error", "duplicate_slide_id", f"Duplicate slide id: {slide.id}", slide.id))
        seen_slide_ids.add(slide.id)
        visible = [element for element in slide.elements if _element_has_visible_content(element)]
        if not visible:
            issues.append(ValidationIssue("warning", "empty_slide", "Slide has no visible content.", slide.id))
        seen_element_ids: set[str] = set()
        for element in slide.elements:
            if element.id in seen_element_ids:
                issues.append(ValidationIssue("error", "duplicate_element_id", f"Duplicate element id: {element.id}", slide.id, element.id))
            seen_element_ids.add(element.id)
            issues.extend(_validate_element(slide, element))
    return issues


def validation_report(deck: DeckSpec) -> dict[str, object]:
    issues = validate_deck(deck)
    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")
    infos = sum(1 for issue in issues if issue.severity == "info")
    return {
        "schema": "tigercapture.ppt.validation.v1",
        "ok": errors == 0,
        "issue_count": len(issues),
        "error_count": errors,
        "warning_count": warnings,
        "info_count": infos,
        "issues": [issue_payload(issue) for issue in issues],
    }


__all__ = ["ValidationIssue", "issue_payload", "validate_deck", "validation_report"]
