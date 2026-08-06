"""Safe, UI-free attachment of baked flipbooks to Painter UI documents."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.painter_ui_flipbook_bake import (
    PAINTER_UI_FLIPBOOK_BAKE_SCHEMA,
    PainterUIFlipbookBakeResult,
)
from app.unreal_umg_flipbook import (
    TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION,
    normalize_umg_flipbook,
    validate_umg_flipbook_record,
)


PAINTER_UI_FLIPBOOK_ATTACHMENT_SCHEMA = (
    "tigerstudio.painter.flipbook_bake_attachment.v1"
)
PAINTER_UI_FLIPBOOK_ATTACH_REPORT_SCHEMA = (
    "tigerstudio.painter.flipbook_attach_report.v1"
)
PAINTER_UI_FLIPBOOK_OBJECT_KINDS = frozenset({"image", "rectangle"})


class PainterUIFlipbookAttachError(ValueError):
    """A refused document attachment with stable machine-readable reasons."""

    def __init__(
        self,
        block_reasons: str | Sequence[str],
        *,
        detail: str = "",
    ) -> None:
        reasons = (
            [block_reasons]
            if isinstance(block_reasons, str)
            else [str(reason) for reason in block_reasons]
        )
        self.block_reasons = tuple(sorted(set(reasons)))
        self.detail = str(detail or "")
        message = ", ".join(self.block_reasons)
        if self.detail:
            message = f"{message}: {self.detail}"
        super().__init__(message)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: object, *, newline: bool) -> bytes:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_bake_manifest_invalid",
            detail=f"{type(exc).__name__}:{exc}",
        ) from exc
    if newline:
        encoded += "\n"
    return encoded.encode("utf-8")


def _verified_file(
    value: Path,
    *,
    missing_reason: str,
    not_file_reason: str,
    read_reason: str,
) -> tuple[Path, bytes]:
    path = Path(value).expanduser()
    try:
        resolved = path.resolve(strict=False)
    except OSError as exc:
        raise PainterUIFlipbookAttachError(
            read_reason,
            detail=f"{path}:{type(exc).__name__}:{exc}",
        ) from exc
    if not resolved.exists():
        raise PainterUIFlipbookAttachError(missing_reason, detail=str(resolved))
    if not resolved.is_file():
        raise PainterUIFlipbookAttachError(not_file_reason, detail=str(resolved))
    try:
        return resolved, resolved.read_bytes()
    except OSError as exc:
        raise PainterUIFlipbookAttachError(
            read_reason,
            detail=f"{resolved}:{type(exc).__name__}:{exc}",
        ) from exc


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _finite_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _verified_bake(
    bake_result: PainterUIFlipbookBakeResult,
) -> dict[str, Any]:
    if not isinstance(bake_result, PainterUIFlipbookBakeResult):
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_bake_result_invalid"
        )
    atlas_path, atlas_bytes = _verified_file(
        bake_result.atlas_path,
        missing_reason="flipbook_attach_atlas_missing",
        not_file_reason="flipbook_attach_atlas_not_file",
        read_reason="flipbook_attach_atlas_read_failed",
    )
    manifest_path, manifest_bytes = _verified_file(
        bake_result.manifest_path,
        missing_reason="flipbook_attach_manifest_missing",
        not_file_reason="flipbook_attach_manifest_not_file",
        read_reason="flipbook_attach_manifest_read_failed",
    )
    expected_manifest_bytes = _canonical_json_bytes(
        bake_result.manifest,
        newline=True,
    )
    if manifest_bytes != expected_manifest_bytes:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_manifest_hash_mismatch",
            detail=str(manifest_path),
        )
    try:
        disk_manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_manifest_invalid",
            detail=f"{manifest_path}:{type(exc).__name__}:{exc}",
        ) from exc
    if disk_manifest != bake_result.manifest:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_manifest_content_mismatch"
        )

    manifest = _mapping(disk_manifest)
    if str(manifest.get("schema") or "") != PAINTER_UI_FLIPBOOK_BAKE_SCHEMA:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_manifest_schema_unsupported"
        )
    try:
        manifest_document_version = int(
            manifest.get("document_schema_version", 0) or 0
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_document_schema_unsupported"
        ) from exc
    if manifest_document_version != TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_document_schema_unsupported"
        )
    atlas_metadata = _mapping(manifest.get("atlas"))
    expected_atlas_hash = str(atlas_metadata.get("sha256") or "").casefold()
    atlas_hash = _sha256(atlas_bytes)
    if not expected_atlas_hash or atlas_hash != expected_atlas_hash:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_atlas_hash_mismatch",
            detail=str(atlas_path),
        )
    if str(atlas_metadata.get("filename") or "") != atlas_path.name:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_manifest_atlas_path_mismatch"
        )

    manifest_umg = _mapping(manifest.get("umg"))
    manifest_record = manifest_umg.get("record")
    if manifest_record != bake_result.flipbook_record:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_flipbook_record_mismatch"
        )
    record = normalize_umg_flipbook(bake_result.flipbook_record)
    asset_id = str(record.get("AssetId") or "")
    record_reasons = validate_umg_flipbook_record(
        bake_result.flipbook_record,
        document_schema_version=TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION,
        resource_ids=[asset_id] if asset_id else [],
    )
    if record_reasons:
        raise PainterUIFlipbookAttachError(
            [
                f"flipbook_attach_record_invalid:{reason}"
                for reason in record_reasons
            ]
        )

    playback_scope = str(manifest.get("playback_scope") or "")
    time_origin = str(manifest.get("time_origin") or "")
    material_ready = bool(manifest.get("material_ready", False))
    manifest_reasons = tuple(
        sorted(
            {
                str(reason)
                for reason in manifest.get("block_reasons", [])
                if str(reason)
            }
        )
    )
    umg_reasons = tuple(
        sorted(
            {
                str(reason)
                for reason in manifest_umg.get("block_reasons", [])
                if str(reason)
            }
        )
    )
    if (
        playback_scope != bake_result.playback_scope
        or time_origin != bake_result.time_origin
        or material_ready != bake_result.material_ready
        or manifest_reasons != tuple(sorted(set(bake_result.block_reasons)))
        or umg_reasons != manifest_reasons
        or str(manifest_umg.get("playback_scope") or "") != playback_scope
        or str(manifest_umg.get("time_origin") or "") != time_origin
        or bool(manifest_umg.get("material_ready", False)) != material_ready
    ):
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_bake_state_mismatch"
        )
    event_origin_blocker = (
        "flipbook_trigger_requires_dynamic_material_time_origin"
    )
    if time_origin != "global_time" or playback_scope not in {
        "ambient_loop",
        "event_triggered",
    }:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_bake_time_contract_unsupported"
        )
    if playback_scope == "ambient_loop" and (
        not material_ready or manifest_reasons
    ):
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_bake_state_mismatch"
        )
    if playback_scope == "event_triggered" and (
        material_ready or event_origin_blocker not in manifest_reasons
    ):
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_bake_state_mismatch"
        )

    source = _mapping(manifest.get("source"))
    bake_sha256 = str(manifest.get("bake_sha256") or "")
    if not bake_sha256:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_bake_provenance_missing"
        )
    sampling = _mapping(manifest.get("sampling"))
    fps_fraction = _mapping(sampling.get("frames_per_second_fraction"))
    try:
        bake_identity = {
            "schema": str(manifest.get("schema") or ""),
            "composition_sha256": str(source.get("composition_sha256") or ""),
            "composition_revision": int(
                source.get("composition_revision", 0) or 0
            ),
            "fps_fraction": [
                int(fps_fraction.get("numerator", 0) or 0),
                int(fps_fraction.get("denominator", 0) or 0),
            ],
            "frame_count": int(sampling.get("frame_count", 0) or 0),
            "cell_size": [
                int(atlas_metadata.get("cell_width", 0) or 0),
                int(atlas_metadata.get("cell_height", 0) or 0),
            ],
            "grid": [
                int(atlas_metadata.get("columns", 0) or 0),
                int(atlas_metadata.get("rows", 0) or 0),
            ],
            "max_atlas_size": int(
                atlas_metadata.get("max_atlas_size", 0) or 0
            ),
            "playback_scope": playback_scope,
            "time_origin": time_origin,
            "loop": bool(record["Loop"]),
        }
    except (TypeError, ValueError, OverflowError) as exc:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_bake_provenance_invalid"
        ) from exc
    if _sha256(_canonical_json_bytes(bake_identity, newline=False)) != bake_sha256:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_bake_hash_mismatch"
        )
    manifest_hash = _sha256(manifest_bytes)
    authored = {
        "source_path": str(atlas_path),
        "columns": int(record["Columns"]),
        "rows": int(record["Rows"]),
        "frame_count": int(record["FrameCount"]),
        "fps": float(record["FramesPerSecond"]),
        "start_frame": int(record["StartFrame"]),
        "loop": bool(record["Loop"]),
        "phase": float(record["Phase"]),
        "static_frame_override": int(record["StaticFrameOverride"]),
        "enabled": True,
    }
    if not _finite_number(authored["fps"]) or not _finite_number(
        authored["phase"]
    ):
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_record_numeric_value_invalid"
        )
    provenance = {
        "schema": PAINTER_UI_FLIPBOOK_ATTACHMENT_SCHEMA,
        "bake_schema": str(manifest.get("schema") or ""),
        "bake_sha256": bake_sha256,
        "atlas_path": str(atlas_path),
        "atlas_sha256": atlas_hash,
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_hash,
        "composition_id": str(source.get("composition_id") or ""),
        "composition_revision": int(
            source.get("composition_revision", 0) or 0
        ),
        "composition_schema_version": int(
            source.get("composition_schema_version", 0) or 0
        ),
        "composition_sha256": str(source.get("composition_sha256") or ""),
        "document_schema_version": manifest_document_version,
        "playback_scope": playback_scope,
        "time_origin": time_origin,
        "material_ready": material_ready,
        "block_reasons": list(manifest_reasons),
    }
    return {
        "authored": authored,
        "provenance": provenance,
        "atlas_sha256": atlas_hash,
        "manifest_sha256": manifest_hash,
        "playback_scope": playback_scope,
        "time_origin": time_origin,
        "material_ready": material_ready,
        "block_reasons": manifest_reasons,
    }


def _document_revision(value: Mapping[str, Any]) -> int:
    raw = value.get("revision", 0)
    if isinstance(raw, bool):
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_document_revision_invalid"
        )
    try:
        number = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_document_revision_invalid"
        ) from exc
    if not math.isfinite(number) or not number.is_integer() or number < 0:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_document_revision_invalid"
        )
    return int(number)


def attach_flipbook_bake_to_painter_document(
    document: Mapping[str, Any],
    object_id: str,
    bake_result: PainterUIFlipbookBakeResult,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a copied Painter document with one verified flipbook attached.

    The function has no UI side effects and never edits ``document`` in place.
    Only ``content.flipbook`` and ``content.flipbook_bake`` on the selected
    image/rectangle are changed.
    """

    if not isinstance(document, Mapping):
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_document_invalid"
        )
    wanted_id = str(object_id or "")
    if not wanted_id:
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_object_id_missing"
        )
    raw_objects = document.get("objects")
    if not isinstance(raw_objects, list):
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_document_objects_invalid"
        )
    matches = [
        row
        for row in raw_objects
        if isinstance(row, Mapping) and str(row.get("id") or "") == wanted_id
    ]
    if not matches:
        raise PainterUIFlipbookAttachError(
            f"flipbook_attach_object_missing:{wanted_id}"
        )
    if len(matches) > 1:
        raise PainterUIFlipbookAttachError(
            f"flipbook_attach_object_id_ambiguous:{wanted_id}"
        )
    kind = str(matches[0].get("kind") or "").strip().casefold()
    if kind not in PAINTER_UI_FLIPBOOK_OBJECT_KINDS:
        raise PainterUIFlipbookAttachError(
            f"flipbook_attach_object_kind_unsupported:{kind or 'unknown'}"
        )

    verified = _verified_bake(bake_result)
    input_revision = _document_revision(document)
    updated = copy.deepcopy(dict(document))
    updated_objects = updated.get("objects")
    if not isinstance(updated_objects, list):
        raise PainterUIFlipbookAttachError(
            "flipbook_attach_document_objects_invalid"
        )
    target = next(
        row
        for row in updated_objects
        if isinstance(row, Mapping) and str(row.get("id") or "") == wanted_id
    )
    if not isinstance(target, dict):
        target_index = updated_objects.index(target)
        target = copy.deepcopy(dict(target))
        updated_objects[target_index] = target
    content = target.get("content")
    content = copy.deepcopy(dict(content)) if isinstance(content, Mapping) else {}
    authored = copy.deepcopy(verified["authored"])
    provenance = copy.deepcopy(verified["provenance"])
    changed = (
        content.get("flipbook") != authored
        or content.get("flipbook_bake") != provenance
    )
    if changed:
        content["flipbook"] = authored
        content["flipbook_bake"] = provenance
        target["content"] = content
        updated["revision"] = input_revision + 1

    result_revision = input_revision + 1 if changed else input_revision
    report = {
        "schema": PAINTER_UI_FLIPBOOK_ATTACH_REPORT_SCHEMA,
        "changed": changed,
        "idempotent_reuse": not changed,
        "object_id": wanted_id,
        "object_kind": kind,
        "input_revision": input_revision,
        "result_revision": result_revision,
        "atlas_path": authored["source_path"],
        "atlas_sha256": verified["atlas_sha256"],
        "manifest_path": provenance["manifest_path"],
        "manifest_sha256": verified["manifest_sha256"],
        "bake_sha256": provenance["bake_sha256"],
        "playback_scope": verified["playback_scope"],
        "time_origin": verified["time_origin"],
        "material_ready": verified["material_ready"],
        "block_reasons": list(verified["block_reasons"]),
        "authored_flipbook": authored,
        "flipbook_bake": provenance,
    }
    return updated, report


__all__ = [
    "PAINTER_UI_FLIPBOOK_ATTACHMENT_SCHEMA",
    "PAINTER_UI_FLIPBOOK_ATTACH_REPORT_SCHEMA",
    "PAINTER_UI_FLIPBOOK_OBJECT_KINDS",
    "PainterUIFlipbookAttachError",
    "attach_flipbook_bake_to_painter_document",
]
