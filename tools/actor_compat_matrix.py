"""Build a Live2D/Spine compatibility matrix for local model corpora.

This is the fast preflight layer before expensive preview/render QA. It scans
real model folders, checks dependency completeness, and can optionally run the
Spine parser. Rendering remains in ``tools/test_spine_resources.py`` because
that path needs OpenGL/Pillow work and is slower.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


_LIVE2D_RENDER_REQUIRED_DEP_KINDS = {"live2d_moc", "live2d_texture"}
_RISK_SCORE = {"high": 5, "medium": 3, "low": 1}


def _find_atlas(spine_path: Path) -> Path | None:
    exact = spine_path.with_suffix(".atlas")
    if exact.exists():
        return exact
    stem = spine_path.with_suffix("")
    for candidate in (
        spine_path.parent / f"{stem.name}.atlas",
        spine_path.parent / f"{stem.name.replace('_ske', '')}.atlas",
    ):
        if candidate.exists():
            return candidate
    atlases = sorted(spine_path.parent.glob("*.atlas"))
    return atlases[0] if atlases else None


def _looks_like_spine_json(path: Path) -> bool:
    if path.suffix.lower() != ".json":
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:2048]
    except Exception:
        return False
    return '"bones"' in head or '"skeleton"' in head or '"slots"' in head


def _preferred_spine_model_path(path: Path) -> Path:
    if path.suffix.lower() != ".skel":
        return path
    json_peer = path.with_suffix(".json")
    if json_peer.exists() and _looks_like_spine_json(json_peer):
        return json_peer
    return path


def find_spine_models(roots: Iterable[Path | str], *, limit: int = 0) -> list[Path]:
    models: list[Path] = []
    seen: set[Path] = set()

    def _append(path: Path) -> bool:
        path = _preferred_spine_model_path(path)
        if path in seen:
            return False
        seen.add(path)
        models.append(path)
        return limit > 0 and len(models) >= int(limit)

    for raw_root in roots:
        root = Path(raw_root)
        if root.is_file():
            if root.suffix.lower() == ".skel" or _looks_like_spine_json(root):
                if _append(root):
                    return sorted(models)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*.skel"):
            if _append(path):
                return sorted(models)
        for path in root.rglob("*.json"):
            if _looks_like_spine_json(path) and _append(path):
                return sorted(models)
    return sorted(models)


def find_live2d_models(roots: Iterable[Path | str], *, limit: int = 0) -> list[Path]:
    models: list[Path] = []
    seen: set[Path] = set()

    def _append(path: Path) -> bool:
        if path in seen:
            return False
        seen.add(path)
        models.append(path)
        return limit > 0 and len(models) >= int(limit)

    for raw_root in roots:
        root = Path(raw_root)
        if root.is_file() and root.name.lower().endswith(".model3.json"):
            if _append(root):
                return sorted(models)
        elif root.exists():
            for path in root.rglob("*.model3.json"):
                if _append(path):
                    return sorted(models)
    return sorted(models)


def audit_spine_model(path: Path | str, *, parse: bool = False) -> dict[str, Any]:
    from tools.qa_project_audit import _spine_dependency_rows

    model = Path(path)
    atlas = _find_atlas(model)
    clip = {
        "skel_path": str(model),
        "atlas_path": str(atlas or ""),
        "duration_ms": 1000,
        "anim_name": "compat",
    }
    dependencies = _spine_dependency_rows(clip)
    missing = [dep for dep in dependencies if not dep.get("exists")]
    row: dict[str, Any] = {
        "kind": "spine",
        "path": str(model),
        "exists": model.exists(),
        "atlas": str(atlas or ""),
        "atlas_exists": bool(atlas and atlas.exists()),
        "dependencies": dependencies,
        "missing_dependencies": missing,
        "parser_checked": bool(parse),
        "parser_ok": None,
        "parser_error": "",
        "feature_flags": [],
        "risk_codes": [],
    }
    feature_info = _spine_static_feature_info(model, atlas)
    row.update(feature_info)
    if model.suffix.lower() == ".skel":
        try:
            from app.spine_editor.spine_json_parser import detect_spine_binary_version

            row["version"] = detect_spine_binary_version(model)
        except Exception:
            row["version"] = ""
    if parse:
        try:
            from app.spine_editor.spine_json_parser import load_spine_file

            skel = load_spine_file(str(model))
            row["parser_ok"] = True
            row["bones"] = len(getattr(skel, "bones", []) or [])
            row["slots"] = len(getattr(skel, "slots", []) or [])
            row["animations"] = len(getattr(skel, "animations", {}) or {})
            parsed_features = _spine_parsed_feature_info(skel)
            row["feature_flags"] = sorted(set(row.get("feature_flags", [])) | set(parsed_features.get("feature_flags", [])))
            row["risk_codes"] = sorted(set(row.get("risk_codes", [])) | set(parsed_features.get("risk_codes", [])))
            row["mesh_count"] = max(int(row.get("mesh_count", 0) or 0), int(parsed_features.get("mesh_count", 0) or 0))
            row["weighted_mesh_count"] = max(
                int(row.get("weighted_mesh_count", 0) or 0),
                int(parsed_features.get("weighted_mesh_count", 0) or 0),
            )
            row["skin_count"] = max(int(row.get("skin_count", 0) or 0), int(parsed_features.get("skin_count", 0) or 0))
        except Exception as exc:
            row["parser_ok"] = False
            row["parser_error"] = f"{type(exc).__name__}: {exc}"
    row["ok"] = bool(
        row["exists"]
        and row["atlas_exists"]
        and not missing
        and (row["parser_ok"] is not False)
    )
    return row


def audit_live2d_model(path: Path | str) -> dict[str, Any]:
    from tools.qa_project_audit import _live2d_dependency_rows

    model = Path(path)
    dependencies = _live2d_dependency_rows({"model_path": str(model)})
    missing = [dep for dep in dependencies if not dep.get("exists")]
    required_missing = [
        dep for dep in missing
        if str(dep.get("kind") or "") in _LIVE2D_RENDER_REQUIRED_DEP_KINDS
    ]
    optional_missing = [
        dep for dep in missing
        if str(dep.get("kind") or "") not in _LIVE2D_RENDER_REQUIRED_DEP_KINDS
    ]
    row: dict[str, Any] = {
        "kind": "live2d",
        "path": str(model),
        "exists": model.exists(),
        "dependencies": dependencies,
        "missing_dependencies": missing,
        "required_missing_dependencies": required_missing,
        "optional_missing_dependencies": optional_missing,
        "texture_count": sum(1 for dep in dependencies if dep.get("kind") == "live2d_texture"),
        "motion_count": sum(1 for dep in dependencies if dep.get("kind") == "live2d_motion"),
        "feature_flags": [],
        "risk_codes": [],
    }
    row.update(_live2d_static_feature_info(model))
    row["ok"] = bool(row["exists"] and not required_missing)
    return row


_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1, "none": 0, "": 0}


def _root_relative_family(path: Path, roots: Iterable[Path | str]) -> str:
    """Return a stable corpus family label for grouping QA failures."""
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path
    best_rel: Path | None = None
    for raw_root in roots:
        root = Path(raw_root)
        try:
            rel = resolved.relative_to(root.resolve())
        except Exception:
            continue
        if best_rel is None or len(rel.parts) < len(best_rel.parts):
            best_rel = rel
    if best_rel is None:
        parent = path.parent.name or path.name
        return parent or "unknown"
    parts = best_rel.parts
    if len(parts) >= 2 and Path(parts[1]).suffix:
        return parts[0]
    if len(parts) >= 2:
        return "/".join(parts[:2])
    if len(parts) == 1:
        return parts[0]
    return "root"


def _dependency_counts(row: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for dep in row.get("dependencies") or []:
        kind = str(dep.get("kind") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def load_known_failures(path: Path | str | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    source = Path(path)
    if not source.exists():
        return []
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("known_failures", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _norm_match_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lower().strip()


def _known_path_matches(row_path: str, expected: str) -> bool:
    row_path = _norm_match_path(row_path)
    expected = _norm_match_path(expected)
    return bool(expected and (row_path == expected or row_path.endswith(expected)))


def _known_failure_matches(row: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    row_kind = str(row.get("kind") or "")
    row_path = str(row.get("path") or "")
    row_codes = {str(code) for code in row.get("issue_codes") or []}
    for entry in entries:
        kind = str(entry.get("kind") or "")
        if kind and kind != row_kind:
            continue
        expected_path = str(entry.get("path") or entry.get("path_suffix") or "")
        if expected_path and not _known_path_matches(row_path, expected_path):
            continue
        expected_codes = {str(code) for code in entry.get("issue_codes") or []}
        if expected_codes and row_codes.isdisjoint(expected_codes):
            continue
        return entry
    return None


def _apply_known_failures(rows: list[dict[str, Any]], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not entries:
        return rows
    out: list[dict[str, Any]] = []
    for row in rows:
        row = dict(row)
        match = _known_failure_matches(row, entries)
        if match is not None and not bool(row.get("ok")):
            row["known_failure"] = {
                "id": str(match.get("id") or ""),
                "reason": str(match.get("reason") or ""),
                "expires": str(match.get("expires") or ""),
            }
            row["quarantined"] = True
        out.append(row)
    return out


def _missing_dependency_kinds(row: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for dep in row.get("missing_dependencies") or []:
        kind = str(dep.get("kind") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _risk(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _append_unique(rows: list[str], value: str) -> None:
    if value and value not in rows:
        rows.append(value)


def _spine_skin_attachment_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    skins = data.get("skins", {})
    rows: list[dict[str, Any]] = []
    if isinstance(skins, list):
        for skin in skins:
            attachments = _as_dict(_as_dict(skin).get("attachments"))
            for slot_name, slot_attachments in attachments.items():
                for attach_name, attach in _as_dict(slot_attachments).items():
                    attach_row = dict(_as_dict(attach))
                    attach_row["_slot"] = str(slot_name)
                    attach_row["_name"] = str(attach_name)
                    rows.append(attach_row)
    elif isinstance(skins, dict):
        for _skin_name, slots in skins.items():
            for slot_name, slot_attachments in _as_dict(slots).items():
                for attach_name, attach in _as_dict(slot_attachments).items():
                    attach_row = dict(_as_dict(attach))
                    attach_row["_slot"] = str(slot_name)
                    attach_row["_name"] = str(attach_name)
                    rows.append(attach_row)
    return rows


def _spine_json_skin_count(data: dict[str, Any]) -> int:
    skins = data.get("skins", {})
    if isinstance(skins, list):
        return len(skins)
    if isinstance(skins, dict):
        return len(skins)
    return 0


def _spine_mesh_is_weighted(attach: dict[str, Any]) -> bool:
    vertices = _as_list(attach.get("vertices"))
    uvs = _as_list(attach.get("uvs"))
    n_verts = len(uvs) // 2
    if not vertices or n_verts <= 0:
        return False
    return len(vertices) > 2 * n_verts


def _spine_static_feature_info(model: Path, atlas: Path | None) -> dict[str, Any]:
    feature_flags: list[str] = []
    risk_codes: list[str] = []
    counts: Counter[str] = Counter()
    version = ""
    if model.suffix.lower() == ".skel":
        _append_unique(feature_flags, "spine_binary")
        try:
            from app.spine_editor.spine_json_parser import detect_spine_binary_version

            version = detect_spine_binary_version(model)
        except Exception:
            version = ""
        if not version:
            _append_unique(risk_codes, "spine_binary_version_unknown")
        else:
            try:
                major_minor = tuple(int(part) for part in version.split(".")[:2])
            except Exception:
                major_minor = ()
            if len(major_minor) >= 2 and major_minor >= (4, 2):
                _append_unique(risk_codes, "spine_binary_42_plus")
    if atlas and atlas.exists():
        try:
            from app.spine_editor.spine_json_parser import atlas_is_pma, load_atlas_pages

            pages = load_atlas_pages(str(atlas))
            counts["atlas_pages"] = len(pages)
            if len(pages) > 1:
                _append_unique(feature_flags, "multi_page_atlas")
                _append_unique(risk_codes, "spine_multi_page_atlas")
            if atlas_is_pma(str(atlas)):
                _append_unique(feature_flags, "premultiplied_alpha_atlas")
        except Exception:
            pass
    if model.suffix.lower() == ".json":
        try:
            data = json.loads(model.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        skeleton = _as_dict(data.get("skeleton"))
        version = str(skeleton.get("spine") or skeleton.get("version") or version)
        counts["bones"] = len(_as_list(data.get("bones")))
        counts["slots"] = len(_as_list(data.get("slots")))
        animations = _as_dict(data.get("animations"))
        counts["animations"] = len(animations)
        counts["skins"] = _spine_json_skin_count(data)
        if counts["skins"] > 1:
            _append_unique(feature_flags, "multi_skin")
            _append_unique(risk_codes, "spine_multi_skin")
        if counts["bones"] >= 150:
            _append_unique(risk_codes, "spine_many_bones")
        if counts["slots"] >= 200:
            _append_unique(risk_codes, "spine_many_slots")
        if counts["animations"] <= 0:
            _append_unique(risk_codes, "spine_no_animation")
        if data.get("events"):
            _append_unique(feature_flags, "events")
            _append_unique(risk_codes, "spine_events")
        constraint_keys = ("ik", "transform", "path", "physics", "constraints")
        if any(data.get(key) for key in constraint_keys):
            _append_unique(feature_flags, "constraints")
            _append_unique(risk_codes, "spine_constraints")
        for attach in _spine_skin_attachment_rows(data):
            atype = str(attach.get("type") or "region").lower()
            if atype in {"mesh", "linkedmesh"} or attach.get("triangles") or attach.get("vertices"):
                counts["mesh"] += 1
                _append_unique(feature_flags, "mesh")
                if _spine_mesh_is_weighted(attach):
                    counts["weighted_mesh"] += 1
                    _append_unique(feature_flags, "weighted_mesh")
                    _append_unique(risk_codes, "spine_weighted_mesh")
                if atype == "linkedmesh":
                    counts["linked_mesh"] += 1
                    _append_unique(feature_flags, "linked_mesh")
                    _append_unique(risk_codes, "spine_linked_mesh")
            if atype == "clipping":
                counts["clipping"] += 1
                _append_unique(feature_flags, "clipping")
                _append_unique(risk_codes, "spine_clipping")
        if version:
            try:
                major_minor = tuple(int(part) for part in version.split(".")[:2])
            except Exception:
                major_minor = ()
            if len(major_minor) >= 2 and major_minor >= (4, 2):
                _append_unique(risk_codes, "spine_json_42_plus")
    return {
        "version": version,
        "feature_flags": sorted(feature_flags),
        "risk_codes": sorted(risk_codes),
        "atlas_page_count": int(counts.get("atlas_pages", 0)),
        "mesh_count": int(counts.get("mesh", 0)),
        "weighted_mesh_count": int(counts.get("weighted_mesh", 0)),
        "linked_mesh_count": int(counts.get("linked_mesh", 0)),
        "skin_count": int(counts.get("skins", 0)),
    }


def _spine_parsed_feature_info(skel: Any) -> dict[str, Any]:
    feature_flags: list[str] = []
    risk_codes: list[str] = []
    mesh_count = 0
    weighted_mesh_count = 0
    for skin in _as_dict(getattr(skel, "skins", {})).values():
        for slot_attachments in _as_dict(skin).values():
            for attach in _as_dict(slot_attachments).values():
                if getattr(attach, "mesh_triangles", None) or getattr(attach, "mesh_uvs", None):
                    mesh_count += 1
                    _append_unique(feature_flags, "mesh")
                    for vertex_weights in getattr(attach, "mesh_weights", []) or []:
                        if len(vertex_weights) > 1 or any(int(weight[0]) >= 0 for weight in vertex_weights):
                            weighted_mesh_count += 1
                            _append_unique(feature_flags, "weighted_mesh")
                            _append_unique(risk_codes, "spine_weighted_mesh")
                            break
    if getattr(skel, "ik_constraints", None):
        _append_unique(feature_flags, "constraints")
        _append_unique(risk_codes, "spine_constraints")
    if not getattr(skel, "animations", None):
        _append_unique(risk_codes, "spine_no_animation")
    return {
        "feature_flags": sorted(feature_flags),
        "risk_codes": sorted(risk_codes),
        "mesh_count": mesh_count,
        "weighted_mesh_count": weighted_mesh_count,
        "skin_count": len(_as_dict(getattr(skel, "skins", {}))),
    }


def _live2d_static_feature_info(model: Path) -> dict[str, Any]:
    feature_flags: list[str] = []
    risk_codes: list[str] = []
    counts: Counter[str] = Counter()
    moc3 = ""
    data: dict[str, Any] = {}
    if model.exists():
        try:
            data = json.loads(model.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    refs = _as_dict(data.get("FileReferences"))
    textures = _as_list(refs.get("Textures"))
    motions = _as_dict(refs.get("Motions"))
    expressions = _as_list(refs.get("Expressions"))
    counts["textures"] = len(textures)
    counts["motion_groups"] = len(motions)
    counts["motions"] = sum(len(_as_list(group)) for group in motions.values())
    counts["expressions"] = len(expressions)
    if textures:
        _append_unique(feature_flags, "textures")
    if counts["textures"] >= 4:
        _append_unique(feature_flags, "many_textures")
        _append_unique(risk_codes, "live2d_many_textures")
    if motions:
        _append_unique(feature_flags, "motions")
    if counts["motions"] <= 0:
        _append_unique(risk_codes, "live2d_no_motion_refs")
    elif counts["motions"] >= 20:
        _append_unique(feature_flags, "many_motions")
        _append_unique(risk_codes, "live2d_many_motions")
    if expressions:
        _append_unique(feature_flags, "expressions")
    for key, flag, risk in (
        ("Physics", "physics", "live2d_physics"),
        ("Pose", "pose", "live2d_pose"),
        ("DisplayInfo", "display_info", "live2d_display_info"),
        ("UserData", "user_data", "live2d_user_data"),
    ):
        if refs.get(key):
            _append_unique(feature_flags, flag)
            _append_unique(risk_codes, risk)
    hit_areas = _as_list(data.get("HitAreas"))
    if hit_areas:
        _append_unique(feature_flags, "hit_areas")
    if any(ord(ch) > 127 for ch in str(model)):
        _append_unique(feature_flags, "non_ascii_path")
        _append_unique(risk_codes, "live2d_non_ascii_path")
    try:
        from app.live2d.compat import moc3_version

        moc_raw = str(refs.get("Moc") or "")
        moc_path = model.parent / moc_raw if moc_raw else model
        moc3 = moc3_version(moc_path)
    except Exception:
        moc3 = ""
    if moc3:
        _append_unique(feature_flags, f"moc3_v{moc3}")
    return {
        "moc3_version": moc3,
        "feature_flags": sorted(feature_flags),
        "risk_codes": sorted(risk_codes),
        "motion_group_count": int(counts.get("motion_groups", 0)),
        "motion_count": int(counts.get("motions", 0)),
        "expression_count": int(counts.get("expressions", 0)),
        "hit_area_count": len(hit_areas),
    }


_RISK_MESSAGES: dict[str, dict[str, str]] = {
    "spine_binary_42_plus": {"severity": "high", "message": "Spine binary 4.2+ requires JSON export or newer runtime support."},
    "spine_binary_version_unknown": {"severity": "medium", "message": "Spine binary version could not be detected."},
    "spine_json_42_plus": {"severity": "medium", "message": "Spine JSON 4.2+ should stay in corpus for mesh/runtime regression checks."},
    "spine_weighted_mesh": {"severity": "medium", "message": "Weighted mesh deformation can expose renderer batching and vertex skinning bugs."},
    "spine_linked_mesh": {"severity": "medium", "message": "Linked meshes depend on parent skin topology resolution."},
    "spine_clipping": {"severity": "medium", "message": "Clipping attachments need explicit render QA coverage."},
    "spine_constraints": {"severity": "medium", "message": "IK/transform/path constraints can expose pose evaluation bugs."},
    "spine_multi_page_atlas": {"severity": "medium", "message": "Multi-page atlas assets can expose texture binding and batching bugs."},
    "spine_multi_skin": {"severity": "low", "message": "Multiple skins need skin selection and linked mesh coverage."},
    "spine_many_bones": {"severity": "low", "message": "High bone count stresses pose update performance."},
    "spine_many_slots": {"severity": "low", "message": "High slot count stresses draw ordering and batching."},
    "spine_events": {"severity": "low", "message": "Event timelines are parsed as compatibility metadata."},
    "spine_no_animation": {"severity": "low", "message": "No animation references; sample only covers static pose compatibility."},
    "live2d_many_textures": {"severity": "medium", "message": "Many texture pages can expose upload, path normalization, or GL limits."},
    "live2d_many_motions": {"severity": "medium", "message": "Large motion sets can expose motion loading and selection bugs."},
    "live2d_non_ascii_path": {"severity": "medium", "message": "Non-ASCII paths require runtime path normalization coverage."},
    "live2d_physics": {"severity": "low", "message": "Physics file should be covered by interaction/render QA."},
    "live2d_pose": {"severity": "low", "message": "Pose file should be covered by interaction/render QA."},
    "live2d_display_info": {"severity": "low", "message": "DisplayInfo metadata should remain parseable."},
    "live2d_user_data": {"severity": "low", "message": "UserData metadata should remain parseable."},
}


def _row_risks(row: dict[str, Any]) -> list[dict[str, str]]:
    return [
        _risk(code, spec["severity"], spec["message"])
        for code in row.get("risk_codes") or []
        if (spec := _RISK_MESSAGES.get(str(code)))
    ]


def _issue(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _row_issues(row: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    kind = str(row.get("kind") or "")
    if not row.get("exists"):
        issues.append(_issue("model_missing", "high", "model file is missing"))
    if kind == "spine":
        if not row.get("atlas_exists"):
            issues.append(_issue("spine_atlas_missing", "high", "Spine atlas file is missing"))
        if row.get("missing_dependencies"):
            issues.append(_issue(
                "spine_texture_missing",
                "high",
                f"{len(row.get('missing_dependencies') or [])} atlas texture reference(s) are missing",
            ))
        if row.get("parser_ok") is False:
            issues.append(_issue(
                "spine_parser_failed",
                "high",
                str(row.get("parser_error") or "Spine parser failed"),
            ))
        if row.get("parser_ok") is True and int(row.get("animations", 0) or 0) <= 0:
            issues.append(_issue("spine_no_animation", "medium", "Spine file parsed but has no animations"))
    elif kind == "live2d":
        if row.get("required_missing_dependencies"):
            issues.append(_issue(
                "live2d_dependency_missing",
                "high",
                f"{len(row.get('required_missing_dependencies') or [])} required model3 dependency reference(s) are missing",
            ))
        if row.get("optional_missing_dependencies"):
            issues.append(_issue(
                "live2d_optional_dependency_missing",
                "medium",
                f"{len(row.get('optional_missing_dependencies') or [])} optional model3 dependency reference(s) are missing",
            ))
        if int(row.get("texture_count", 0) or 0) <= 0:
            issues.append(_issue("live2d_no_texture_refs", "medium", "model3 has no texture references"))
        if int(row.get("motion_count", 0) or 0) <= 0:
            issues.append(_issue("live2d_no_motion_refs", "low", "model3 has no motion references"))
    return issues


def _row_severity(issues: list[dict[str, str]]) -> str:
    if not issues:
        return "none"
    return max(
        (str(issue.get("severity") or "") for issue in issues),
        key=lambda value: _SEVERITY_RANK.get(value, 0),
    )


def _risk_severity(risks: list[dict[str, str]]) -> str:
    if not risks:
        return "none"
    return max(
        (str(risk.get("severity") or "") for risk in risks),
        key=lambda value: _SEVERITY_RANK.get(value, 0),
    )


def _risk_score(risks: list[dict[str, str]]) -> int:
    return sum(_RISK_SCORE.get(str(risk.get("severity") or ""), 0) for risk in risks)


def _stress_tier(row: dict[str, Any], risk_score: int) -> str:
    if row.get("ok") is False:
        return "blocked"
    # NIKKE-style Spine samples commonly combine weighted mesh, constraints,
    # and multi-page atlases. That totals 9 with the current risk weights and
    # is already expensive enough to belong in the stress render set.
    if risk_score >= 9:
        return "stress"
    if risk_score >= 4:
        return "watch"
    return "standard"


def _recommendation(row: dict[str, Any], issues: list[dict[str, str]]) -> str:
    codes = {str(issue.get("code") or "") for issue in issues}
    if "model_missing" in codes:
        return "Restore or relink the model file before preview/export QA."
    if "spine_atlas_missing" in codes:
        return "Place the matching .atlas beside the Spine .skel/.json file or fix the atlas path."
    if "spine_texture_missing" in codes:
        return "Restore every texture page named in the Spine atlas before render QA."
    if "spine_parser_failed" in codes:
        return "Keep the sample in the corpus and reproduce with --parse-spine; parser support likely needs work."
    if "live2d_dependency_missing" in codes:
        return "Restore required model3 Moc/texture dependencies relative to the model3 file before render QA."
    if "live2d_optional_dependency_missing" in codes:
        return "Base render can continue, but restore optional model3 expression/physics/display/motion references before interaction QA."
    if "live2d_no_texture_refs" in codes:
        return "Check whether this is a nonstandard Live2D package; texture references are expected."
    if "live2d_no_motion_refs" in codes or "spine_no_animation" in codes:
        return "Usable as a static compatibility sample; add animated samples for motion QA."
    if row.get("ok"):
        return "Ready for render/nonblank QA."
    return "Inspect dependencies and parser output."


def _enrich_row(row: dict[str, Any], roots: Iterable[Path | str]) -> dict[str, Any]:
    out = dict(row)
    path = Path(str(out.get("path") or ""))
    issues = _row_issues(out)
    risks = _row_risks(out)
    risk_score = _risk_score(risks)
    out["family"] = _root_relative_family(path, roots)
    out["model_name"] = path.stem
    out["extension"] = path.suffix.lower()
    try:
        out["file_size"] = path.stat().st_size if path.exists() else 0
    except Exception:
        out["file_size"] = 0
    out["dependency_counts"] = _dependency_counts(out)
    out["missing_dependency_kinds"] = _missing_dependency_kinds(out)
    out["issues"] = issues
    out["issue_codes"] = [issue["code"] for issue in issues]
    out["severity"] = _row_severity(issues)
    out["risks"] = risks
    out["risk_codes"] = [risk["code"] for risk in risks]
    out["risk_severity"] = _risk_severity(risks)
    out["risk_score"] = risk_score
    out["stress_tier"] = _stress_tier(out, risk_score)
    out["recommendation"] = _recommendation(out, issues)
    return out


def _bucket_add(bucket: dict[str, int], row: dict[str, Any]) -> None:
    bucket["total"] = bucket.get("total", 0) + 1
    if row.get("quarantined"):
        bucket["quarantined"] = bucket.get("quarantined", 0) + 1
    elif row.get("ok"):
        bucket["ok"] = bucket.get("ok", 0) + 1
    else:
        bucket["failed"] = bucket.get("failed", 0) + 1
    severity = str(row.get("severity") or "none")
    bucket[severity] = bucket.get(severity, 0) + 1


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, dict[str, int]] = {}
    by_family: dict[str, dict[str, int]] = {}
    issue_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    feature_counts: Counter[str] = Counter()
    stress_tiers: Counter[str] = Counter()
    missing_dependency_counts: Counter[str] = Counter()
    for row in rows:
        kind = str(row.get("kind") or "unknown")
        _bucket_add(by_kind.setdefault(kind, {}), row)
        _bucket_add(by_family.setdefault(str(row.get("family") or "unknown"), {}), row)
        issue_counts.update(str(code) for code in row.get("issue_codes") or [])
        risk_counts.update(str(code) for code in row.get("risk_codes") or [])
        feature_counts.update(str(flag) for flag in row.get("feature_flags") or [])
        stress_tiers.update([str(row.get("stress_tier") or "standard")])
        for dep_kind, count in (row.get("missing_dependency_kinds") or {}).items():
            missing_dependency_counts[str(dep_kind)] += int(count)
    failed = [row for row in rows if not row.get("ok") and not row.get("quarantined")]
    quarantined = [row for row in rows if row.get("quarantined")]
    top_failures = sorted(
        failed,
        key=lambda row: (
            -_SEVERITY_RANK.get(str(row.get("severity") or ""), 0),
            str(row.get("family") or ""),
            str(row.get("model_name") or ""),
        ),
    )[:20]
    risky_rows = [row for row in rows if int(row.get("risk_score", 0) or 0) > 0]
    top_risks = sorted(
        risky_rows,
        key=lambda row: (
            -int(row.get("risk_score", 0) or 0),
            str(row.get("family") or ""),
            str(row.get("model_name") or ""),
        ),
    )[:20]
    return {
        "total": len(rows),
        "ok": sum(1 for row in rows if row.get("ok")),
        "failed": len(failed),
        "quarantined": len(quarantined),
        "by_kind": by_kind,
        "by_family": dict(sorted(by_family.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "risk_counts": dict(sorted(risk_counts.items())),
        "feature_counts": dict(sorted(feature_counts.items())),
        "stress_tiers": dict(sorted(stress_tiers.items())),
        "missing_dependency_counts": dict(sorted(missing_dependency_counts.items())),
        "top_failures": [
            {
                "kind": row.get("kind"),
                "family": row.get("family"),
                "model_name": row.get("model_name"),
                "severity": row.get("severity"),
                "issue_codes": row.get("issue_codes"),
                "path": row.get("path"),
                "recommendation": row.get("recommendation"),
            }
            for row in top_failures
        ],
        "known_failures": [
            {
                "kind": row.get("kind"),
                "family": row.get("family"),
                "model_name": row.get("model_name"),
                "severity": row.get("severity"),
                "issue_codes": row.get("issue_codes"),
                "path": row.get("path"),
                "known_failure": row.get("known_failure"),
            }
            for row in quarantined[:20]
        ],
        "top_risks": [
            {
                "kind": row.get("kind"),
                "family": row.get("family"),
                "model_name": row.get("model_name"),
                "risk_score": row.get("risk_score"),
                "risk_severity": row.get("risk_severity"),
                "risk_codes": row.get("risk_codes"),
                "feature_flags": row.get("feature_flags"),
                "stress_tier": row.get("stress_tier"),
                "path": row.get("path"),
                "recommendation": (
                    "Prioritize this passing model in render/animation QA because it exercises "
                    "high-risk actor features."
                ),
            }
            for row in top_risks
        ],
    }


def build_actor_compat_matrix(
    roots: Iterable[Path | str],
    *,
    parse_spine: bool = False,
    limit: int = 0,
    known_failures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    spine_models = find_spine_models(roots, limit=limit)
    live2d_models = find_live2d_models(roots, limit=limit)
    rows = [
        audit_spine_model(path, parse=parse_spine)
        for path in spine_models
    ] + [
        audit_live2d_model(path)
        for path in live2d_models
    ]
    rows = [_enrich_row(row, roots) for row in rows]
    rows = _apply_known_failures(rows, list(known_failures or []))
    summary = _summary(rows)
    return {
        "ok": summary["failed"] == 0,
        "roots": [str(Path(root)) for root in roots],
        "summary": summary,
        "rows": rows,
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="*", type=Path, default=[Path("resources")])
    parser.add_argument("--parse-spine", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--known-failures", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/actor_compat_matrix.json"))
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print only summary/top failures to stdout while still writing the full report.",
    )
    args = parser.parse_args()

    report = build_actor_compat_matrix(
        args.roots,
        parse_spine=args.parse_spine,
        limit=args.limit,
        known_failures=load_known_failures(args.known_failures),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.summary_only:
        print(json.dumps({
            "ok": report.get("ok"),
            "roots": report.get("roots"),
            "summary": report.get("summary"),
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {args.out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
