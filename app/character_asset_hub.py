"""Character Asset Hub folder scanning and handoff contracts.

The hub is intentionally Qt-free.  UI surfaces, Media Pool actions, MCP, and QA
can all consume the same report without loading editor widgets.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import html
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


CHARACTER_ASSET_HUB_SCHEMA = "tigercapture.character_asset_hub.v1"
CHARACTER_ASSET_RECORD_SCHEMA = "tigercapture.character_asset_hub.asset.v1"
CHARACTER_ASSET_THUMBNAIL_SCHEMA = "tigercapture.character_asset_hub.thumbnail.v1"

LIVE2D_KIND = "live2d"
SPINE_KIND = "spine"
MMD_KIND = "mmd"
VRM_KIND = "vrm"
SUPPORTED_KINDS = (LIVE2D_KIND, SPINE_KIND, MMD_KIND, VRM_KIND)

_LIVE2D_MODEL_SUFFIX = ".model3.json"
_LIVE2D_JSON_SUFFIXES = (
    ".motion3.json",
    ".exp3.json",
    ".physics3.json",
    ".pose3.json",
    ".userdata3.json",
    ".cdi3.json",
)
_SPINE_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def scan_character_asset_folder(
    root: str | Path,
    *,
    max_depth: int = 8,
    render_probe: bool = False,
) -> dict[str, Any]:
    """Scan a user-supplied folder for placeable character assets.

    ``render_probe`` is intentionally opt-in.  The default report answers
    whether an asset is dependency-ready for render, without spending a full
    render pass on every model in a folder.
    """
    root_path = Path(root).expanduser()
    if root_path.exists():
        root_path = root_path.resolve()
    payload: dict[str, Any] = {
        "schema": CHARACTER_ASSET_HUB_SCHEMA,
        "root": str(root_path),
        "root_exists": root_path.is_dir(),
        "render_probe": bool(render_probe),
        "assets": [],
        "counts": {kind: 0 for kind in SUPPORTED_KINDS},
        "ready_count": 0,
        "blocked_count": 0,
        "timeline_addable_count": 0,
        "warnings": [],
    }
    if not root_path.is_dir():
        payload["ok"] = False
        payload["warnings"].append("root_missing_or_not_directory")
        return payload

    files = _iter_files(root_path, max_depth=max_depth)
    vmd_paths = [path for path in files if path.suffix.casefold() == ".vmd"]
    records: list[dict[str, Any]] = []

    for path in files:
        lower_name = path.name.casefold()
        suffix = path.suffix.casefold()
        try:
            if lower_name.endswith(_LIVE2D_MODEL_SUFFIX):
                records.append(_scan_live2d_asset(root_path, path))
            elif _is_spine_candidate(path):
                records.append(_scan_spine_asset(root_path, path))
            elif _is_mmd_model_path(path):
                records.append(_scan_mmd_asset(root_path, path, vmd_paths, render_probe=render_probe))
            elif suffix == ".vrm":
                records.append(_scan_vrm_asset(root_path, path))
        except Exception as exc:
            kind = _kind_guess(path)
            records.append(
                _base_record(root_path, path, kind, display_name=path.stem, asset_type=f"{kind}_asset")
                | {
                    "render": _render_status("scan_failed", False, probe=bool(render_probe), reason=type(exc).__name__),
                    "errors": [f"{type(exc).__name__}: {exc}"],
                    "timeline_add": _timeline_disabled("scan_failed"),
                }
            )

    deduped = _dedupe_records(records)
    deduped.sort(key=lambda row: (str(row.get("kind") or ""), str(row.get("path") or "")))
    payload["assets"] = deduped
    payload["counts"] = {kind: sum(1 for row in deduped if row.get("kind") == kind) for kind in SUPPORTED_KINDS}
    payload["ready_count"] = sum(1 for row in deduped if bool((row.get("render") or {}).get("capable")))
    payload["blocked_count"] = sum(1 for row in deduped if not bool((row.get("render") or {}).get("capable")))
    payload["timeline_addable_count"] = sum(1 for row in deduped if bool((row.get("timeline_add") or {}).get("enabled")))
    payload["ok"] = bool(deduped)
    if not deduped:
        payload["warnings"].append("no_character_assets_found")
    return payload


def build_character_asset_timeline_add(
    record: Mapping[str, Any],
    *,
    start_ms: int = 0,
    duration_ms: int = 10_000,
) -> dict[str, Any]:
    """Return the existing public action payload for adding this asset."""
    kind = str(record.get("kind") or "")
    path = str(record.get("path") or "")
    if not path:
        return _timeline_disabled("missing_asset_path")
    start = max(0, int(start_ms or 0))
    duration = max(1, int(duration_ms or 10_000))
    features = record.get("features") if isinstance(record.get("features"), Mapping) else {}
    transform = (
        record.get("recommended_transform")
        if isinstance(record.get("recommended_transform"), Mapping)
        else {}
    )

    if kind == LIVE2D_KIND:
        return {
            "enabled": bool((record.get("render") or {}).get("capable")),
            "action": "actor.add",
            "label": "Add Live2D to Timeline",
            "params": {
                "kind": "live2d",
                "path": path,
                "start_ms": start,
                "duration_ms": duration,
                "pos_x": float(transform.get("pos_x", 0.5)),
                "pos_y": float(transform.get("pos_y", 0.5)),
                "scale": float(transform.get("scale", 1.0)),
                "opacity": 1.0,
            },
        }
    if kind == SPINE_KIND:
        atlas_path = str(features.get("atlas_path") or "")
        animations = list(features.get("animations") or [])
        skins = list(features.get("skins") or [])
        return {
            "enabled": bool((record.get("render") or {}).get("capable")),
            "action": "actor.add",
            "label": "Add Spine to Timeline",
            "params": {
                "kind": "spine",
                "path": path,
                "atlas_path": atlas_path,
                "anim_name": str(animations[0]) if animations else "",
                "skin_name": str(skins[0]) if skins else "default",
                "start_ms": start,
                "duration_ms": duration,
                "pos_x": float(transform.get("pos_x", 0.5)),
                "pos_y": float(transform.get("pos_y", 0.5)),
                "scale": float(transform.get("scale", 1.0)),
            },
        }
    if kind == MMD_KIND:
        motions = list(features.get("motions") or [])
        return {
            "enabled": Path(path).is_file(),
            "action": "mmd.actor.add",
            "label": "Add MMD to Timeline",
            "params": {
                "path": path,
                "motion_path": str(motions[0].get("path") or "") if motions and isinstance(motions[0], Mapping) else "",
                "start_ms": start,
                "duration_ms": duration,
            },
        }
    if kind == VRM_KIND:
        profile = record.get("profile") if isinstance(record.get("profile"), Mapping) else {}
        return {
            "enabled": bool(profile.get("ok") and profile.get("vseeface_compatible")),
            "action": "vtuber.vseeface_select_vrm0_avatar",
            "label": "Use VRM as Avatar Target",
            "params": {"path": path},
            "reason": "" if bool(profile.get("vseeface_compatible")) else "vrm_not_vseeface_vrm0",
        }
    return _timeline_disabled("unsupported_kind")


def simulate_character_asset_hub_user_flow(
    root: str | Path,
    *,
    start_ms: int = 0,
    duration_ms: int = 10_000,
    max_depth: int = 8,
) -> dict[str, Any]:
    """Deterministically mimic the user dropping a folder and pressing add.

    This is the core QA path: no mouse is needed to prove that a folder turns
    into categorized cards and public timeline/avatar actions.
    """
    scan = scan_character_asset_folder(root, max_depth=max_depth)
    steps: list[dict[str, Any]] = []
    for record in list(scan.get("assets") or []):
        if not isinstance(record, Mapping):
            continue
        step = build_character_asset_timeline_add(record, start_ms=start_ms, duration_ms=duration_ms)
        if step.get("enabled") and step.get("action"):
            steps.append({"asset_id": record.get("id"), **step})
    return {
        "schema": "tigercapture.character_asset_hub.user_flow.v1",
        "ok": bool(scan.get("ok")) and bool(steps),
        "scan": scan,
        "timeline_steps": steps,
        "step_count": len(steps),
    }


def write_character_asset_hub_thumbnails(
    payload: Mapping[str, Any],
    out_dir: str | Path,
    *,
    size: int = 128,
) -> dict[str, Any]:
    """Write deterministic SVG placeholder thumbnails for hub cards."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = deepcopy(dict(payload))
    assets: list[dict[str, Any]] = []
    for raw in list(result.get("assets") or []):
        if not isinstance(raw, Mapping):
            continue
        record = dict(raw)
        asset_id = str(record.get("id") or _asset_id(str(record.get("kind") or ""), str(record.get("path") or "")))
        path = out / f"{asset_id}.svg"
        path.write_text(_thumbnail_svg(record, size=max(48, int(size or 128))), encoding="utf-8")
        thumb = dict(record.get("thumbnail") or {})
        thumb.update(
            {
                "schema": CHARACTER_ASSET_THUMBNAIL_SCHEMA,
                "status": "generated_placeholder",
                "path": str(path),
                "kind": record.get("kind"),
            }
        )
        record["thumbnail"] = thumb
        assets.append(record)
    result["assets"] = assets
    result["thumbnail_dir"] = str(out)
    return result


