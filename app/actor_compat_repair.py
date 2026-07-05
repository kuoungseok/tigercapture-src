"""Non-destructive actor path repair and dependency diagnostics."""
from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from typing import Any


def _looks_like_spine_json(path: Path) -> bool:
    if path.suffix.lower() != ".json" and not path.name.lower().endswith(".skel.json"):
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    except Exception:
        return False
    return '"bones"' in head or '"skeleton"' in head or '"slots"' in head


def _spine_base_name(path: Path) -> str:
    name = path.name
    lower = name.lower()
    if lower.endswith(".skel.json"):
        return name[: -len(".skel.json")]
    return path.stem


def _resolve_spine_model_path(path: Path) -> Path:
    suffix = path.suffix.lower()
    if suffix == ".atlas":
        candidates = [
            path.with_suffix(".json"),
            path.with_suffix(".skel"),
            path.with_name(path.stem + ".skel.json"),
        ]
        try:
            candidates.extend(sorted(path.parent.glob("*.json")))
            candidates.extend(sorted(path.parent.glob("*.skel")))
        except Exception:
            pass
        for candidate in candidates:
            if candidate.is_file() and (
                candidate.suffix.lower() == ".skel" or _looks_like_spine_json(candidate)
            ):
                return candidate
        return path
    if suffix == ".skel":
        json_peer = path.with_suffix(".json")
        if json_peer.is_file() and _looks_like_spine_json(json_peer):
            return json_peer
    return path


def _find_spine_atlas(input_path: Path, model_path: Path) -> Path | None:
    if input_path.suffix.lower() == ".atlas" and input_path.is_file():
        return input_path
    base = _spine_base_name(model_path)
    candidates = [
        model_path.parent / f"{base}.atlas",
        model_path.with_suffix(".atlas"),
    ]
    if model_path.name.lower().endswith(".skel.json"):
        candidates.append(model_path.with_name(f"{base}.skel.atlas"))
    try:
        candidates.extend(sorted(model_path.parent.glob("*.atlas")))
    except Exception:
        pass
    seen: set[Path] = set()
    for candidate in candidates:
        key = candidate.resolve() if candidate.exists() else candidate
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            return candidate
    return None


def _spine_texture_pages(atlas_path: Path | None) -> list[str]:
    if atlas_path is None:
        return []
    try:
        from app.spine_editor.spine_json_parser import load_atlas_pages

        return [str(atlas_path.parent / page) for page in load_atlas_pages(str(atlas_path))]
    except Exception:
        return []


def _live2d_metadata(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    refs = payload.get("FileReferences") if isinstance(payload.get("FileReferences"), dict) else {}
    motions = refs.get("Motions") if isinstance(refs.get("Motions"), dict) else {}
    expressions = refs.get("Expressions") if isinstance(refs.get("Expressions"), list) else []
    return {
        "moc": str(refs.get("Moc") or ""),
        "textures": len(refs.get("Textures") or []) if isinstance(refs.get("Textures"), list) else 0,
        "motions": sum(len(rows) for rows in motions.values() if isinstance(rows, list)),
        "expressions": len(expressions),
        "physics": bool(refs.get("Physics")),
        "pose": bool(refs.get("Pose")),
    }


def repair_actor_model_path(kind: str, path: str) -> dict[str, Any]:
    """Return a best-effort loadable actor path without modifying source files."""
    raw_kind = str(kind or "").lower()
    source = Path(path)
    steps: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, Any] = {}
    repaired = source

    if raw_kind == "live2d":
        try:
            from app.live2d.compat import moc3_version, model_support_error, normalize_live2d_model_path

            normalized = normalize_live2d_model_path(source)
            if normalized:
                repaired = Path(normalized)
                if repaired != source:
                    steps.append("normalized Live2D Unity/bytes model into runtime Cubism model3.json")
            else:
                warnings.append("no Live2D model3.json could be resolved from source")
            support_error = model_support_error(repaired)
            if support_error:
                warnings.append(support_error)
            metadata.update(_live2d_metadata(repaired))
            metadata["moc3_version"] = moc3_version(repaired)
        except Exception as exc:
            warnings.append(f"Live2D compatibility repair failed: {type(exc).__name__}: {exc}")

    elif raw_kind == "spine":
        repaired = _resolve_spine_model_path(source)
        if repaired != source:
            steps.append(f"resolved Spine load file: {repaired.name}")
        atlas = _find_spine_atlas(source, repaired)
        if atlas is not None:
            metadata["atlas_path"] = str(atlas)
            metadata["atlas"] = atlas.name
            pages = _spine_texture_pages(atlas)
            metadata["texture_pages"] = pages
            missing_pages = [page for page in pages if not Path(page).exists()]
            if missing_pages:
                warnings.append(f"missing atlas texture page(s): {', '.join(Path(p).name for p in missing_pages[:4])}")
            try:
                from app.spine_editor.spine_json_parser import atlas_is_pma

                metadata["pma"] = bool(atlas_is_pma(str(atlas)))
            except Exception:
                metadata["pma"] = False
        else:
            warnings.append("matching Spine atlas was not found")
        if repaired.suffix.lower() == ".skel":
            try:
                from app.spine_editor.spine_json_parser import detect_spine_binary_version

                metadata["spine_binary_version"] = detect_spine_binary_version(repaired)
            except Exception:
                pass
        metadata["looks_like_json"] = bool(_looks_like_spine_json(repaired))

    else:
        warnings.append(f"unknown actor kind: {kind}")

    return {
        "ok": repaired.exists() and not any("could not be loaded safely" in w.lower() for w in warnings),
        "kind": raw_kind,
        "original_path": str(source),
        "path": str(repaired),
        "changed": str(repaired) != str(source),
        "steps": steps,
        "warnings": warnings,
        "metadata": metadata,
    }


