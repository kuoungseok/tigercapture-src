"""Programmatic edit helpers for user PPT decks."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from typing import Any

from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec


def _clamp01(value: Any, default: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = float(default)
    return max(0.0, min(1.0, number))


def element_payload(element: SlideElement, *, include_metadata: bool = True) -> dict[str, Any]:
    from app.pptgen.animations import animation_is_active, animation_payload

    payload: dict[str, Any] = {
        "id": element.id,
        "kind": element.kind,
        "name": element.name,
        "x": float(element.x),
        "y": float(element.y),
        "w": float(element.w),
        "h": float(element.h),
        "rotation": float(element.rotation),
        "opacity": float(element.opacity),
        "visible": bool(element.visible),
        "locked": bool(element.locked),
    }
    if element.text:
        payload["text"] = element.text
    if element.source_path:
        payload["source_path"] = element.source_path
    if animation_is_active(element.animation):
        payload["animation"] = animation_payload(element.animation)
    if include_metadata and element.metadata:
        payload["metadata"] = dict(element.metadata)
    return payload


def slide_payload(slide: SlideSpec, *, include_metadata: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": slide.id,
        "title": slide.title,
        "layout_id": slide.layout_id,
        "duration_ms": int(slide.duration_ms),
        "transition": slide.transition,
        "element_count": len(slide.elements),
        "elements": [element_payload(element, include_metadata=include_metadata) for element in slide.elements],
    }
    if include_metadata and slide.metadata:
        payload["metadata"] = dict(slide.metadata)
    return payload


def deck_snapshot(deck: DeckSpec, *, selected_slide_id: str = "", include_metadata: bool = True) -> dict[str, Any]:
    return {
        "schema": "tigercapture.ppt.deck_snapshot.v1",
        "deck_id": deck.id,
        "title": deck.title,
        "slide_count": len(deck.slides),
        "selected_slide_id": selected_slide_id,
        "slides": [slide_payload(slide, include_metadata=include_metadata) for slide in deck.slides],
    }


def find_slide(deck: DeckSpec, slide_id: str = "") -> SlideSpec:
    wanted = str(slide_id or "").strip()
    if wanted:
        slide = deck.slide_by_id(wanted)
        if slide is None:
            raise KeyError(f"slide not found: {wanted}")
        return slide
    if not deck.slides:
        raise KeyError("deck has no slides")
    return deck.slides[0]


def unique_slide_id(deck: DeckSpec, base: str = "slide") -> str:
    existing = {slide.id for slide in deck.slides}
    root = str(base or "slide").strip() or "slide"
    candidate = root
    suffix = 2
    while candidate in existing:
        candidate = f"{root}-{suffix}"
        suffix += 1
    return candidate


def add_deck_slide(
    deck: DeckSpec,
    *,
    title: str = "",
    layout_id: str = "blank",
    duration_ms: int = 5000,
    index: int | None = None,
) -> SlideSpec:
    number = len(deck.slides) + 1
    slide = SlideSpec(
        id=unique_slide_id(deck, f"slide-{number:03d}"),
        title=str(title or f"New Slide {number}"),
        layout_id=str(layout_id or "blank"),
        duration_ms=max(1, int(duration_ms or 5000)),
    )
    if index is None:
        deck.slides.append(slide)
    else:
        deck.slides.insert(max(0, min(len(deck.slides), int(index))), slide)
    return slide


def duplicate_slide(deck: DeckSpec, slide_id: str, *, index: int | None = None) -> SlideSpec:
    source = find_slide(deck, slide_id)
    clone = copy.deepcopy(source)
    clone.id = unique_slide_id(deck, f"{source.id}-copy")
    clone.title = f"{source.title or source.id} Copy"
    old_index = deck.slides.index(source)
    insert_at = old_index + 1 if index is None else max(0, min(len(deck.slides), int(index)))
    deck.slides.insert(insert_at, clone)
    return clone


def delete_slide(deck: DeckSpec, slide_id: str, *, keep_one: bool = True) -> dict[str, Any]:
    slide = find_slide(deck, slide_id)
    if keep_one and len(deck.slides) <= 1:
        raise RuntimeError("cannot delete the only slide")
    index = deck.slides.index(slide)
    payload = slide_payload(slide)
    del deck.slides[index]
    selected = deck.slides[min(index, len(deck.slides) - 1)].id if deck.slides else ""
    return {
        "schema": "tigercapture.ppt.slide_deleted.v1",
        "slide_id": slide.id,
        "deleted": payload,
        "slide_count": len(deck.slides),
        "selected_slide_id": selected,
    }


def move_deck_slide(deck: DeckSpec, slide_id: str, *, index: int) -> SlideSpec:
    slide = find_slide(deck, slide_id)
    old_index = deck.slides.index(slide)
    del deck.slides[old_index]
    deck.slides.insert(max(0, min(len(deck.slides), int(index))), slide)
    return slide


def update_slide(
    deck: DeckSpec,
    slide_id: str,
    *,
    title: str | None = None,
    layout_id: str | None = None,
    duration_ms: int | None = None,
    speaker_notes: str | None = None,
    transition: str | None = None,
    background: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> SlideSpec:
    slide = find_slide(deck, slide_id)
    if title is not None:
        slide.title = str(title)
    if layout_id is not None:
        slide.layout_id = str(layout_id or "blank")
    if duration_ms is not None:
        slide.duration_ms = max(1, int(duration_ms))
    if speaker_notes is not None:
        slide.speaker_notes = str(speaker_notes)
    if transition is not None:
        slide.transition = str(transition or "cut")
    if background is not None:
        slide.background = str(background)
    if isinstance(metadata, Mapping):
        slide.metadata.update(dict(metadata))
    return slide


def find_element(deck: DeckSpec, element_id: str, *, slide_id: str = "") -> tuple[SlideSpec, SlideElement]:
    wanted = str(element_id or "").strip()
    if not wanted:
        raise KeyError("element_id is required")
    slides = [find_slide(deck, slide_id)] if str(slide_id or "").strip() else list(deck.slides)
    for slide in slides:
        for element in slide.elements:
            if element.id == wanted:
                return slide, element
    raise KeyError(f"element not found: {wanted}")


def unique_element_id(slide: SlideSpec, base: str) -> str:
    existing = {element.id for element in slide.elements}
    root = str(base or "element").strip() or "element"
    candidate = root
    suffix = 2
    while candidate in existing:
        candidate = f"{root}-{suffix}"
        suffix += 1
    return candidate


def normalize_element_z_indices(slide: SlideSpec) -> None:
    ordered = sorted(enumerate(slide.elements), key=lambda row: (int(row[1].z_index), row[0]))
    for z_index, (_old_index, element) in enumerate(ordered):
        element.z_index = z_index
    slide.elements = [element for _old_index, element in ordered]


def duplicate_element(
    deck: DeckSpec,
    element_id: str,
    *,
    slide_id: str = "",
    dx: float = 0.03,
    dy: float = 0.03,
) -> tuple[SlideSpec, SlideElement]:
    slide, element = find_element(deck, element_id, slide_id=slide_id)
    if element.locked:
        raise RuntimeError(f"element is locked: {element.id}")
    clone = copy.deepcopy(element)
    clone.id = unique_element_id(slide, f"{element.id}-copy")
    clone.name = f"{element.name or element.kind} Copy"
    clone.x = _clamp01(float(element.x) + float(dx), element.x)
    clone.y = _clamp01(float(element.y) + float(dy), element.y)
    clone.z_index = max((int(row.z_index) for row in slide.elements), default=-1) + 1
    slide.add_element(clone)
    normalize_element_z_indices(slide)
    return slide, clone


def set_element_z_order(
    deck: DeckSpec,
    element_id: str,
    *,
    slide_id: str = "",
    mode: str = "front",
) -> tuple[SlideSpec, SlideElement]:
    slide, element = find_element(deck, element_id, slide_id=slide_id)
    if element.locked:
        raise RuntimeError(f"element is locked: {element.id}")
    ordered = sorted(slide.elements, key=lambda row: int(row.z_index))
    try:
        index = ordered.index(element)
    except ValueError:
        index = 0
    mode_key = str(mode or "front").lower().strip()
    if mode_key in {"front", "bring_front", "to_front"}:
        ordered.append(ordered.pop(index))
    elif mode_key in {"back", "send_back", "to_back"}:
        ordered.insert(0, ordered.pop(index))
    elif mode_key in {"forward", "bring_forward"} and index < len(ordered) - 1:
        ordered[index], ordered[index + 1] = ordered[index + 1], ordered[index]
    elif mode_key in {"backward", "send_backward"} and index > 0:
        ordered[index], ordered[index - 1] = ordered[index - 1], ordered[index]
    else:
        if mode_key not in {"forward", "bring_forward", "backward", "send_backward"}:
            raise ValueError(f"unknown z-order mode: {mode}")
    for z_index, row in enumerate(ordered):
        row.z_index = z_index
    slide.elements = ordered
    return slide, element


def align_element(
    deck: DeckSpec,
    element_id: str,
    *,
    slide_id: str = "",
    horizontal: str = "",
    vertical: str = "",
) -> tuple[SlideSpec, SlideElement]:
    slide, element = find_element(deck, element_id, slide_id=slide_id)
    if element.locked:
        raise RuntimeError(f"element is locked: {element.id}")
    h = str(horizontal or "").lower().strip()
    v = str(vertical or "").lower().strip()
    if h in {"left", "l"}:
        element.x = 0.0
    elif h in {"center", "centre", "middle", "c"}:
        element.x = max(0.0, min(1.0, (1.0 - float(element.w)) / 2.0))
    elif h in {"right", "r"}:
        element.x = max(0.0, 1.0 - float(element.w))
    elif h:
        raise ValueError(f"unknown horizontal alignment: {horizontal}")
    if v in {"top", "t"}:
        element.y = 0.0
    elif v in {"middle", "center", "centre", "m"}:
        element.y = max(0.0, min(1.0, (1.0 - float(element.h)) / 2.0))
    elif v in {"bottom", "b"}:
        element.y = max(0.0, 1.0 - float(element.h))
    elif v:
        raise ValueError(f"unknown vertical alignment: {vertical}")
    return slide, element


def delete_element(deck: DeckSpec, element_id: str, *, slide_id: str = "") -> dict[str, Any]:
    slide, element = find_element(deck, element_id, slide_id=slide_id)
    if element.locked:
        raise RuntimeError(f"element is locked: {element.id}")
    index = slide.elements.index(element)
    deleted = element_payload(element)
    del slide.elements[index]
    return {
        "schema": "tigercapture.ppt.element_deleted.v1",
        "slide_id": slide.id,
        "element_id": element.id,
        "deleted": deleted,
        "element_count": len(slide.elements),
    }


def update_element(
    deck: DeckSpec,
    element_id: str,
    *,
    slide_id: str = "",
    name: str | None = None,
    text: str | None = None,
    x: Any = None,
    y: Any = None,
    w: Any = None,
    h: Any = None,
    rotation: Any = None,
    opacity: Any = None,
    visible: bool | None = None,
    style: Mapping[str, Any] | None = None,
    animation: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[SlideSpec, SlideElement]:
    slide, element = find_element(deck, element_id, slide_id=slide_id)
    if element.locked:
        raise RuntimeError(f"element is locked: {element.id}")
    if name is not None:
        element.name = str(name)
    if text is not None:
        element.text = str(text)
    if x is not None:
        element.x = _clamp01(x, element.x)
    if y is not None:
        element.y = _clamp01(y, element.y)
    if w is not None:
        element.w = _clamp01(w, element.w)
    if h is not None:
        element.h = _clamp01(h, element.h)
    if rotation is not None:
        element.rotation = float(rotation)
    if opacity is not None:
        element.opacity = _clamp01(opacity, element.opacity)
    if visible is not None:
        element.visible = bool(visible)
    if isinstance(style, Mapping):
        allowed = set(element.style.__dataclass_fields__.keys())
        for key, value in style.items():
            if key in allowed:
                setattr(element.style, key, value)
    if isinstance(animation, Mapping):
        from app.pptgen.animations import update_element_animation_from_mapping

        _slide, element = update_element_animation_from_mapping(deck, element_id, animation, slide_id=slide_id)
    if isinstance(metadata, Mapping):
        element.metadata.update(dict(metadata))
    return slide, element


def set_element_animation(
    deck: DeckSpec,
    element_id: str,
    *,
    slide_id: str = "",
    in_animation: Any = None,
    out_animation: Any = None,
    trigger: Any = None,
    start_ms: Any = None,
    duration_ms: Any = None,
    click_index: Any = None,
    easing: Any = None,
    motion_x: Any = None,
    motion_y: Any = None,
    scale: Any = None,
) -> tuple[SlideSpec, SlideElement]:
    from app.pptgen.animations import set_element_animation as _set_element_animation

    return _set_element_animation(
        deck,
        element_id,
        slide_id=slide_id,
        in_animation=in_animation,
        out_animation=out_animation,
        trigger=trigger,
        start_ms=start_ms,
        duration_ms=duration_ms,
        click_index=click_index,
        easing=easing,
        motion_x=motion_x,
        motion_y=motion_y,
        scale=scale,
    )


def set_table_data(
    deck: DeckSpec,
    element_id: str,
    *,
    cells: Sequence[Sequence[Any]],
    slide_id: str = "",
    header: bool | None = None,
) -> tuple[SlideSpec, SlideElement]:
    slide, element = find_element(deck, element_id, slide_id=slide_id)
    if element.kind != "table":
        raise RuntimeError(f"element is not a table: {element.id}")
    normalized = [[str(cell) for cell in row] for row in cells if isinstance(row, Sequence) and not isinstance(row, (str, bytes))]
    if not normalized:
        raise RuntimeError("cells must contain at least one row")
    col_count = max(1, max(len(row) for row in normalized))
    for row in normalized:
        while len(row) < col_count:
            row.append("")
    element.metadata["rows"] = len(normalized)
    element.metadata["cols"] = col_count
    element.metadata["cells"] = normalized
    if header is not None:
        element.metadata["header"] = bool(header)
    return slide, element


def set_chart_data(
    deck: DeckSpec,
    element_id: str,
    *,
    labels: Sequence[Any],
    values: Sequence[Any],
    slide_id: str = "",
    chart_type: str = "bar",
) -> tuple[SlideSpec, SlideElement]:
    slide, element = find_element(deck, element_id, slide_id=slide_id)
    if element.kind != "chart":
        raise RuntimeError(f"element is not a chart: {element.id}")
    normalized_labels = [str(label) for label in labels]
    normalized_values = [str(value) if isinstance(value, str) else float(value) for value in values]
    count = min(len(normalized_labels), len(normalized_values))
    if count <= 0:
        raise RuntimeError("labels and values must contain at least one item")
    element.metadata["labels"] = normalized_labels[:count]
    element.metadata["values"] = normalized_values[:count]
    element.metadata["chart_type"] = chart_type or "bar"
    return slide, element


__all__ = [
    "add_deck_slide",
    "deck_snapshot",
    "delete_element",
    "delete_slide",
    "align_element",
    "duplicate_element",
    "duplicate_slide",
    "element_payload",
    "find_element",
    "find_slide",
    "move_deck_slide",
    "normalize_element_z_indices",
    "set_element_animation",
    "set_chart_data",
    "set_element_z_order",
    "set_table_data",
    "slide_payload",
    "unique_element_id",
    "unique_slide_id",
    "update_element",
    "update_slide",
]