def summarize_character_asset_hub(payload: Mapping[str, Any]) -> str:
    counts = payload.get("counts") if isinstance(payload.get("counts"), Mapping) else {}
    return (
        f"Character Asset Hub: assets={len(list(payload.get('assets') or []))} "
        f"ready={int(payload.get('ready_count', 0) or 0)} "
        f"timeline={int(payload.get('timeline_addable_count', 0) or 0)} "
        f"live2d={int(counts.get(LIVE2D_KIND, 0) or 0)} "
        f"spine={int(counts.get(SPINE_KIND, 0) or 0)} "
        f"mmd={int(counts.get(MMD_KIND, 0) or 0)} "
        f"vrm={int(counts.get(VRM_KIND, 0) or 0)}"
    )


def _iter_files(root: Path, *, max_depth: int) -> list[Path]:
    limit = max(1, int(max_depth or 1))
    rows: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            depth = len(path.relative_to(root).parts)
        except Exception:
            depth = limit + 1
        if depth <= limit:
            rows.append(path)
    rows.sort(key=lambda row: str(row).casefold())
    return rows


def _scan_live2d_asset(root: Path, model_path: Path) -> dict[str, Any]:
    record = _base_record(root, model_path, LIVE2D_KIND, display_name=model_path.stem, asset_type="live2d_model")
    data = _read_json(model_path)
    refs = data.get("FileReferences") if isinstance(data.get("FileReferences"), Mapping) else {}
    missing: list[dict[str, Any]] = []
    features: dict[str, Any] = {
        "motions": [],
        "expressions": [],
        "textures": [],
        "physics": "",
        "pose": "",
        "moc3_version": -1,
    }
    moc_path = _resolve_ref(model_path.parent, refs.get("Moc"))
    if moc_path is not None:
        features["moc"] = str(moc_path)
        if not moc_path.is_file():
            missing.append(_missing_file("moc", moc_path, required=True))
    else:
        missing.append(_missing_file("moc", model_path.parent / "<missing Moc>", required=True))

    textures = refs.get("Textures") if isinstance(refs.get("Textures"), list) else []
    for index, raw in enumerate(textures):
        texture = _resolve_ref(model_path.parent, raw)
        if texture is None:
            continue
        features["textures"].append(str(texture))
        if not texture.is_file():
            missing.append(_missing_file(f"texture:{index}", texture, required=True))

    motions = refs.get("Motions") if isinstance(refs.get("Motions"), Mapping) else {}
    for group, rows in motions.items():
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, Mapping):
                continue
            motion_path = _resolve_ref(model_path.parent, row.get("File"))
            item = {
                "group": str(group),
                "name": str(row.get("Name") or (motion_path.stem if motion_path else "")),
                "path": str(motion_path) if motion_path else "",
            }
            features["motions"].append(item)
            if motion_path is not None and not motion_path.is_file():
                missing.append(_missing_file(f"motion:{group}", motion_path, required=False))

    expressions = refs.get("Expressions") if isinstance(refs.get("Expressions"), list) else []
    for row in expressions:
        if not isinstance(row, Mapping):
            continue
        expression_path = _resolve_ref(model_path.parent, row.get("File"))
        item = {
            "name": str(row.get("Name") or (expression_path.stem if expression_path else "")),
            "path": str(expression_path) if expression_path else "",
        }
        features["expressions"].append(item)
        if expression_path is not None and not expression_path.is_file():
            missing.append(_missing_file("expression", expression_path, required=False))

    for key in ("Physics", "Pose"):
        ref_path = _resolve_ref(model_path.parent, refs.get(key))
        if ref_path is not None:
            features[key.casefold()] = str(ref_path)
            if not ref_path.is_file():
                missing.append(_missing_file(key.casefold(), ref_path, required=False))

    warnings: list[str] = []
    try:
        from app.live2d.compat import moc3_version, model_support_error

        features["moc3_version"] = int(moc3_version(model_path))
        support_error = model_support_error(model_path)
        if support_error:
            warnings.append(support_error)
    except Exception as exc:
        warnings.append(f"live2d_support_probe_failed:{type(exc).__name__}")

    required_missing = [row for row in missing if row.get("required")]
    capable = not required_missing and not any("cannot be loaded safely" in row.lower() for row in warnings)
    record.update(
        {
            "features": features,
            "missing_files": missing,
            "warnings": warnings,
            "recommended_transform": _recommended_transform(LIVE2D_KIND),
            "render": _render_status(
                "ready_unprobed" if capable else "missing_dependency",
                capable,
                probe=False,
                reason="" if capable else "missing_required_live2d_dependency",
            ),
        }
    )
    record["timeline_add"] = build_character_asset_timeline_add(record)
    return record


