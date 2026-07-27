"""Painter provider adapter for the shared TigerStudioUMG backend."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document
from app.painter_ui_responsive import resolve_ui_responsive_document


PAINTER_UMG_ADAPTER_SCHEMA = "tigerstudio.painter.ui.umg_adapter.v1"
TIGER_UMG_SCHEMA_VERSION = 3


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resource_id(path: Path, kind: str) -> str:
    key = f"{kind}:{path.resolve()}".encode("utf-8", errors="surrogatepass")
    return f"{kind}_{hashlib.sha256(key).hexdigest()[:20]}"


def _umg_kind(kind: str) -> str:
    return {
        "frame": "Group",
        "group": "Group",
        "text": "Text",
        "image": "Image",
        "button": "Button",
        "progress": "Image",
        "rectangle": "Image",
        "ellipse": "Image",
        "line": "Image",
        "path": "Image",
    }.get(kind, "Unsupported")


def painter_ui_to_umg_document(
    value: Mapping[str, Any],
    *,
    artboard_id: str = "",
) -> dict[str, Any]:
    source_document = normalize_ui_document(value)
    document = resolve_ui_responsive_document(source_document)
    selected_artboard_id = str(artboard_id or document["active_artboard_id"])
    artboard = next(
        (
            row
            for row in document["artboards"]
            if row["id"] == selected_artboard_id
        ),
        None,
    )
    if artboard is None:
        raise ValueError(f"Painter UI artboard not found: {selected_artboard_id}")
    included_ids = {
        row["id"]
        for row in document["objects"]
        if row["artboard_id"] == selected_artboard_id
    }
    resources: dict[str, dict[str, Any]] = {}
    layers: list[dict[str, Any]] = []
    for row in sorted(
        (
            row
            for row in document["objects"]
            if row["artboard_id"] == selected_artboard_id
        ),
        key=lambda item: (item["z_index"], item["id"]),
    ):
        style = dict(row.get("style") or {})
        content = dict(row.get("content") or {})
        kind = _umg_kind(str(row["kind"]))
        disposition = "Native" if kind != "Unsupported" else "Blocked"
        asset_id = ""
        source_path = str(
            content.get("source_path") or content.get("path") or ""
        )
        if row["kind"] == "image" and source_path:
            path = Path(source_path).expanduser()
            asset_id = _resource_id(path, "texture")
            resources[asset_id] = {
                "Id": asset_id,
                "Kind": "texture",
                "SourcePath": str(path),
                "DestinationName": f"TS_{asset_id}",
                "ContentHash": _hash_file(path) if path.is_file() else "",
                "SettingsJson": "{}",
            }
        payload = {
            "source_kind": row["kind"],
            "clip_content": bool(row.get("clip_content", False)),
            "source_params": {
                "shape": (
                    "ellipse" if row["kind"] == "ellipse" else "rectangle"
                ),
                "radius": float(style.get("radius", 0.0) or 0.0),
                "stroke": str(style.get("stroke") or "#00000000"),
                "stroke_width": float(
                    style.get("stroke_width", 0.0) or 0.0
                ),
            },
            "text": str(content.get("text") or row["name"]),
            "fill": str(
                style.get("text_color")
                if row["kind"] == "text"
                else style.get("fill")
                or "#FFFFFFFF"
            ),
            "font_size": float(style.get("font_size", 16.0) or 16.0),
            "painter_conversion": (
                "native"
                if row["kind"]
                in {"frame", "group", "text", "image", "button"}
                else "converted_to_slate_image"
            ),
            "token_bindings": dict(row.get("token_bindings") or {}),
            "accessibility": dict(row.get("accessibility") or {}),
            "umg_mapping": (
                "native_or_converted" if disposition == "Native"
                else "blocked_preflight"
            ),
            "umg_block_reasons": (
                [] if disposition == "Native" else ["unsupported_object_kind"]
            ),
        }
        layers.append(
            {
                "Id": row["id"],
                "ParentId": (
                    row["parent_id"]
                    if row["parent_id"] in included_ids
                    else ""
                ),
                "Name": row["name"],
                "Kind": kind,
                "Disposition": disposition,
                "Position": {
                    "X": float(row["x"]) + float(row["width"]) * 0.5,
                    "Y": float(row["y"]) + float(row["height"]) * 0.5,
                },
                "Size": {
                    "X": float(row["width"]),
                    "Y": float(row["height"]),
                },
                "Scale": {"X": 1.0, "Y": 1.0},
                "Anchor": {
                    "X": float(row.get("pivot_x", 0.5)),
                    "Y": float(row.get("pivot_y", 0.5)),
                },
                "RotationDegrees": float(row["rotation"]),
                "Opacity": float(row["opacity"]),
                "AssetId": asset_id,
                "PayloadJson": json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        )
    interactions = []
    for row in document["interactions"]:
        if row["source_object_id"] not in included_ids:
            continue
        parameters = dict(row.get("parameters") or {})
        interactions.append(
            {
                "ComponentId": row["source_object_id"],
                "Trigger": row["trigger"],
                "Actions": [
                    {
                        "Type": row["action"],
                        "TargetId": (
                            row["target_object_id"]
                            or row["target_artboard_id"]
                            or row["component_id"]
                        ),
                        "Name": row["name"],
                        "ResourceId": "",
                        "ResourcePath": str(parameters.get("uri") or ""),
                        "ValueJson": json.dumps(
                            parameters.get("value"),
                            ensure_ascii=False,
                        ),
                        "ParametersJson": json.dumps(
                            parameters,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    }
                ],
            }
        )
    return {
        "SchemaVersion": TIGER_UMG_SCHEMA_VERSION,
        "Provider": "painter",
        "DocumentId": (
            f"painter-{document['document_id']}-{selected_artboard_id}"
        ),
        "Revision": int(document["revision"]),
        "Width": int(artboard["width"]),
        "Height": int(artboard["height"]),
        "FrameRate": 30.0,
        "DurationMilliseconds": 1000,
        "Resources": list(resources.values()),
        "Layers": layers,
        "Animations": [],
        "Interactions": interactions,
        "PainterSource": {
            "Schema": PAINTER_UMG_ADAPTER_SCHEMA,
            "DocumentId": document["document_id"],
            "ArtboardId": selected_artboard_id,
            "Revision": document["revision"],
        },
    }


def preflight_painter_umg(
    value: Mapping[str, Any],
    *,
    artboard_id: str = "",
) -> dict[str, Any]:
    document = painter_ui_to_umg_document(value, artboard_id=artboard_id)
    counts = {"Native": 0, "Material": 0, "Baked": 0, "Blocked": 0}
    blockers: list[dict[str, Any]] = []
    for row in document["Layers"]:
        disposition = str(row["Disposition"] or "Blocked")
        counts[disposition] = counts.get(disposition, 0) + 1
        payload = json.loads(str(row.get("PayloadJson") or "{}"))
        if disposition == "Blocked":
            blockers.append(
                {
                    "object_id": row["Id"],
                    "name": row["Name"],
                    "reasons": list(payload.get("umg_block_reasons") or []),
                }
            )
    missing_resources = [
        row["SourcePath"]
        for row in document["Resources"]
        if not Path(str(row["SourcePath"])).expanduser().is_file()
    ]
    return {
        "schema": PAINTER_UMG_ADAPTER_SCHEMA,
        "ok": not blockers and not missing_resources,
        "document_id": document["DocumentId"],
        "artboard_id": document["PainterSource"]["ArtboardId"],
        "counts": counts,
        "blockers": blockers,
        "missing_resources": missing_resources,
        "interaction_count": len(document["Interactions"]),
        "resource_count": len(document["Resources"]),
    }


def package_painter_umg(
    value: Mapping[str, Any],
    output_dir: str | Path,
    *,
    artboard_id: str = "",
) -> dict[str, Any]:
    document = painter_ui_to_umg_document(value, artboard_id=artboard_id)
    root = Path(output_dir).expanduser().resolve()
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    packaged = json.loads(json.dumps(document, ensure_ascii=False))
    missing: list[str] = []
    copied: list[str] = []
    for row in packaged["Resources"]:
        source = Path(str(row["SourcePath"])).expanduser()
        if not source.is_file():
            missing.append(str(source))
            continue
        destination = assets / f"{row['Id']}{source.suffix.lower()}"
        shutil.copy2(source, destination)
        row["SourcePath"] = destination.relative_to(root).as_posix()
        row["ContentHash"] = _hash_file(destination)
        copied.append(str(destination))
    document_path = root / "tiger_umg_document.json"
    document_path.write_text(
        json.dumps(packaged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    preflight = preflight_painter_umg(value, artboard_id=artboard_id)
    return {
        "ok": preflight["ok"] and not missing,
        "document_path": str(document_path),
        "asset_count": len(packaged["Resources"]),
        "copied": copied,
        "missing": missing,
        "document": packaged,
        "preflight": preflight,
    }


def generate_painter_umg(
    value: Mapping[str, Any],
    *,
    project_path: str | Path,
    output_dir: str | Path,
    artboard_id: str = "",
    destination_root: str = "/Game/TigerStudio/Generated",
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    package = package_painter_umg(
        value,
        output_dir,
        artboard_id=artboard_id,
    )
    if not package["ok"]:
        return package
    from app.unreal_umg_workflow import run_unreal_umg_generation

    generated = run_unreal_umg_generation(
        project_path,
        package["document_path"],
        destination_root=destination_root,
        timeout_seconds=timeout_seconds,
    )
    return {**generated, "package": package}


__all__ = [
    "PAINTER_UMG_ADAPTER_SCHEMA",
    "TIGER_UMG_SCHEMA_VERSION",
    "generate_painter_umg",
    "package_painter_umg",
    "painter_ui_to_umg_document",
    "preflight_painter_umg",
]
