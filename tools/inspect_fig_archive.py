"""Inspect a Figma ``.fig`` archive from the command line.

Point this at a local copy saved from Figma (``File > Save local copy``) to see
what the native reader recovers before wiring the file into the Painter UI
import path. Three views are available:

    python tools/inspect_fig_archive.py design.fig                 # summary
    python tools/inspect_fig_archive.py design.fig --dump-rest out.json
    python tools/inspect_fig_archive.py design.fig --dump-raw out.json

``--dump-rest`` writes the translated REST-shaped payload, which is the exact
input :func:`app.painter_ui_figma.import_figma_payload` consumes, so the result
drops straight into the compatibility corpus. ``--dump-raw`` writes the decoded
internal message instead, which is what to read when a node fails to translate.

The ``.fig`` layout is reverse engineered rather than a published Figma
contract; treat any failure here as expected and fall back to the REST import.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.painter_ui_figma_fig import PainterUIFigError, read_fig_archive  # noqa: E402
from app.painter_ui_figma_fig_rest import fig_archive_to_rest_payload  # noqa: E402
from app.painter_ui_figma_kiwi import schema_summary  # noqa: E402


def _json_safe(value: Any) -> Any:
    """Make the decoded message serializable without losing binary blobs."""

    if isinstance(value, (bytes, bytearray)):
        return {"__bytes__": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, dict):
        return {key: _json_safe(entry) for key, entry in value.items()}
    if isinstance(value, list):
        return [_json_safe(entry) for entry in value]
    return value


def _summarize(path: Path) -> int:
    try:
        archive = read_fig_archive(path)
    except PainterUIFigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    rows = archive.node_changes
    counts = Counter(str(row.get("type") or "?") for row in rows)

    print(f"file          {path}")
    print(f"fig version   {archive.version}")
    print(f"schema        {dict(schema_summary(archive.schema))}, {len(archive.schema.definitions)} definitions")
    print(f"node changes  {len(rows)}")
    print(f"images        {len(archive.images)}")
    if archive.meta:
        print(f"meta          {json.dumps(archive.meta, ensure_ascii=False)[:200]}")
    print("\ninternal node types")
    for name, count in counts.most_common():
        print(f"  {count:6d}  {name}")

    try:
        _payload, report = fig_archive_to_rest_payload(archive)
    except ValueError as exc:
        print(f"\ntranslation failed: {exc}", file=sys.stderr)
        return 1
    print("\ntranslation")
    print(f"  nodes        {report['node_count']}")
    print(f"  roots        {report['root_count']}")
    print(f"  unmapped     {report['unmapped_node_types'] or 'none'}")
    for warning in report["warnings"]:
        print(f"  warning      {warning}")
    return 0


def _dump(path: Path, target: Path, *, raw: bool) -> int:
    try:
        archive = read_fig_archive(path)
        if raw:
            payload: Any = _json_safe(archive.message)
        else:
            payload, _report = fig_archive_to_rest_payload(archive)
    except (PainterUIFigError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {target} ({target.stat().st_size} bytes)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path, help="path to a .fig archive")
    parser.add_argument("--dump-rest", type=Path, default=None, help="write the translated REST payload as JSON")
    parser.add_argument("--dump-raw", type=Path, default=None, help="write the decoded internal message as JSON")
    args = parser.parse_args(argv)

    if args.dump_rest and args.dump_raw:
        parser.error("choose one of --dump-rest or --dump-raw")
    if args.dump_rest:
        return _dump(args.path, args.dump_rest, raw=False)
    if args.dump_raw:
        return _dump(args.path, args.dump_raw, raw=True)
    return _summarize(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
