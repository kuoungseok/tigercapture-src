"""High-level structural and compatibility reporting for AEP projects."""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .model import AepChunk, AepDocument, AepSafetyLimits
from .rifx import parse_aep_file

REPORT_SCHEMA = "tigerstudio.motion.aep.inspect.v1"
_PRINTABLE_ASCII = re.compile(rb"[\x20-\x7e]{4,}")
_UTF16_BE = re.compile(rb"(?:\x00[\x20-\x7e]){4,}")
_UTF16_LE = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")
_PATH_HINT = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|/)[^\"'<>\x00\r\n]*?"
    r"\.(?:png|jpe?g|webp|gif|psd|ai|svg|mov|mp4|mxf|wav|aiff?|mp3|exr|aep)",
    re.IGNORECASE,
)
_RISK_MARKERS: dict[str, tuple[str, ...]] = {
    "third_party_effects": ("plugin", "plug-in", "videocopilot", "red giant", "sapphire"),
    "dynamic_link_or_3d": ("cinema 4d", "cineware", "dynamic link"),
    "fonts": ("font family", "fontfamily", "postscriptname"),
}


def _expression_property_count(document: AepDocument, chunks: Iterable[AepChunk]) -> int:
    count = 0
    for chunk in chunks:
        if chunk.tag != "tdb4" or chunk.size < 124:
            continue
        payload = document.payload(chunk)
        if payload[120] & 0x01:
            count += 1
    return count


def _leaf_chunks(root: AepChunk) -> Iterable[AepChunk]:
    return (chunk for chunk in root.walk() if not chunk.children)


def _bounded_text(value: str, limit: int) -> str:
    return value.strip(" \t\r\n\x00")[:limit]


def extract_strings(document: AepDocument, limits: AepSafetyLimits | None = None) -> list[str]:
    active = limits or AepSafetyLimits()
    found: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        text = _bounded_text(value, active.max_string_chars)
        if len(text) < 4 or text in seen or len(found) >= active.max_strings:
            return
        seen.add(text)
        found.append(text)

    for chunk in _leaf_chunks(document.root):
        payload = bytes(document.payload(chunk))
        for match in _PRINTABLE_ASCII.finditer(payload):
            add(match.group().decode("ascii", errors="ignore"))
        for match in _UTF16_BE.finditer(payload):
            add(match.group().decode("utf-16-be", errors="ignore"))
        for match in _UTF16_LE.finditer(payload):
            add(match.group().decode("utf-16-le", errors="ignore"))
        if len(found) >= active.max_strings:
            break
    if document.xmp_text:
        for match in re.finditer(r">([^<>]{4,})<", document.xmp_text):
            add(match.group(1))
            if len(found) >= active.max_strings:
                break
    return found


def inspect_aep_document(
    document: AepDocument,
    *,
    limits: AepSafetyLimits | None = None,
    include_tree: bool = False,
) -> dict[str, Any]:
    chunks = list(document.root.walk())
    tags = Counter(chunk.tag for chunk in chunks)
    list_types = Counter(chunk.list_type for chunk in chunks if chunk.list_type)
    strings = extract_strings(document, limits)
    paths: list[str] = []
    seen_paths: set[str] = set()
    for value in strings:
        for match in _PATH_HINT.finditer(value):
            path = match.group(0).strip('"\' ')
            if path not in seen_paths:
                seen_paths.add(path)
                paths.append(path)

    searchable = "\n".join(strings).lower()
    signals = {
        name: sorted({marker for marker in markers if marker in searchable})
        for name, markers in _RISK_MARKERS.items()
    }
    signals = {name: values for name, values in signals.items() if values}
    expression_count = _expression_property_count(document, chunks)
    if expression_count:
        signals["expressions"] = {"property_count": expression_count}
    blockers: list[str] = []
    if signals.get("expressions"):
        blockers.append("expressions_require_after_effects_evaluation")
    if signals.get("third_party_effects"):
        blockers.append("third_party_effects_require_after_effects_or_bake")
    if signals.get("dynamic_link_or_3d"):
        blockers.append("dynamic_link_or_cineware_requires_after_effects")
    disposition = "ae_render_required" if blockers else "native_conversion_candidate"

    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "ok": True,
        "source": document.source_path,
        "sha256": hashlib.sha256(document.data).hexdigest(),
        "file_size": document.file_size,
        "rifx_size": document.root.size,
        "root_type": document.root.list_type,
        "xmp_bytes": document.file_size - document.xmp_offset,
        "structure": {
            "chunk_count": len(chunks),
            "max_depth": max(chunk.depth for chunk in chunks),
            "tags": dict(tags.most_common()),
            "list_types": dict(list_types.most_common()),
            "opaque_lists": sum(1 for chunk in chunks if chunk.opaque),
        },
        "assets": {"path_candidates": paths},
        "compatibility": {
            "disposition": disposition,
            "blockers": blockers,
            "signals": signals,
            "native_scope": [
                "container_structure",
                "string_and_linked_asset_discovery",
                "unknown_chunk_preservation_metadata",
            ],
            "not_evaluated": [
                "expressions",
                "scripts",
                "third_party_plugins",
                "after_effects_rendering",
            ],
        },
        "string_count": len(strings),
        "strings_preview": strings[:100],
    }
    if include_tree:
        report["tree"] = document.root.to_summary()
    return report


def inspect_aep_file(
    path: str | Path,
    *,
    limits: AepSafetyLimits | None = None,
    include_tree: bool = False,
) -> dict[str, Any]:
    document = parse_aep_file(path, limits=limits)
    return inspect_aep_document(document, limits=limits, include_tree=include_tree)
