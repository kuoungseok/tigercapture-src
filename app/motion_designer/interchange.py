"""Truthful limited Motion interchange exporters with loss preflight."""
from __future__ import annotations

import json
import shutil
from html import escape
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

from .evaluator import evaluate_composition
from .keyframes import evaluate_property
from .schema import AnimatedProperty, MotionComposition, MotionLayer
from .vector_shapes import VectorPath, path_from_params


INTERCHANGE_SCHEMA = "tigercapture.motion.interchange.v1"
INTERCHANGE_FORMATS = {
    "lottie": "Lottie JSON (shape/text/transform subset)",
    "svg": "SVG still (shape/text subset)",
    "gltf_subscene": "glTF/GLB single AR/PBR source passthrough",
    "otio_timing": "OTIO media/timing references",
}


def list_interchange_formats() -> list[dict[str, str]]:
    return [{"id": key, "label": label} for key, label in INTERCHANGE_FORMATS.items()]


def _animated_source(value: Any) -> bool:
    return isinstance(value, Mapping) and bool(value.get("keyframes"))


def _source_value(params: Mapping[str, Any], key: str, default: Any, time_ms: float = 0.0) -> Any:
    if key not in params:
        return default
    return evaluate_property(AnimatedProperty.from_dict(params.get(key)), time_ms)


def _procedural_reasons(layer: MotionLayer) -> list[str]:
    reasons: list[str] = []
    if layer.behaviors:
        reasons.append("behaviors")
    if layer.metadata.get("expressions"):
        reasons.append("expressions")
    if layer.metadata.get("audio_reactive_bindings"):
        reasons.append("audio reactive bindings")
    return reasons


