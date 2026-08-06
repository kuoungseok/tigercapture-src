from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.qa_painter_ui_figma_document_corpus import (  # noqa: E402
    _selector_canonical_bytes,
    _selector_semantic_value,
)


_AUTO_EXTRA_IDS = (
    "1993:3156", "2495:1898", "1620:1350", "1620:1440",
    "1620:1519", "1620:1554", "1620:1667", "1620:1694",
    "1749:3056", "1620:2915", "1730:3063",
)
_RADIX_IDS = (
    "2001:4197", "2001:4290", "2001:4581", "2001:4819",
    "2001:4895", "2001:4947", "2001:5123", "2001:5604",
    "2001:5917", "2001:6097", "4:7679",
)


def _archive_index(artifact: dict[str, object]) -> dict[str, tuple[dict, tuple[str, ...], str]]:
    path = ROOT / "external" / "assets" / "figma" / "compat_corpus" / str(
        artifact["relative_path"]
    )
    with zipfile.ZipFile(path) as archive:
        document_name = next(
            name for name in archive.namelist() if name.endswith("document.json")
        )
        payload = json.loads(archive.read(document_name))
    index: dict[str, tuple[dict, tuple[str, ...], str]] = {}

    def visit(node: object, ancestry: tuple[str, ...] = (), canvas: str = "") -> None:
        if not isinstance(node, dict):
            return
        node_id = str(node.get("id") or "")
        here = (*ancestry, node_id)
        current_canvas = node_id if node.get("type") == "CANVAS" else canvas
        if node_id:
            index[node_id] = (node, here, current_canvas)
        for child in node.get("children") or []:
            visit(child, here, current_canvas)

    visit(payload["document"])
    return index


def _node_count(node: dict) -> int:
    return 1 + sum(
        _node_count(child)
        for child in node.get("children") or []
        if isinstance(child, dict)
    )


def build_manifest() -> dict[str, object]:
    manifest_dir = ROOT / "qa_corpus" / "painter_ui_figma_documents"
    nightly = json.loads((manifest_dir / "nightly_manifest.json").read_text(encoding="utf-8"))
    artifacts = {
        "grida.auto-layout": {
            "source": copy.deepcopy(nightly["cases"][0]["source"]),
            "artifact": copy.deepcopy(nightly["cases"][0]["artifact"]),
        },
        "grida.radix-icons": {
            "source": copy.deepcopy(nightly["cases"][1]["source"]),
            "artifact": copy.deepcopy(nightly["cases"][1]["artifact"]),
        },
    }
    auto_index = _archive_index(artifacts["grida.auto-layout"]["artifact"])
    auto_ids = [
        str(child["id"])
        for child in auto_index["2411:1174"][0]["children"]
        if str(child.get("id")) != "2411:11034"
    ] + list(_AUTO_EXTRA_IDS)
    assert len(auto_ids) == len(set(auto_ids)) == 67
    cases: list[dict[str, object]] = []
    sources = (
        ("grida.auto-layout", auto_ids, auto_index),
        (
            "grida.radix-icons",
            list(_RADIX_IDS),
            _archive_index(artifacts["grida.radix-icons"]["artifact"]),
        ),
    )
    for artifact_ref, node_ids, index in sources:
        for node_id in node_ids:
            node, ancestry, canvas = index[node_id]
            exact = _selector_canonical_bytes(node)
            semantic = _selector_canonical_bytes(_selector_semantic_value(node))
            count = _node_count(node)
            short_ref = "auto" if artifact_ref.endswith("layout") else "radix"
            cases.append(
                {
                    "id": f"release.{short_ref}.{node_id.replace(':', '-')}",
                    "title": f"{node.get('name') or node_id} ({node_id})",
                    "artifact_ref": artifact_ref,
                    "selector": {
                        "kind": "node_subtree",
                        "node_id": node_id,
                        "ancestor_canvas_id": canvas,
                        "ancestry": list(ancestry),
                        "expected_type": str(node.get("type") or ""),
                        "expected_name": str(node.get("name") or ""),
                        "subtree_sha256": hashlib.sha256(exact).hexdigest(),
                        "semantic_sha256": hashlib.sha256(semantic).hexdigest(),
                        "observed_nodes": count,
                        "observed_json_bytes": len(exact),
                        "wrapper": "promote_to_original_canvas",
                    },
                    "expectations": {
                        "min_artboards": 1,
                        "min_objects": max(1, count - 1),
                        "required_source_features": ["auto_layout"],
                        "preserve_features": [
                            "auto_layout"
                            if artifact_ref == "grida.auto-layout"
                            else "path_geometry"
                        ],
                    },
                }
            )
    assert len(cases) == 78
    return {
        "schema": "tigercapture.painter.figma_document_corpus.v2",
        "description": "Audited release gate: 20 fast fixtures, 2 standalone geometry fixtures, and 78 disjoint selectors from two pinned CC BY Figma Community REST archives.",
        "storage_root": "external/assets/figma/compat_corpus",
        "includes": [
            {"path": "manifest.json"},
            {
                "path": "nightly_manifest.json",
                "case_ids": ["grida.stroke.file", "grida.vector-frame.nodes"],
            },
        ],
        "source_artifacts": artifacts,
        "coverage": {
            "expected_case_count": 100,
            "expected_selector_case_count": 78,
            "min_selector_original_sources": 2,
            "min_selector_nodes": 7578,
            "max_missing_image_count": 0,
            "selector_min_source_feature_cases": {
                "image_fill": 48,
                "vector_geometry_complete": 74,
                "auto_layout": 78,
                "component": 12,
                "component_set": 2,
                "instance": 50,
                "text": 68,
                "text_ranges": 46,
                "mask": 11,
                "effects": 41,
                "boolean_operation": 41,
                "variable_bindings": 57,
                "figma_variable_binding_alias": 57,
            },
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-start", type=int, default=0)
    parser.add_argument("--chunk-size", type=int, default=0)
    args = parser.parse_args()
    text = json.dumps(build_manifest(), ensure_ascii=True, indent=2) + "\n"
    end = args.chunk_start + args.chunk_size if args.chunk_size else None
    sys.stdout.write(text[args.chunk_start:end])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