def _dedupe(rows: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        text = str(row or "").strip()
        key = text.casefold()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def _warning_to_action(kind: str, warning: str) -> str:
    text = str(warning or "").casefold()
    if "matching spine atlas" in text or "atlas was not found" in text:
        return "Choose the matching .atlas file or place it next to the Spine .json/.skel file."
    if "missing atlas texture" in text or "texture page" in text:
        return "Copy the missing atlas texture PNG/WebP pages next to the .atlas file, then refresh Actor QA."
    if "no live2d model3" in text or "model3.json" in text:
        return "Select the .model3.json file or the Unity-export folder that contains the Cubism runtime files."
    if "could not be loaded safely" in text or "unsupported" in text:
        return "Convert the actor to a supported Cubism/Spine runtime version or quarantine it as a known failure."
    if "unknown actor kind" in text:
        return "Import the asset as either Live2D or Spine so the correct diagnostics can run."
    if str(kind or "").lower() == "spine":
        return "Open Actor QA Browser, inspect atlas/skin/slot diagnostics, then run render QA on this model."
    if str(kind or "").lower() == "live2d":
        return "Open Actor QA Browser, inspect MOC/texture/motion diagnostics, then run render QA on this model."
    return "Open Actor QA Browser and refresh compatibility/render diagnostics."


def actor_dependency_guidance(kind: str) -> dict[str, Any]:
    """Return optional dependency status for actor features that affect quality."""
    raw_kind = str(kind or "").lower()
    mediapipe_available = importlib.util.find_spec("mediapipe") is not None
    rows = []
    if raw_kind == "live2d":
        rows.append(
            {
                "id": "mediapipe_facemesh",
                "label": "MediaPipe FaceMesh",
                "available": mediapipe_available,
                "required": False,
                "feature": "face/eye/mouth mocap detail",
                "action": (
                    "Ready for detailed face, gaze, mouth, and blink parameters."
                    if mediapipe_available
                    else "Install/enable MediaPipe only if detailed face/eye/mouth mocap is needed; OpenCV fallback still works."
                ),
            }
        )
    return {
        "kind": raw_kind,
        "optional_dependencies": rows,
        "all_optional_ready": all(bool(row.get("available")) for row in rows) if rows else True,
    }


def actor_repair_guidance_report(
    kind: str,
    path: str,
    *,
    status_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return user-facing actor load guidance without mutating any files."""
    repair = repair_actor_model_path(kind, path)
    status = status_row if isinstance(status_row, dict) else {}
    warnings = [str(row) for row in repair.get("warnings", []) or [] if str(row)]
    issue_codes = [str(row) for row in status.get("issue_codes", []) or [] if str(row)]
    risk_codes = [str(row) for row in status.get("risk_codes", []) or [] if str(row)]
    severity = str(status.get("severity") or status.get("risk_severity") or ("ok" if repair.get("ok") else "high"))
    actions: list[str] = []
    for warning in warnings:
        actions.append(_warning_to_action(str(repair.get("kind") or kind), warning))
    if status.get("recommendation"):
        actions.append(str(status.get("recommendation")))
    if issue_codes:
        actions.append("Review issue codes in Actor QA Browser before claiming this model is supported.")
    if risk_codes:
        actions.append("Run animation/render sweep QA for this model because compatibility risk codes are present.")
    if not actions and repair.get("ok"):
        actions.append("Path repair found a loadable actor file. Run render QA before using it in release material.")
    dependency = actor_dependency_guidance(str(repair.get("kind") or kind))
    for row in dependency.get("optional_dependencies", []) or []:
        if isinstance(row, dict) and not row.get("available"):
            actions.append(str(row.get("action") or "Install optional actor dependency if this feature is needed."))
    blockers = []
    if not repair.get("ok"):
        blockers.append("load_path_not_ready")
    if severity in {"high", "fail"}:
        blockers.append("high_severity_actor_issue")
    claim_blockers = list(blockers)
    if warnings:
        claim_blockers.append("actor_dependency_warning")
    if issue_codes:
        claim_blockers.append("actor_issue_codes_present")
    return {
        "kind": str(repair.get("kind") or kind).lower(),
        "ok": bool(repair.get("ok")) and not blockers,
        "ready_for_release_claim": bool(repair.get("ok")) and not claim_blockers,
        "severity": severity,
        "blockers": _dedupe(blockers),
        "claim_blockers": _dedupe(claim_blockers),
        "original_path": repair.get("original_path"),
        "load_path": repair.get("path"),
        "path_changed": bool(repair.get("changed")),
        "steps": list(repair.get("steps") or []),
        "warnings": warnings,
        "issue_codes": issue_codes,
        "risk_codes": risk_codes,
        "metadata": dict(repair.get("metadata") or {}),
        "optional_dependency_status": dependency,
        "actions": _dedupe(actions),
        "claim_guard": [
            "Do not market this as all Unity/game-exported Live2D/Spine rigs compatible.",
            "Use corpus QA, render QA, and known-failure quarantine before release claims.",
        ],
    }