def preflight_interchange(composition: MotionComposition, format_id: str, *, time_ms: float = 0.0) -> dict[str, Any]:
    identifier = str(format_id)
    if identifier not in INTERCHANGE_FORMATS:
        raise ValueError(f"Unknown Motion interchange format: {identifier}")
    blockers: list[dict[str, str]] = []
    bake_required: list[dict[str, str]] = []
    warnings: list[str] = []
    supported: list[str] = []
    if identifier == "lottie":
        active = [
            layer for layer in composition.layers
            if layer.visible and layer.out_ms > max(0, layer.in_ms)
            and layer.in_ms < composition.duration_ms
        ]
    else:
        active = [layer for layer in composition.layers if layer.visible and layer.in_ms <= time_ms < layer.out_ms]
    if identifier in {"lottie", "svg"}:
        for layer in active:
            if layer.layer_type in {"group", "null", "camera", "light"}:
                continue
            if layer.layer_type not in {"shape", "text"}:
                blockers.append({
                    "layer_id": layer.id, "reason": f"{layer.layer_type} is outside the {identifier} 2D subset",
                })
                continue
            if layer.effects or layer.masks or layer.blend_mode != "normal":
                blockers.append({
                    "layer_id": layer.id,
                    "reason": "effects, masks, and non-normal blend modes are not represented by this exporter",
                })
                continue
            if identifier == "lottie":
                procedural = _procedural_reasons(layer)
                if procedural:
                    bake_required.append({"layer_id": layer.id, "reason": ", ".join(procedural)})
                params = layer.source.params
                unsupported_params = (
                    ("trim", "vector trim"), ("repeater", "vector repeater"),
                    ("boolean", "vector boolean"), ("text_path", "text path"),
                )
                for key, label in unsupported_params:
                    if params.get(key):
                        bake_required.append({"layer_id": layer.id, "reason": label})
                if layer.layer_type == "text":
                    animation = params.get("text_animation")
                    if isinstance(animation, Mapping) and any(
                        str(animation.get(phase) or "none") != "none" for phase in ("in", "hold", "out")
                    ):
                        bake_required.append({"layer_id": layer.id, "reason": "typography selector animation"})
                for key in ("path", "fill", "stroke", "stroke_width", "text", "font_size"):
                    if _animated_source(params.get(key)):
                        bake_required.append({"layer_id": layer.id, "reason": f"animated source parameter {key}"})
            else:
                params = layer.source.params
                unsupported_params = (
                    ("trim", "Trim Paths"),
                    ("offset_path", "Offset Paths"),
                    ("repeater", "Repeater"),
                    ("boolean", "Merge Paths"),
                    ("gradient", "gradient fill"),
                    ("stroke_gradient", "gradient stroke"),
                    ("stroke_taper", "Variable-width/tapered strokes"),
                    ("text_path", "text on path"),
                    ("text_animation", "legacy typography animation"),
                    ("text_animators", "Text Animator stacks"),
                    ("font_axes", "variable font axes"),
                )
                for key, label in unsupported_params:
                    if params.get(key):
                        bake_required.append({
                            "layer_id": layer.id,
                            "reason": f"Feature '{label}' is outside the editable SVG still subset.",
                        })
            supported.append(layer.id)
    elif identifier == "gltf_subscene":
        sources = [layer for layer in active if layer.layer_type == "ar_pbr" and layer.source.uri]
        others = [layer for layer in active if layer.layer_type not in {"ar_pbr", "camera", "light", "group", "null"}]
        if len(sources) != 1:
            blockers.append({"layer_id": "", "reason": "glTF passthrough requires exactly one active AR/PBR source"})
        elif Path(sources[0].source.uri).suffix.lower() not in {".gltf", ".glb"}:
            blockers.append({"layer_id": sources[0].id, "reason": "source must already be .gltf or .glb"})
        elif not Path(sources[0].source.uri).is_file():
            blockers.append({"layer_id": sources[0].id, "reason": "source glTF/GLB file is missing"})
        else:
            supported.append(sources[0].id)
            warnings.append("Motion camera, light, material override, and screen placement are intentionally not embedded")
        for layer in others:
            blockers.append({"layer_id": layer.id, "reason": "non-3D layers cannot be embedded in glTF passthrough"})
    else:
        media_layers = [layer for layer in composition.layers if layer.source.uri]
        supported.extend(layer.id for layer in media_layers)
        omitted = len(composition.layers) - len(media_layers)
        if omitted:
            warnings.append(f"{omitted} generated layer(s) have no external media reference and are omitted by OTIO")
        if not media_layers:
            blockers.append({"layer_id": "", "reason": "OTIO timing export requires at least one media-backed layer"})
    deduplicated_bake = list({(row["layer_id"], row["reason"]): row for row in bake_required}.values())
    return {
        "schema": INTERCHANGE_SCHEMA,
        "format_id": identifier,
        "label": INTERCHANGE_FORMATS[identifier],
        "ok": not blockers and not deduplicated_bake,
        "supported_layer_ids": supported,
        "blockers": blockers,
        "bake_required": deduplicated_bake,
        "warnings": warnings,
        "scope": "limited",
    }


def _value(prop: AnimatedProperty, multiplier: float = 1.0):
    def convert(value: Any):
        if isinstance(value, (list, tuple)):
            return [float(item) * multiplier for item in value]
        return float(value) * multiplier

    if not prop.keyframes:
        return {"a": 0, "k": convert(prop.default)}
    rows = []
    for keyframe in prop.keyframes:
        value = convert(keyframe.value)
        row: dict[str, Any] = {"t": keyframe.time_ms, "s": value if isinstance(value, list) else [value]}
        if keyframe.interpolation == "hold":
            row["h"] = 1
        rows.append(row)
    return {"a": 1, "k": rows}


def _hex_rgba(value: Any) -> tuple[float, float, float, float]:
    text = str(value or "#ffffff").lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text) + "ff"
    elif len(text) == 6:
        text += "ff"
    if len(text) != 8:
        text = "ffffffff"
    try:
        channels = tuple(int(text[index:index + 2], 16) / 255.0 for index in range(0, 8, 2))
    except ValueError:
        channels = (1.0, 1.0, 1.0, 1.0)
    return channels  # type: ignore[return-value]