def _scan_spine_asset(root: Path, source_path: Path) -> dict[str, Any]:
    from app.actor_compat_repair import repair_actor_model_path

    repair = repair_actor_model_path(SPINE_KIND, str(source_path))
    model_path = Path(str(repair.get("path") or source_path))
    record = _base_record(root, model_path, SPINE_KIND, display_name=model_path.stem, asset_type="spine_skeleton")
    metadata = dict(repair.get("metadata") or {})
    missing: list[dict[str, Any]] = []
    features: dict[str, Any] = {
        "animations": [],
        "skins": [],
        "atlas_path": str(metadata.get("atlas_path") or ""),
        "texture_pages": list(metadata.get("texture_pages") or []),
        "spine_binary_version": str(metadata.get("spine_binary_version") or ""),
        "pma": bool(metadata.get("pma", False)),
    }
    if not features["atlas_path"]:
        missing.append(_missing_file("atlas", model_path.with_suffix(".atlas"), required=True))
    for page in list(features["texture_pages"]):
        page_path = Path(str(page))
        if not page_path.is_file():
            missing.append(_missing_file("atlas_page", page_path, required=True))

    if model_path.suffix.casefold() == ".json" or model_path.name.casefold().endswith(".skel.json"):
        try:
            data = _read_json(model_path)
            animations = data.get("animations")
            if isinstance(animations, Mapping):
                features["animations"] = sorted(str(key) for key in animations.keys())
            skins = data.get("skins")
            features["skins"] = _spine_skin_names(skins)
        except Exception as exc:
            missing.append(
                {
                    "role": "spine_json",
                    "path": str(model_path),
                    "required": True,
                    "reason": f"parse_failed:{type(exc).__name__}",
                }
            )

    warnings = [str(row) for row in list(repair.get("warnings") or []) if str(row)]
    required_missing = [row for row in missing if row.get("required")]
    capable = bool(repair.get("ok")) and not required_missing
    record.update(
        {
            "features": features,
            "missing_files": missing,
            "warnings": warnings,
            "recommended_transform": _recommended_transform(SPINE_KIND),
            "render": _render_status(
                "ready_unprobed" if capable else "missing_dependency",
                capable,
                probe=False,
                reason="" if capable else "missing_required_spine_dependency",
            ),
        }
    )
    record["timeline_add"] = build_character_asset_timeline_add(record)
    return record


