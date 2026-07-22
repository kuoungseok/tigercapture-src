"""Qt-free Live2D and Spine source state for Motion Designer."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping

from .keyframes import evaluate_property
from .schema import AnimatedProperty, MotionComposition, MotionLayer, SourceRef


LIVE2D_SOURCE_KIND = "live2d_actor"
SPINE_SOURCE_KIND = "spine_actor"
ACTOR_SOURCE_KINDS = {LIVE2D_SOURCE_KIND, SPINE_SOURCE_KIND}


def _deep_merge(target: dict[str, Any], changes: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in changes.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[str(key)] = dict(value) if isinstance(value, Mapping) else value
    return target


def _value(value: Any, time_ms: float, fallback: Any, value_type: str = "scalar") -> Any:
    if value is None:
        return fallback
    if isinstance(value, Mapping) and ({"default", "keyframes"} & set(value)):
        return evaluate_property(AnimatedProperty.from_dict(value, value_type=value_type), time_ms)
    return value


def _live2d_catalog(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"motions": [], "expressions": [], "physics": False, "pose": False}
    refs = data.get("FileReferences") if isinstance(data, dict) else {}
    refs = refs if isinstance(refs, Mapping) else {}
    motions: list[dict[str, Any]] = []
    groups = refs.get("Motions") if isinstance(refs.get("Motions"), Mapping) else {}
    for group in sorted(groups):
        rows = groups.get(group)
        if not isinstance(rows, list):
            continue
        motions.extend({"group": str(group), "index": index} for index, _row in enumerate(rows))
    expressions: list[str] = []
    for row in refs.get("Expressions", []) if isinstance(refs.get("Expressions"), list) else []:
        if not isinstance(row, Mapping):
            continue
        identifier = str(row.get("Name") or row.get("Id") or Path(str(row.get("File") or "")).stem)
        if identifier:
            expressions.append(identifier)
    return {
        "motions": motions,
        "expressions": expressions,
        "physics": bool(refs.get("Physics")),
        "pose": bool(refs.get("Pose")),
    }


def inspect_actor_source(kind: str, path: str | Path) -> dict[str, Any]:
    """Resolve a durable actor source and report selectable animation metadata."""
    from app.actor_compat_repair import repair_actor_model_path

    normalized_kind = str(kind or "").lower()
    repair_kind = "live2d" if normalized_kind == LIVE2D_SOURCE_KIND else "spine"
    repair = repair_actor_model_path(repair_kind, str(path))
    resolved = Path(str(repair.get("path") or path))
    result: dict[str, Any] = {
        "ok": bool(repair.get("ok")),
        "kind": normalized_kind,
        "source_path": str(Path(path).expanduser().resolve()),
        "resolved_path": str(resolved.expanduser().resolve()),
        "repair": repair,
        "motions": [],
        "expressions": [],
        "animations": [],
        "skins": [],
        "atlas_path": str((repair.get("metadata") or {}).get("atlas_path") or ""),
    }
    if normalized_kind == LIVE2D_SOURCE_KIND:
        result.update(_live2d_catalog(resolved))
    elif normalized_kind == SPINE_SOURCE_KIND and resolved.is_file():
        try:
            from app.spine_editor.spine_json_parser import load_spine_file

            skeleton = load_spine_file(str(resolved))
            result["animations"] = sorted(str(name) for name in (getattr(skeleton, "animations", {}) or {}))
            result["skins"] = sorted(str(name) for name in (getattr(skeleton, "skins", {}) or {}))
        except Exception as exc:
            result["ok"] = False
            result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def _preferred(values: list[str], names: tuple[str, ...], fallback: str = "") -> str:
    folded = {value.casefold(): value for value in values}
    for name in names:
        if name.casefold() in folded:
            return folded[name.casefold()]
    return values[0] if values else fallback


def default_actor_params(kind: str, *, width: int, height: int, source_info: Mapping[str, Any]) -> dict[str, Any]:
    normalized_kind = str(kind or "").lower()
    playback: dict[str, Any] = {
        "loop": True,
        "rate": 1.0,
        "preview_cache_fps": 30.0,
    }
    if normalized_kind == LIVE2D_SOURCE_KIND:
        motions = list(source_info.get("motions") or [])
        selected = next((row for row in motions if str(row.get("group", "")).casefold() == "idle"), None)
        selected = selected or (motions[0] if motions else {})
        playback.update({
            "motion_group": str(selected.get("group") or ""),
            "motion_index": int(selected.get("index", 0) or 0),
            "expression": "",
        })
    else:
        animations = [str(value) for value in source_info.get("animations", [])]
        skins = [str(value) for value in source_info.get("skins", [])]
        playback.update({
            "animation": _preferred(animations, ("idle", "wait", "loop", "action", "walk", "run")),
            "skin": _preferred(skins, ("default",), "default"),
        })
    return {
        "asset": {
            "resolved_path": str(source_info.get("resolved_path") or ""),
            "atlas_path": str(source_info.get("atlas_path") or ""),
        },
        "playback": playback,
        "actor": {
            "position": AnimatedProperty(value_type="vector2", default=[0.5, 0.5]).to_dict(),
            "scale": AnimatedProperty(default=1.0).to_dict(),
            "opacity": AnimatedProperty(default=1.0).to_dict(),
        },
        "render": {"width": int(width), "height": int(height), "premultiplied_alpha": True},
        "parameters": {},
        "catalog": {
            "motions": list(source_info.get("motions") or []),
            "expressions": list(source_info.get("expressions") or []),
            "animations": list(source_info.get("animations") or []),
            "skins": list(source_info.get("skins") or []),
        },
    }


def create_actor_layer(
    kind: str,
    path: str | Path,
    *,
    width: int,
    height: int,
    duration_ms: int,
    name: str = "",
    start_ms: int = 0,
    end_ms: int = 0,
    params: Mapping[str, Any] | None = None,
) -> MotionLayer:
    normalized_kind = str(kind or "").lower()
    if normalized_kind not in ACTOR_SOURCE_KINDS:
        raise ValueError(f"Unsupported Motion actor kind: {kind}")
    source = Path(path).expanduser().resolve()
    info = inspect_actor_source(normalized_kind, source)
    if not info.get("ok"):
        warnings = list((info.get("repair") or {}).get("warnings") or [])
        raise ValueError(warnings[0] if warnings else str(info.get("error") or f"Actor source is not loadable: {source}"))
    values = default_actor_params(normalized_kind, width=width, height=height, source_info=info)
    if params:
        _deep_merge(values, params)
    layer = MotionLayer(
        name=str(name or source.stem),
        layer_type=normalized_kind,
        source=SourceRef(kind=normalized_kind, uri=str(source), params=values),
        in_ms=max(0, int(start_ms)),
        out_ms=max(max(0, int(start_ms)) + 1, int(end_ms or duration_ms)),
        metadata={"actor_renderer": "existing_tiger_actor_runtime"},
    )
    layer.transform.position.default = [float(width) * 0.5, float(height) * 0.5]
    return layer


@dataclass(slots=True)
class MotionActorFrame:
    kind: str
    source_path: str
    resolved_path: str
    atlas_path: str
    playback_time_ms: float
    motion_group: str = ""
    motion_index: int = 0
    expression: str = ""
    animation: str = ""
    skin: str = "default"
    loop: bool = True
    position: list[float] = field(default_factory=lambda: [0.5, 0.5])
    scale: float = 1.0
    opacity: float = 1.0
    parameters: dict[str, Any] = field(default_factory=dict)
    mouth_open: float = 0.0
    diagnostics: dict[str, Any] = field(default_factory=dict)


def _mouth_open(cues: list[Any], composition_time_ms: float) -> float:
    now = float(composition_time_ms)
    for cue in cues:
        if not isinstance(cue, Mapping):
            continue
        start = float(cue.get("start_ms", 0) or 0)
        end = max(start + 1.0, float(cue.get("end_ms", start + 1) or start + 1))
        if start <= now <= end:
            edge = min(1.0, (now - start) / 55.0, (end - now) / 55.0)
            return max(0.12, min(1.0, 0.72 + 0.24 * edge))
    return 0.0


def evaluate_actor_frame(
    layer: MotionLayer,
    time_ms: float,
    *,
    composition: MotionComposition | None = None,
    composition_time_ms: float | None = None,
) -> MotionActorFrame:
    if layer.layer_type not in ACTOR_SOURCE_KINDS and layer.source.kind not in ACTOR_SOURCE_KINDS:
        raise ValueError(f"Motion layer is not an actor source: {layer.layer_type}")
    params = layer.source.params
    asset = params.get("asset") if isinstance(params.get("asset"), Mapping) else {}
    playback = params.get("playback") if isinstance(params.get("playback"), Mapping) else {}
    actor = params.get("actor") if isinstance(params.get("actor"), Mapping) else {}
    rate = max(0.01, min(8.0, float(_value(playback.get("rate"), time_ms, 1.0))))
    play_time = max(0.0, float(time_ms) * rate)
    loop = bool(_value(playback.get("loop"), time_ms, True, "bool"))
    duration = max(1.0, float(layer.out_ms - layer.in_ms) * rate)
    if loop:
        play_time %= duration
    position = list(_value(actor.get("position"), time_ms, [0.5, 0.5], "vector2"))
    position = (position + [0.5, 0.5])[:2]
    global_time = float(time_ms if composition_time_ms is None else composition_time_ms)
    cues = list(layer.metadata.get("lip_sync_cues") or [])
    mouth = _mouth_open(cues, global_time)
    resolved = str(asset.get("resolved_path") or layer.source.uri)
    diagnostics = {
        "ok": Path(resolved).is_file(),
        "actor_kind": layer.layer_type,
        "source_path": layer.source.uri,
        "resolved_path": resolved,
        "timeline_evaluation": "deterministic_source_time",
        "lip_sync_cue_count": len(cues),
        "voice_timing_source_id": str(layer.metadata.get("voice_timing_source_id") or ""),
        "composition_revision": int(getattr(composition, "revision", 0) or 0),
    }
    return MotionActorFrame(
        kind=layer.layer_type,
        source_path=layer.source.uri,
        resolved_path=resolved,
        atlas_path=str(asset.get("atlas_path") or ""),
        playback_time_ms=play_time,
        motion_group=str(_value(playback.get("motion_group"), time_ms, "", "string")),
        motion_index=int(_value(playback.get("motion_index"), time_ms, 0)),
        expression=str(_value(playback.get("expression"), time_ms, "", "string")),
        animation=str(_value(playback.get("animation"), time_ms, "", "string")),
        skin=str(_value(playback.get("skin"), time_ms, "default", "string")),
        loop=loop,
        position=[float(position[0]), float(position[1])],
        scale=max(0.01, min(20.0, float(_value(actor.get("scale"), time_ms, 1.0)))),
        opacity=max(0.0, min(1.0, float(_value(actor.get("opacity"), time_ms, 1.0)))),
        parameters=dict(params.get("parameters") or {}),
        mouth_open=mouth,
        diagnostics=diagnostics,
    )


def update_actor_params(layer: MotionLayer, changes: Mapping[str, Any]) -> None:
    if layer.layer_type not in ACTOR_SOURCE_KINDS:
        raise ValueError(f"Motion layer is not an actor: {layer.id}")
    _deep_merge(layer.source.params, changes)


__all__ = [
    "ACTOR_SOURCE_KINDS", "LIVE2D_SOURCE_KIND", "SPINE_SOURCE_KIND", "MotionActorFrame",
    "create_actor_layer", "default_actor_params", "evaluate_actor_frame", "inspect_actor_source",
    "update_actor_params",
]