def _lottie_transform(layer: MotionLayer, fps: float) -> dict[str, Any]:
    def frames(prop: AnimatedProperty, multiplier: float = 1.0):
        data = _value(prop, multiplier)
        if data["a"]:
            for row in data["k"]:
                row["t"] = float(row["t"]) * fps / 1000.0
        return data

    width = float(_source_value(layer.source.params, "width", 0.0) or 0.0)
    height = float(_source_value(layer.source.params, "height", 0.0) or 0.0)
    anchor = frames(layer.transform.anchor)
    if anchor["a"]:
        for row in anchor["k"]:
            row["s"] = [float(row["s"][0]) * width, float(row["s"][1]) * height]
    else:
        anchor["k"] = [float(anchor["k"][0]) * width, float(anchor["k"][1]) * height]
    return {
        "o": frames(layer.transform.opacity, 100.0),
        "r": frames(layer.transform.rotation),
        "p": frames(layer.transform.position),
        "a": anchor,
        "s": frames(layer.transform.scale, 100.0),
    }


def _lottie_path(path: VectorPath) -> dict[str, Any]:
    return {
        "i": [list(point.in_tangent) for point in path.points],
        "o": [list(point.out_tangent) for point in path.points],
        "v": [list(point.position) for point in path.points],
        "c": bool(path.closed),
    }


def lottie_document(composition: MotionComposition) -> dict[str, Any]:
    report = preflight_interchange(composition, "lottie", time_ms=0.0)
    if not report["ok"]:
        raise ValueError("Lottie preflight failed")
    layers: list[dict[str, Any]] = []
    fonts: dict[str, dict[str, str]] = {}
    export_layers = [layer for layer in composition.layers if layer.id in report["supported_layer_ids"]]
    index_by_id = {layer.id: index for index, layer in enumerate(export_layers, start=1)}
    for layer in export_layers:
        index = index_by_id[layer.id]
        row: dict[str, Any] = {
            "ddd": 0, "ind": index, "nm": layer.name,
            "ip": layer.in_ms * composition.fps / 1000.0,
            "op": layer.out_ms * composition.fps / 1000.0,
            "st": 0, "ks": _lottie_transform(layer, composition.fps),
        }
        if layer.parent_id in index_by_id:
            row["parent"] = index_by_id[layer.parent_id]
        params = layer.source.params
        if layer.layer_type == "shape":
            fill = _hex_rgba(_source_value(params, "fill", "#ffffff"))
            stroke = _hex_rgba(_source_value(params, "stroke", "#00000000"))
            stroke_width = float(_source_value(params, "stroke_width", 0.0))
            shapes: list[dict[str, Any]] = [{"ty": "sh", "nm": layer.name, "ks": {"a": 0, "k": _lottie_path(path_from_params(params))}}]
            if fill[3] > 0:
                shapes.append({"ty": "fl", "c": {"a": 0, "k": list(fill[:3])}, "o": {"a": 0, "k": fill[3] * 100.0}})
            if stroke_width > 0 and stroke[3] > 0:
                shapes.append({"ty": "st", "c": {"a": 0, "k": list(stroke[:3])}, "o": {"a": 0, "k": stroke[3] * 100.0}, "w": {"a": 0, "k": stroke_width}})
            row.update({"ty": 4, "shapes": shapes})
        else:
            family = str(_source_value(params, "font_family", "Segoe UI") or "Segoe UI")
            font_name = family.replace(" ", "_")
            fonts[font_name] = {"fName": font_name, "fFamily": family, "fStyle": "Regular"}
            fill = _hex_rgba(_source_value(params, "fill", "#ffffff"))
            row.update({
                "ty": 5,
                "t": {"d": {"k": [{"t": 0, "s": {
                    "t": str(_source_value(params, "text", "") or ""), "f": font_name,
                    "s": float(_source_value(params, "font_size", 72.0) or 72.0), "fc": list(fill[:3]),
                }}]}},
            })
        layers.append(row)
    return {
        "v": "5.12.2", "fr": composition.fps, "ip": 0,
        "op": composition.duration_ms * composition.fps / 1000.0,
        "w": composition.width, "h": composition.height, "nm": composition.name,
        "ddd": 0, "assets": [], "fonts": {"list": list(fonts.values())}, "layers": layers,
        "meta": {"g": "Tiger Studio Motion Designer", "tc": {"scope": "limited", "schema": INTERCHANGE_SCHEMA}},
    }