def _scan_mmd_asset(
    root: Path,
    model_path: Path,
    vmd_paths: list[Path],
    *,
    render_probe: bool,
) -> dict[str, Any]:
    record = _base_record(root, model_path, MMD_KIND, display_name=model_path.stem, asset_type="mmd_model")
    motions = _nearby_mmd_motions(root, model_path, vmd_paths)
    features: dict[str, Any] = {
        "motions": [{"name": path.stem, "path": str(path)} for path in motions],
        "morphs": [],
        "materials": 0,
        "bones": 0,
        "physics": False,
        "format": "pbx" if model_path.name.casefold().endswith(".pbx.json") else model_path.suffix.casefold().lstrip("."),
    }
    warnings: list[str] = []
    missing: list[dict[str, Any]] = []
    capable = model_path.is_file()
    render = _render_status("ready_unprobed" if capable else "missing_model", capable, probe=False)
    if render_probe and capable:
        try:
            from app.mmd.diagnostics import analyze_mmd_model

            report = analyze_mmd_model(model_path, motions[0] if motions else None)
            model = report.get("model") if isinstance(report.get("model"), Mapping) else {}
            features.update(
                {
                    "materials": int(model.get("materials", 0) or 0),
                    "bones": int(model.get("bones", 0) or 0),
                    "morph_count": int(model.get("morphs", 0) or 0),
                    "physics": bool(int(model.get("rigid_bodies", 0) or 0) or int(model.get("joints", 0) or 0)),
                    "feature_flags": list(report.get("feature_flags") or []),
                    "risk_codes": list(report.get("risk_codes") or []),
                }
            )
            capable = bool(report.get("ok"))
            render = _render_status(
                "ready_probed" if capable else "render_risk",
                capable,
                probe=True,
                reason=",".join(str(code) for code in list(report.get("risk_codes") or [])[:4]),
                diagnostics=report,
            )
        except Exception as exc:
            capable = False
            render = _render_status("parse_failed", False, probe=True, reason=type(exc).__name__)
            warnings.append(f"mmd_parse_failed:{type(exc).__name__}: {exc}")
    record.update(
        {
            "features": features,
            "missing_files": missing,
            "warnings": warnings,
            "recommended_transform": _recommended_transform(MMD_KIND),
            "render": render,
        }
    )
    record["timeline_add"] = build_character_asset_timeline_add(record)
    return record


