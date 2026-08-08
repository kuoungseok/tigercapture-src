"""Adapters between existing Tiger Studio typography/PPT models and MotionLayer."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from .ppt_animation_bridge import animation_from_motion_layer, behavior_from_ppt_animation
from .schema import MotionLayer, SourceRef


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(vars(value)) if hasattr(value, "__dict__") else {}


def layer_from_typography(payload: Any, *, width: int, height: int) -> MotionLayer:
    data = _mapping(payload)
    style = _mapping(data.get("style") or getattr(payload, "style", None))
    animation = _mapping(data.get("animation") or getattr(payload, "animation", None))
    text = str(data.get("text") or getattr(payload, "text", "") or "Title")
    start_ms = int(data.get("start_ms", getattr(payload, "start_ms", 0)) or 0)
    end_ms = int(data.get("end_ms", getattr(payload, "end_ms", 2000)) or 2000)
    params = {
        "text": text, "font_family": style.get("font_family", "Noto Sans KR"),
        "font_size": int(style.get("font_size", 72) or 72),
        "font_weight": int(style.get("font_weight", 700) or 700),
        "fill": str(style.get("color") or "#ffffff"),
        "alignment": str(style.get("alignment") or "center"),
        "letter_spacing": max(0.0, float(style.get("letter_spacing", 0.0) or 0.0)),
        "line_height": float(style.get("line_height", 1.2) or 1.2),
        "stroke": str(style.get("outline_color") or "#000000"),
        "stroke_width": float(style.get("outline_width", 0.0) or 0.0),
        "shadow_color": str(style.get("shadow_color") or "transparent"),
        "shadow_offset_x": float(style.get("shadow_offset_x", 0.0) or 0.0),
        "shadow_offset_y": float(style.get("shadow_offset_y", 0.0) or 0.0),
        "background_color": str(style.get("background_color") or "transparent"),
        "background_radius": float(style.get("background_radius", 0.0) or 0.0),
        "text_animation": {
            "in": str(animation.get("in_animation") or "none"),
            "hold": str(animation.get("hold_animation") or "none"),
            "out": str(animation.get("out_animation") or "none"),
            "in_duration_ms": max(0, int(float(animation.get("in_duration", .5) or 0.0) * 1000.0)),
            "out_duration_ms": max(0, int(float(animation.get("out_duration", .5) or 0.0) * 1000.0)),
            "unit": str(_mapping(animation.get("custom_params")).get("unit") or "character"),
            "stagger_ms": max(0, int(_mapping(animation.get("custom_params")).get("stagger_ms", 35) or 0)),
            "selector_start": 0.0, "selector_end": 1.0,
            "intensity": max(0.0, float(animation.get("in_intensity", 100.0) or 0.0) / 100.0),
        },
    }
    layer = MotionLayer(name=text[:32] or "Typography", layer_type="text", source=SourceRef(
        kind="typography", params=params, metadata={"bridge": "typography"}), in_ms=0,
        out_ms=max(1, end_ms - start_ms), source_in_ms=start_ms,
        metadata={"typography_clip_id": str(data.get("id", getattr(payload, "id", "")) or "")},
    )
    layer.transform.position.default = [
        float(style.get("position_x", .5) or .5) * width,
        float(style.get("position_y", .5) or .5) * height,
    ]
    layer.transform.rotation.default = float(style.get("rotation", 0.0) or 0.0)
    return layer


def layer_from_ppt_element(payload: Any, *, width: int, height: int, duration_ms: int) -> MotionLayer:
    from app.pptgen.schema import SlideElement

    element = payload if isinstance(payload, SlideElement) else SlideElement.from_dict(dict(payload))
    kind = str(element.kind or "shape")
    if kind in {"text", "typography_actor", "callout"}:
        layer_type = "text"
        source = SourceRef(kind="ppt_text", params={
            "text": element.text, "width": max(1, int(element.w * width)),
            "height": max(1, int(element.h * height)), "font_family": element.style.font_family,
            "font_size": element.style.font_size, "font_weight": 700 if element.style.bold else 400,
            "italic": element.style.italic, "underline": element.style.underline,
            "fill": element.style.color, "alignment": element.style.align,
            "line_height": element.style.line_height,
            "letter_spacing": max(0.0, element.style.letter_spacing),
        })
    elif kind in {"image", "video_actor"} and element.source_path:
        layer_type = "image"
        source = SourceRef(kind="ppt_media", uri=element.source_path, params={
            "width": max(1, int(element.w * width)), "height": max(1, int(element.h * height)),
        })
    else:
        layer_type = "line" if kind == "line" else "shape"
        source = SourceRef(kind="ppt_shape", params={
            "width": max(1, int(element.w * width)), "height": max(1, int(element.h * height)),
            "fill": element.style.fill or "transparent", "stroke": element.style.stroke or element.style.color,
            "stroke_width": element.style.stroke_width, "radius": element.style.radius,
        })
    layer = MotionLayer(name=element.name or kind.title(), layer_type=layer_type, source=source,
                        out_ms=max(1, int(duration_ms)), visible=element.visible, locked=element.locked,
                        metadata={"ppt_element_id": element.id, "ppt_kind": element.kind,
                                  "ppt_element_metadata": dict(element.metadata)})
    layer.transform.position.default = [(element.x + element.w * .5) * width, (element.y + element.h * .5) * height]
    layer.transform.rotation.default = element.rotation
    layer.transform.opacity.default = element.opacity
    behavior, animation_payload = behavior_from_ppt_animation(element.animation, width=width, height=height)
    layer.metadata["ppt_animation"] = animation_payload
    if behavior is not None:
        layer.behaviors.append(behavior)
    return layer


def ppt_element_from_layer(layer: MotionLayer, *, width: int, height: int) -> tuple[dict[str, Any], list[str]]:
    from app.pptgen.schema import ElementStyle, SlideElement

    params = layer.source.params
    source_width = max(1.0, float(params.get("width", 400.0)))
    source_height = max(1.0, float(params.get("height", 220.0)))
    position = layer.transform.position.default
    x = max(0.0, min(1.0, (float(position[0]) - source_width * .5) / max(1, width)))
    y = max(0.0, min(1.0, (float(position[1]) - source_height * .5) / max(1, height)))
    w, h = min(1.0, source_width / max(1, width)), min(1.0, source_height / max(1, height))
    style = ElementStyle(
        fill=params.get("fill"), stroke=params.get("stroke"),
        stroke_width=float(params.get("stroke_width", 0.0) or 0.0),
        color=str(params.get("fill") or "#182033"), font_family=str(params.get("font_family") or "Noto Sans KR"),
        font_size=int(params.get("font_size", 34) or 34),
        bold=int(params.get("font_weight", 400) or 400) >= 600,
        italic=bool(params.get("italic", False)), underline=bool(params.get("underline", False)),
        align=str(params.get("alignment") or "left"), line_height=float(params.get("line_height", 1.2) or 1.2),
        letter_spacing=max(0.0, float(params.get("letter_spacing", 0.0) or 0.0)),
        radius=float(params.get("radius", 0.0) or 0.0),
    )
    if layer.layer_type == "text":
        kind, text, source_path = "text", str(params.get("text") or layer.name), ""
    elif layer.layer_type == "image":
        kind, text, source_path = "image", "", layer.source.uri
    else:
        kind, text, source_path = "line" if layer.layer_type == "line" else "shape", "", ""
    animation, motion_warnings = animation_from_motion_layer(layer, width=width, height=height)
    element = SlideElement(id=str(layer.metadata.get("ppt_element_id") or layer.id), kind=kind, name=layer.name,
                           x=x, y=y, w=w, h=h, rotation=float(layer.transform.rotation.default),
                           opacity=float(layer.transform.opacity.default), text=text, source_path=source_path,
                           visible=layer.visible, locked=layer.locked, style=style, animation=animation,
                           metadata=dict(layer.metadata.get("ppt_element_metadata") or {}))
    warnings: list[str] = list(motion_warnings)
    if layer.effects:
        warnings.append("layer effects require bake for native PPT export")
    if layer.masks:
        warnings.append("layer masks require bake for native PPT export")
    if any(prop.keyframes for prop in layer.transform.properties().values()):
        warnings.append("complex motion requires video bake for PPT export")
    text_animation = params.get("text_animation")
    if isinstance(text_animation, Mapping) and any(
        str(text_animation.get(key) or "none") != "none" for key in ("in", "hold", "out")
    ):
        warnings.append("per-glyph typography animation requires video bake for PPT export")
    if params.get("text_path"):
        warnings.append("text-on-path requires video bake for PPT export")
    if params.get("font_axes"):
        warnings.append("variable font axes may require font substitution or bake for PPT export")
    if layer.parent_id or layer.blend_mode != "normal":
        warnings.append("hierarchy or blend mode requires bake for PPT export")
    return element.to_dict() if hasattr(element, "to_dict") else asdict(element), warnings