def _svg_path(path: VectorPath) -> str:
    if not path.points:
        return ""
    commands = [f"M {path.points[0].position[0]:.4f} {path.points[0].position[1]:.4f}"]
    segment_count = len(path.points) if path.closed else len(path.points) - 1
    for index in range(segment_count):
        start = path.points[index]
        end = path.points[(index + 1) % len(path.points)]
        c1 = (start.position[0] + start.out_tangent[0], start.position[1] + start.out_tangent[1])
        c2 = (end.position[0] + end.in_tangent[0], end.position[1] + end.in_tangent[1])
        commands.append(f"C {c1[0]:.4f} {c1[1]:.4f} {c2[0]:.4f} {c2[1]:.4f} {end.position[0]:.4f} {end.position[1]:.4f}")
    if path.closed:
        commands.append("Z")
    return " ".join(commands)


def svg_document(composition: MotionComposition, *, time_ms: float = 0.0) -> str:
    report = preflight_interchange(composition, "svg", time_ms=time_ms)
    if not report["ok"]:
        raise ValueError("SVG preflight failed")
    states = {state.id: state for state in evaluate_composition(composition, time_ms)}
    body: list[str] = []
    for layer in composition.layers:
        if layer.id not in report["supported_layer_ids"]:
            continue
        state = states[layer.id]
        a, b, c, d, tx, ty = state.matrix
        params = layer.source.params
        width = float(_source_value(params, "width", 400.0, state.local_time_ms) or 400.0)
        height = float(_source_value(params, "height", 220.0, state.local_time_ms) or 220.0)
        offset_x = -width * float(state.anchor[0])
        offset_y = -height * float(state.anchor[1])
        transform = f"matrix({a:.8g} {b:.8g} {c:.8g} {d:.8g} {tx:.8g} {ty:.8g}) translate({offset_x:.8g} {offset_y:.8g})"
        opacity = max(0.0, min(1.0, float(state.opacity)))
        if layer.layer_type == "shape":
            fill = escape(str(_source_value(params, "fill", "#ffffff", state.local_time_ms)))
            stroke = escape(str(_source_value(params, "stroke", "none", state.local_time_ms)))
            stroke_width = float(_source_value(params, "stroke_width", 0.0, state.local_time_ms))
            body.append(f'<path id="{escape(layer.id)}" d="{_svg_path(path_from_params(params, state.local_time_ms))}" transform="{transform}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width:.8g}" opacity="{opacity:.8g}"/>')
        else:
            text = escape(str(_source_value(params, "text", "", state.local_time_ms) or ""))
            family = escape(str(_source_value(params, "font_family", "Segoe UI", state.local_time_ms) or "Segoe UI"), quote=True)
            size = float(_source_value(params, "font_size", 72.0, state.local_time_ms) or 72.0)
            fill = escape(str(_source_value(params, "fill", "#ffffff", state.local_time_ms) or "#ffffff"))
            body.append(f'<text id="{escape(layer.id)}" transform="{transform}" font-family="{family}" font-size="{size:.8g}" fill="{fill}" opacity="{opacity:.8g}">{text}</text>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{composition.width}" height="{composition.height}" '
        f'viewBox="0 0 {composition.width} {composition.height}">' + "".join(body) + "</svg>"
    )