def _scan_vrm_asset(root: Path, path: Path) -> dict[str, Any]:
    record = _base_record(root, path, VRM_KIND, display_name=path.stem, asset_type="vrm_avatar")
    try:
        from app.vtuber.vrm_profile import inspect_vrm_profile

        profile = inspect_vrm_profile(path)
    except Exception as exc:
        profile = {"ok": False, "errors": [f"vrm_profile_failed:{type(exc).__name__}: {exc}"]}
    warnings = [str(row) for row in list(profile.get("warnings") or []) if str(row)]
    errors = [str(row) for row in list(profile.get("errors") or []) if str(row)]
    features = {
        "profile": str(profile.get("profile") or ""),
        "title": str(profile.get("title") or path.stem),
        "author": str(profile.get("author") or ""),
        "humanoid_bone_count": int(profile.get("humanoid_bone_count", 0) or 0),
        "blend_shape_group_count": int(profile.get("blend_shape_group_count", 0) or 0),
        "vseeface_compatible": bool(profile.get("vseeface_compatible")),
    }
    capable = bool(profile.get("ok"))
    record.update(
        {
            "profile": profile,
            "features": features,
            "missing_files": [],
            "warnings": warnings,
            "errors": errors,
            "recommended_transform": _recommended_transform(VRM_KIND),
            "render": _render_status(
                "ready_unprobed" if capable else "parse_failed",
                capable,
                probe=False,
                reason="" if capable else ",".join(errors[:2]),
            ),
        }
    )
    record["timeline_add"] = build_character_asset_timeline_add(record)
    return record


