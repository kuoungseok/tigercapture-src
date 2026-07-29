"""Object-anchored review comments, checkpoints, diffs, and offline packages."""
from __future__ import annotations

import copy
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document, validate_ui_document


REVIEW_SCHEMA = "tigerstudio.painter.ui.review.v1"
REVIEW_PACKAGE_SCHEMA = "tigerstudio.painter.ui.review_package.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _review_target(document: Mapping[str, Any]) -> dict[str, Any]:
    linked = document.get("linked_targets")
    linked = linked if isinstance(linked, Mapping) else {}
    raw = linked.get("review")
    raw = raw if isinstance(raw, Mapping) else {}
    return {
        "schema": REVIEW_SCHEMA,
        "comments": [
            dict(row) for row in raw.get("comments", []) if isinstance(row, Mapping)
        ],
        "checkpoints": [
            dict(row)
            for row in raw.get("checkpoints", [])
            if isinstance(row, Mapping)
        ],
    }


def inspect_ui_review(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    target = _review_target(document)
    unresolved = [
        row for row in target["comments"] if not bool(row.get("resolved"))
    ]
    return {
        "schema": REVIEW_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "comment_count": len(target["comments"]),
        "unresolved_count": len(unresolved),
        "checkpoint_count": len(target["checkpoints"]),
        "comments": target["comments"],
        "checkpoints": [
            {
                key: value
                for key, value in row.items()
                if key != "document"
            }
            for row in target["checkpoints"]
        ],
    }


def _commit_review(
    value: Mapping[str, Any],
    target: Mapping[str, Any],
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    linked = copy.deepcopy(document["linked_targets"])
    linked["review"] = copy.deepcopy(dict(target))
    document["linked_targets"] = linked
    document["revision"] = int(document["revision"]) + 1
    return document


def add_ui_review_comment(
    value: Mapping[str, Any],
    *,
    text: str,
    object_id: str = "",
    artboard_id: str = "",
    author: str = "",
    x: float = 0.5,
    y: float = 0.5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    object_key = str(object_id or "")
    object_row = next(
        (row for row in document["objects"] if row["id"] == object_key),
        None,
    )
    if object_key and object_row is None:
        raise ValueError(f"Painter UI review object not found: {object_key}")
    artboard_key = str(
        artboard_id
        or (object_row["artboard_id"] if object_row is not None else "")
        or document["active_artboard_id"]
    )
    if artboard_key not in {row["id"] for row in document["artboards"]}:
        raise ValueError(f"Painter UI review artboard not found: {artboard_key}")
    if not str(text or "").strip():
        raise ValueError("Review comment text is required")
    target = _review_target(document)
    existing_ids = {str(row.get("id") or "") for row in target["comments"]}
    index = 1
    while f"ui-comment-{index}" in existing_ids:
        index += 1
    row = {
        "id": f"ui-comment-{index}",
        "object_id": object_key,
        "artboard_id": artboard_key,
        "author": str(author or "Reviewer"),
        "text": str(text).strip(),
        "resolved": False,
        "created_at": _now(),
        "updated_at": _now(),
        "anchor": {
            "x": min(1.0, max(0.0, float(x))),
            "y": min(1.0, max(0.0, float(y))),
        },
        "replies": [],
    }
    target["comments"].append(row)
    return _commit_review(document, target), row


def update_ui_review_comment(
    value: Mapping[str, Any],
    comment_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    target = _review_target(document)
    for index, row in enumerate(target["comments"]):
        if str(row.get("id") or "") != str(comment_id):
            continue
        updated = copy.deepcopy(row)
        if "text" in changes:
            text = str(changes["text"] or "").strip()
            if not text:
                raise ValueError("Review comment text is required")
            updated["text"] = text
        if "resolved" in changes:
            updated["resolved"] = bool(changes["resolved"])
        if "reply" in changes and str(changes["reply"] or "").strip():
            replies = list(updated.get("replies") or [])
            replies.append(
                {
                    "author": str(changes.get("author") or "Reviewer"),
                    "text": str(changes["reply"]).strip(),
                    "created_at": _now(),
                }
            )
            updated["replies"] = replies
        updated["updated_at"] = _now()
        target["comments"][index] = updated
        return _commit_review(document, target), updated
    raise ValueError(f"Painter UI review comment not found: {comment_id}")


def remove_ui_review_comment(
    value: Mapping[str, Any],
    comment_id: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    target = _review_target(document)
    before = len(target["comments"])
    target["comments"] = [
        row
        for row in target["comments"]
        if str(row.get("id") or "") != str(comment_id)
    ]
    if len(target["comments"]) == before:
        raise ValueError(f"Painter UI review comment not found: {comment_id}")
    return _commit_review(document, target)


def _checkpoint_document(document: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = normalize_ui_document(document)
    linked = copy.deepcopy(snapshot["linked_targets"])
    review = _review_target(snapshot)
    review["checkpoints"] = []
    linked["review"] = review
    snapshot["linked_targets"] = linked
    return snapshot


def create_ui_review_checkpoint(
    value: Mapping[str, Any],
    *,
    name: str,
    author: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    target = _review_target(document)
    snapshot = _checkpoint_document(document)
    payload = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    existing_ids = {str(row.get("id") or "") for row in target["checkpoints"]}
    index = 1
    while f"ui-checkpoint-{index}" in existing_ids:
        index += 1
    checkpoint = {
        "id": f"ui-checkpoint-{index}",
        "name": str(name or f"Checkpoint {index}"),
        "author": str(author or "Designer"),
        "created_at": _now(),
        "source_revision": int(document["revision"]),
        "document_sha256": hashlib.sha256(payload).hexdigest(),
        "document": snapshot,
    }
    target["checkpoints"].append(checkpoint)
    return _commit_review(document, target), {
        key: row for key, row in checkpoint.items() if key != "document"
    }


def _rows_by_id(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {
        str(row.get("id") or ""): row
        for row in value.get(key, [])
        if isinstance(row, Mapping) and str(row.get("id") or "")
    }


def diff_ui_documents(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    left = normalize_ui_document(before)
    right = normalize_ui_document(after)
    sections: dict[str, Any] = {}
    for key in ("artboards", "objects", "components", "tokens", "interactions"):
        before_rows = _rows_by_id(left, key)
        after_rows = _rows_by_id(right, key)
        added = sorted(set(after_rows) - set(before_rows))
        removed = sorted(set(before_rows) - set(after_rows))
        changed = sorted(
            row_id
            for row_id in set(before_rows) & set(after_rows)
            if before_rows[row_id] != after_rows[row_id]
        )
        sections[key] = {
            "added": added,
            "removed": removed,
            "changed": changed,
        }
    return {
        "schema": "tigerstudio.painter.ui.revision_diff.v1",
        "document_id": right["document_id"],
        "before_revision": left["revision"],
        "after_revision": right["revision"],
        "sections": sections,
        "change_count": sum(
            len(values)
            for section in sections.values()
            for values in section.values()
        ),
    }


def diff_ui_checkpoint(
    value: Mapping[str, Any],
    checkpoint_id: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    target = _review_target(document)
    checkpoint = next(
        (
            row
            for row in target["checkpoints"]
            if str(row.get("id") or "") == str(checkpoint_id)
        ),
        None,
    )
    if checkpoint is None:
        raise ValueError(f"Painter UI checkpoint not found: {checkpoint_id}")
    return diff_ui_documents(checkpoint["document"], document)


def developer_inspect_ui_document(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    validation = validate_ui_document(document)
    from app.painter_ui_delivery import preflight_ui_delivery
    from app.painter_ui_dev_handoff import inspect_ui_dev_handoff

    dev_handoff = inspect_ui_dev_handoff(
        document,
        object_ids=[row["id"] for row in document["objects"]],
    )

    return {
        "schema": "tigerstudio.painter.ui.developer_inspect.v1",
        "document_id": document["document_id"],
        "revision": document["revision"],
        "validation": validation,
        "objects": [
            {
                "id": row["id"],
                "name": row["name"],
                "kind": row["kind"],
                "artboard_id": row["artboard_id"],
                "parent_id": row["parent_id"],
                "geometry": {
                    key: row[key]
                    for key in ("x", "y", "width", "height", "rotation")
                },
                "token_bindings": dict(row.get("token_bindings") or {}),
                "accessibility": dict(row.get("accessibility") or {}),
            }
            for row in document["objects"]
        ],
        "delivery": {
            target: preflight_ui_delivery(document, target)
            for target in (
                "asset_export",
                "design_handoff",
                "review_prototype",
                "unreal_umg",
            )
        },
        "review": inspect_ui_review(document),
        "dev_handoff": dev_handoff,
    }


def export_ui_review_package(
    value: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    inspect_report = developer_inspect_ui_document(document)
    dev_handoff = inspect_report["dev_handoff"]
    review = inspect_ui_review(document)
    files = {
        "design_document.json": document,
        "inspection.json": inspect_report,
        "dev_handoff.json": dev_handoff,
        "review.json": review,
    }
    artifacts = []
    for name, payload in files.items():
        path = root / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        artifacts.append(str(path))
    index = root / "index.html"
    index.write_text(
        """<!doctype html><meta charset="utf-8"><title>Tiger Studio Review</title>
<style>body{font:14px system-ui;background:#17191d;color:#eef1f5;margin:0}
main{max-width:1000px;margin:auto;padding:32px}article{border-top:1px solid #343941;padding:14px 0}
code{color:#93c5fd}.resolved{opacity:.55}</style><main>
<h1>Tiger Studio UI Review</h1>
<p>Document <code>%s</code>, revision %s</p><h2>Comments</h2>%s
<h2>Developer inspection</h2><p>%s objects, %s validation errors.</p></main>"""
        % (
            html.escape(document["document_id"]),
            document["revision"],
            "".join(
                '<article class="%s"><strong>%s</strong><p>%s</p><code>%s</code></article>'
                % (
                    "resolved" if row.get("resolved") else "",
                    html.escape(str(row.get("author") or "Reviewer")),
                    html.escape(str(row.get("text") or "")),
                    html.escape(str(row.get("object_id") or row.get("artboard_id") or "")),
                )
                for row in review["comments"]
            )
            or "<p>No comments.</p>",
            len(document["objects"]),
            len(inspect_report["validation"]["errors"]),
        ),
        encoding="utf-8",
    )
    artifacts.append(str(index))
    manifest = {
        "schema": REVIEW_PACKAGE_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "entrypoint": "index.html",
        "artifacts": [Path(path).name for path in artifacts],
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    artifacts.append(str(manifest_path))
    return {
        "ok": True,
        "root": str(root),
        "entrypoint": str(index),
        "artifacts": artifacts,
        "manifest": manifest,
    }


__all__ = [
    "REVIEW_PACKAGE_SCHEMA",
    "REVIEW_SCHEMA",
    "add_ui_review_comment",
    "create_ui_review_checkpoint",
    "developer_inspect_ui_document",
    "diff_ui_checkpoint",
    "diff_ui_documents",
    "export_ui_review_package",
    "inspect_ui_review",
    "remove_ui_review_comment",
    "update_ui_review_comment",
]