def otio_document(composition: MotionComposition) -> dict[str, Any]:
    report = preflight_interchange(composition, "otio_timing")
    if not report["ok"]:
        raise ValueError("OTIO preflight failed")
    rate = float(composition.fps)
    tracks = []
    for layer in composition.layers:
        if layer.id not in report["supported_layer_ids"]:
            continue
        clip = {
            "OTIO_SCHEMA": "Clip.2", "name": layer.name,
            "metadata": {"tigercapture": {"layer_id": layer.id, "layer_type": layer.layer_type}},
            "source_range": {
                "OTIO_SCHEMA": "TimeRange.1",
                "start_time": {"OTIO_SCHEMA": "RationalTime.1", "value": layer.source_in_ms * rate / 1000.0, "rate": rate},
                "duration": {"OTIO_SCHEMA": "RationalTime.1", "value": (layer.out_ms - layer.in_ms) * rate / 1000.0, "rate": rate},
            },
            "media_reference": {
                "OTIO_SCHEMA": "ExternalReference.1",
                "target_url": Path(layer.source.uri).expanduser().resolve().as_uri(),
                "available_range": None, "metadata": {},
            },
        }
        children = []
        if layer.in_ms > 0:
            children.append({
                "OTIO_SCHEMA": "Gap.1", "name": "",
                "source_range": {
                    "OTIO_SCHEMA": "TimeRange.1",
                    "start_time": {"OTIO_SCHEMA": "RationalTime.1", "value": 0.0, "rate": rate},
                    "duration": {"OTIO_SCHEMA": "RationalTime.1", "value": layer.in_ms * rate / 1000.0, "rate": rate},
                },
                "metadata": {},
            })
        children.append(clip)
        tracks.append({
            "OTIO_SCHEMA": "Track.1", "name": layer.name, "kind": "Video", "metadata": {},
            "children": children,
        })
    return {
        "OTIO_SCHEMA": "Timeline.1", "name": composition.name,
        "global_start_time": {"OTIO_SCHEMA": "RationalTime.1", "value": 0.0, "rate": rate},
        "tracks": {
            "OTIO_SCHEMA": "Stack.1", "name": "Motion References", "metadata": {},
            "children": tracks,
        },
        "metadata": {"tigercapture": {"scope": "media_timing_reference", "schema": INTERCHANGE_SCHEMA}},
    }


def _copy_gltf_source(source: Path, output: Path) -> list[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == ".glb":
        if output.suffix.lower() != ".glb":
            raise ValueError("A GLB source requires a .glb output path")
        shutil.copy2(source, output)
        return [str(output)]
    if output.suffix.lower() != ".gltf":
        raise ValueError("A glTF source requires a .gltf output path")
    data = json.loads(source.read_text(encoding="utf-8"))
    copied = [str(output)]
    asset_dir = output.parent / f"{output.stem}_assets"
    used: dict[str, str] = {}
    for collection in ("buffers", "images"):
        for row in data.get(collection, []):
            uri = str(row.get("uri") or "")
            if not uri or uri.startswith("data:"):
                continue
            dependency = (source.parent / uri).resolve()
            if not dependency.is_file():
                raise FileNotFoundError(f"glTF dependency is missing: {dependency}")
            name = dependency.name
            if name in used and used[name] != str(dependency):
                name = f"{dependency.stem}_{len(used)}{dependency.suffix}"
            used[name] = str(dependency)
            target = asset_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dependency, target)
            row["uri"] = f"{asset_dir.name}/{quote(name)}"
            copied.append(str(target))
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return copied


def export_interchange(composition: MotionComposition, format_id: str, output_path: str | Path, *,
                       time_ms: float = 0.0) -> dict[str, Any]:
    report = preflight_interchange(composition, format_id, time_ms=time_ms)
    if not report["ok"]:
        reasons = [row["reason"] for row in [*report["blockers"], *report["bake_required"]]]
        raise RuntimeError("Motion interchange preflight failed: " + "; ".join(reasons))
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if format_id == "lottie":
        output.write_text(json.dumps(lottie_document(composition), ensure_ascii=False, indent=2), encoding="utf-8")
        paths = [str(output)]
    elif format_id == "svg":
        output.write_text(svg_document(composition, time_ms=time_ms), encoding="utf-8")
        paths = [str(output)]
    elif format_id == "otio_timing":
        output.write_text(json.dumps(otio_document(composition), ensure_ascii=False, indent=2), encoding="utf-8")
        paths = [str(output)]
    else:
        source_layer = next(layer for layer in composition.layers if layer.id in report["supported_layer_ids"])
        paths = _copy_gltf_source(Path(source_layer.source.uri).resolve(), output)
    return {"ok": True, "format_id": format_id, "output_path": str(output), "paths": paths, "preflight": report}


__all__ = [
    "INTERCHANGE_FORMATS", "INTERCHANGE_SCHEMA", "export_interchange", "list_interchange_formats",
    "lottie_document", "otio_document", "preflight_interchange", "svg_document",
]