def _base_record(root: Path, path: Path, kind: str, *, display_name: str, asset_type: str) -> dict[str, Any]:
    resolved = path.expanduser().resolve() if path.exists() else path
    return {
        "schema": CHARACTER_ASSET_RECORD_SCHEMA,
        "id": _asset_id(kind, str(resolved)),
        "kind": kind,
        "asset_type": asset_type,
        "display_name": display_name or path.stem or path.name,
        "path": str(resolved),
        "relative_path": _safe_relative(resolved, root),
        "root": str(root),
        "thumbnail": {
            "schema": CHARACTER_ASSET_THUMBNAIL_SCHEMA,
            "status": "placeholder_pending",
            "kind": kind,
        },
        "features": {},
        "missing_files": [],
        "warnings": [],
        "errors": [],
        "recommended_transform": _recommended_transform(kind),
        "render": _render_status("unknown", False, probe=False),
        "timeline_add": _timeline_disabled("not_analyzed"),
    }


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def _resolve_ref(base: Path, value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def _missing_file(role: str, path: Path, *, required: bool) -> dict[str, Any]:
    return {
        "role": str(role),
        "path": str(path),
        "required": bool(required),
        "reason": "missing_file",
    }


def _render_status(
    status: str,
    capable: bool,
    *,
    probe: bool,
    reason: str = "",
    diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": str(status),
        "capable": bool(capable),
        "probe": bool(probe),
        "reason": str(reason or ""),
        "diagnostics": dict(diagnostics or {}),
    }


def _timeline_disabled(reason: str) -> dict[str, Any]:
    return {"enabled": False, "action": "", "params": {}, "label": "", "reason": str(reason or "")}


def _recommended_transform(kind: str) -> dict[str, Any]:
    if kind == MMD_KIND:
        return {
            "origin": "feet_ground_contact",
            "anchor": "timeline_actor_center",
            "pos_x": 0.5,
            "pos_y": 0.54,
            "scale": 1.0,
            "notes": ["MMD models should be foot-ground aligned before camera framing."],
        }
    if kind == VRM_KIND:
        return {
            "origin": "humanoid_hips",
            "anchor": "vtuber_program_output_safe_area",
            "pos_x": 0.5,
            "pos_y": 0.5,
            "scale": 1.0,
            "preset": "bust_up",
            "notes": ["VRM placement is controlled by VTuber Studio avatar framing."],
        }
    if kind == SPINE_KIND:
        return {
            "origin": "skeleton_bounds_center",
            "anchor": "screen_center",
            "pos_x": 0.5,
            "pos_y": 0.5,
            "scale": 1.0,
            "notes": ["Use first skin/animation as the timeline default, then refine in Spine editor."],
        }
    return {
        "origin": "model_bounds_center",
        "anchor": "screen_center",
        "pos_x": 0.5,
        "pos_y": 0.5,
        "scale": 1.0,
        "notes": ["Live2D transform is normalized to the actor viewport."],
    }


def _asset_id(kind: str, path: str) -> str:
    digest = hashlib.sha1(f"{kind}:{path}".encode("utf-8", "replace")).hexdigest()[:12]
    return f"{kind}_{digest}"


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def _dedupe_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (str(record.get("kind") or ""), str(record.get("path") or "").casefold())
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def _kind_guess(path: Path) -> str:
    name = path.name.casefold()
    suffix = path.suffix.casefold()
    if name.endswith(_LIVE2D_MODEL_SUFFIX):
        return LIVE2D_KIND
    if suffix in {".skel", ".atlas"} or _looks_like_spine_json(path):
        return SPINE_KIND
    if _is_mmd_model_path(path):
        return MMD_KIND
    if suffix == ".vrm":
        return VRM_KIND
    return "unknown"


def _is_mmd_model_path(path: Path) -> bool:
    suffix = path.suffix.casefold()
    return suffix in {".pmx", ".pmd"} or path.name.casefold().endswith(".pbx.json")


def _nearby_mmd_motions(root: Path, model_path: Path, vmd_paths: list[Path]) -> list[Path]:
    same_dir = [path for path in vmd_paths if path.parent == model_path.parent]
    rows = same_dir or vmd_paths
    rows = [path.expanduser().resolve() for path in rows if path.is_file()]
    rows.sort(key=lambda path: (0 if path.parent == model_path.parent else 1, _safe_relative(path, root).casefold()))
    return rows


def _is_spine_candidate(path: Path) -> bool:
    name = path.name.casefold()
    suffix = path.suffix.casefold()
    if suffix == ".skel" or suffix == ".atlas":
        return True
    if suffix != ".json" and not name.endswith(".skel.json"):
        return False
    if name.endswith(_LIVE2D_MODEL_SUFFIX) or any(name.endswith(suffix) for suffix in _LIVE2D_JSON_SUFFIXES):
        return False
    if name.endswith(".pbx.json"):
        return False
    return _looks_like_spine_json(path)


def _looks_like_spine_json(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:8192]
    except Exception:
        return False
    return '"bones"' in head or '"skeleton"' in head or '"slots"' in head


def _spine_skin_names(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        return sorted(str(key) for key in value.keys()) or ["default"]
    if isinstance(value, list):
        names: list[str] = []
        for row in value:
            if isinstance(row, Mapping):
                names.append(str(row.get("name") or "default"))
            elif row:
                names.append(str(row))
        return sorted(set(names)) or ["default"]
    return ["default"]


def _thumbnail_svg(record: Mapping[str, Any], *, size: int) -> str:
    kind = str(record.get("kind") or "?").upper()
    title = html.escape(str(record.get("display_name") or kind)[:18])
    render = record.get("render") if isinstance(record.get("render"), Mapping) else {}
    status = html.escape(str(render.get("status") or "unknown")[:22])
    colors = {
        LIVE2D_KIND: ("#252044", "#8f7cff"),
        SPINE_KIND: ("#2a1f16", "#f0a060"),
        MMD_KIND: ("#2b1724", "#ff6fae"),
        VRM_KIND: ("#241a32", "#b06bff"),
    }
    bg, fg = colors.get(str(record.get("kind") or ""), ("#20242a", "#aeb6c4"))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" rx="12" fill="{bg}"/>
  <rect x="6" y="6" width="{size - 12}" height="{size - 12}" rx="10" fill="none" stroke="{fg}" stroke-opacity="0.55"/>
  <circle cx="{size // 2}" cy="{size // 2 - 10}" r="{max(12, size // 7)}" fill="{fg}" fill-opacity="0.35"/>
  <path d="M {size // 2} {size // 2 + 4} L {size // 2 - 26} {size - 34} L {size // 2 + 26} {size - 34} Z" fill="{fg}" fill-opacity="0.22"/>
  <text x="{size // 2}" y="24" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="700" fill="#ffffff">{kind}</text>
  <text x="{size // 2}" y="{size - 20}" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="10" fill="#f4f6fa">{title}</text>
  <text x="{size // 2}" y="{size - 8}" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="8" fill="#bfc6d1">{status}</text>
</svg>
"""


__all__ = [
    "CHARACTER_ASSET_HUB_SCHEMA",
    "CHARACTER_ASSET_RECORD_SCHEMA",
    "CHARACTER_ASSET_THUMBNAIL_SCHEMA",
    "build_character_asset_timeline_add",
    "scan_character_asset_folder",
    "simulate_character_asset_hub_user_flow",
    "summarize_character_asset_hub",
    "write_character_asset_hub_thumbnails",
]
