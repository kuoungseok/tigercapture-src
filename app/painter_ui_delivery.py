"""General delivery adapters for Painter UI Designer documents."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_document import (
    UI_DELIVERY_TARGETS,
    normalize_ui_document,
    validate_ui_document,
)


_TARGET_CAPABILITIES: dict[str, dict[str, Any]] = {
    "asset_export": {
        "title": "Asset Export",
        "artifact_types": ["png", "webp", "svg", "density_variants"],
        "native_kinds": {"rectangle", "ellipse", "line", "path", "text", "image"},
        "material_kinds": set(),
        "baked_kinds": {"frame", "group", "button", "progress"},
    },
    "design_handoff": {
        "title": "Design Handoff",
        "artifact_types": ["design_document", "tokens", "components", "interactions"],
        "native_kinds": {
            "frame", "group", "rectangle", "ellipse", "line", "path", "text",
            "image", "button", "progress",
        },
        "material_kinds": set(),
        "baked_kinds": set(),
    },
    "review_prototype": {
        "title": "Review Prototype",
        "artifact_types": ["static_review_package"],
        "native_kinds": {
            "frame", "group", "rectangle", "ellipse", "line", "text", "image",
            "button", "progress",
        },
        "material_kinds": set(),
        "baked_kinds": {"path"},
    },
    "unreal_umg": {
        "title": "Unreal UMG",
        "artifact_types": ["widget_blueprint"],
        "native_kinds": {"frame", "group", "text", "image", "button", "progress"},
        "material_kinds": {"rectangle", "ellipse", "line", "path"},
        "baked_kinds": set(),
    },
}


def list_ui_delivery_profiles() -> dict[str, Any]:
    return {
        "schema": "tigerstudio.painter.ui.delivery_profiles.v1",
        "profiles": [
            {
                "id": target,
                "target": target,
                "title": _TARGET_CAPABILITIES[target]["title"],
                "artifact_types": list(
                    _TARGET_CAPABILITIES[target]["artifact_types"]
                ),
            }
            for target in UI_DELIVERY_TARGETS
        ],
    }


def classify_ui_object_delivery(
    value: Mapping[str, Any],
    target: str,
) -> dict[str, Any]:
    target_id = str(target or "").strip().casefold()
    if target_id not in _TARGET_CAPABILITIES:
        raise ValueError(f"Unknown Painter UI delivery target: {target}")
    obj = dict(value)
    kind = str(obj.get("kind") or "").strip().casefold()
    style = obj.get("style")
    style = style if isinstance(style, Mapping) else {}
    capabilities = _TARGET_CAPABILITIES[target_id]
    if target_id == "unreal_umg" and style.get("font_axes"):
        disposition = "blocked"
        reason = (
            "variable-font axes require an Unreal text bake path that is not "
            "available yet"
        )
    elif style.get("paint_layer_id"):
        disposition = "baked"
        reason = "Painter layer appearance requires a deterministic asset bake"
    elif (
        target_id == "unreal_umg"
        and any(style.get(key) for key in ("gradient", "mask", "material"))
    ):
        disposition = "material"
        reason = "represented by a generated or shared Unreal UI Material"
    elif kind in capabilities["native_kinds"]:
        disposition = "native"
        reason = "represented directly by the target"
    elif kind in capabilities["material_kinds"]:
        disposition = "material"
        reason = "represented through the target material adapter"
    elif kind in capabilities["baked_kinds"]:
        disposition = "baked"
        reason = "converted to a deterministic raster asset"
    else:
        disposition = "blocked"
        reason = "target adapter has no declared conversion"
    return {
        "object_id": str(obj.get("id") or ""),
        "name": str(obj.get("name") or kind or "UI Object"),
        "kind": kind,
        "target": target_id,
        "disposition": disposition,
        "display_disposition": disposition.title(),
        "reason": reason,
    }


def ui_object_delivery_statuses(
    value: Mapping[str, Any],
    object_id: str,
    *,
    normalize: bool = True,
) -> dict[str, Any]:
    # Read-only report: a caller that already holds canonical output should not
    # pay to re-derive the whole document for one object's statuses.
    document = (
        value
        if not normalize and isinstance(value, Mapping)
        else normalize_ui_document(value)
    )
    selected_id = str(object_id or "")
    obj = next(
        (row for row in document["objects"] if row["id"] == selected_id),
        None,
    )
    if obj is None:
        raise ValueError(f"Unknown Painter UI object: {object_id}")
    return {
        "schema": "tigerstudio.painter.ui.object_delivery_status.v1",
        "document_id": document["document_id"],
        "revision": document["revision"],
        "object_id": selected_id,
        "targets": [
            classify_ui_object_delivery(obj, target)
            for target in UI_DELIVERY_TARGETS
        ],
    }


def preflight_ui_delivery(
    value: Mapping[str, Any],
    target: str,
) -> dict[str, Any]:
    target_id = str(target or "").strip().casefold()
    if target_id not in _TARGET_CAPABILITIES:
        raise ValueError(f"Unknown Painter UI delivery target: {target}")
    document = normalize_ui_document(value)
    validation = validate_ui_document(document)
    capabilities = _TARGET_CAPABILITIES[target_id]
    rows: list[dict[str, Any]] = []
    counts = {"native": 0, "material": 0, "baked": 0, "blocked": 0}
    for obj in document["objects"]:
        status = classify_ui_object_delivery(obj, target_id)
        counts[status["disposition"]] += 1
        rows.append(status)
    blockers = list(validation["errors"])
    blockers.extend(
        f"blocked_object:{row['object_id']}"
        for row in rows
        if row["disposition"] == "blocked"
    )
    return {
        "schema": "tigerstudio.painter.ui.delivery_preflight.v2",
        "ok": not blockers,
        "target": target_id,
        "title": capabilities["title"],
        "document_id": document["document_id"],
        "revision": document["revision"],
        "counts": counts,
        "objects": rows,
        "blockers": blockers,
        "warnings": list(validation["warnings"]),
        "artifact_types": list(capabilities["artifact_types"]),
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def package_design_handoff(
    value: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    preflight = preflight_ui_delivery(document, "design_handoff")
    if not preflight["ok"]:
        return {**preflight, "artifacts": []}
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "design_document": root / "design_document.json",
        "tokens": root / "tokens.json",
        "components": root / "components.json",
        "interactions": root / "interactions.json",
    }
    _write_json(files["design_document"], document)
    _write_json(files["tokens"], document["tokens"])
    _write_json(files["components"], document["components"])
    _write_json(files["interactions"], document["interactions"])
    artifacts = [
        {
            "kind": kind,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for kind, path in files.items()
    ]
    manifest = {
        "schema": "tigerstudio.painter.ui.handoff_manifest.v1",
        "document_id": document["document_id"],
        "revision": document["revision"],
        "artboard_count": len(document["artboards"]),
        "object_count": len(document["objects"]),
        "artifacts": artifacts,
        "preflight": preflight,
    }
    manifest_path = root / "manifest.json"
    _write_json(manifest_path, manifest)
    artifacts.append(
        {
            "kind": "manifest",
            "path": str(manifest_path),
            "bytes": manifest_path.stat().st_size,
            "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        }
    )
    return {
        "schema": "tigerstudio.painter.ui.handoff_report.v1",
        "ok": True,
        "target": "design_handoff",
        "output_dir": str(root),
        "document_id": document["document_id"],
        "revision": document["revision"],
        "artifacts": artifacts,
        "preflight": preflight,
    }


__all__ = [
    "classify_ui_object_delivery",
    "list_ui_delivery_profiles",
    "package_design_handoff",
    "preflight_ui_delivery",
    "ui_object_delivery_statuses",
]
