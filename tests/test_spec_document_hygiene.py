from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CORE_AGENT_DOCS = [
    "SPEC.md",
    "AGENTS.md",
    "docs/AGENT_START_HERE.md",
    "docs/SPEC_PYTHON_ACTION_SYSTEM.md",
]

REQUIRED_SPEC_LINKS = [
    "docs/SPEC_BROADCAST_SCENE.md",
    "docs/SPEC_REPO_MAINTAINABILITY.md",
    "docs/SPEC_UI_RENEWAL.md",
    "docs/SPEC_VSEEFACE_BRIDGE.md",
]

KNOWN_MOJIBAKE_MARKERS = [
    "\ufffd",
    "\uf9e6\u226a",
    "?\uba2e",
    "\u8adb\uaccc",
    "\u5bc3\ub6af",
    "?\uba84\ucb5b",
    "?\ub2ff\ub9b0",
    "?\u317d\ubefe",
    "?\uc579\uaf66",
    "\u724d",
    "\u6ecc",
    "\u703e",
    "\u800c??",
]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_core_agent_docs_have_no_known_mojibake() -> None:
    failures: list[str] = []
    for rel_path in CORE_AGENT_DOCS:
        text = _read(rel_path)
        for marker in KNOWN_MOJIBAKE_MARKERS:
            if marker in text:
                failures.append(f"{rel_path}: {marker!r}")
    assert not failures


def test_main_spec_links_active_handoff_specs() -> None:
    spec = _read("SPEC.md")
    missing = [rel for rel in REQUIRED_SPEC_LINKS if rel not in spec]
    assert not missing


def test_unreal_specific_docs_are_not_reintroduced() -> None:
    assert not (ROOT / "docs/SPEC_UNREAL_MCP_CAPTURE_CONTROL.md").exists()

    checked_files = [ROOT / "SPEC.md", ROOT / "AGENTS.md"]
    checked_files.extend((ROOT / "docs").rglob("*.md"))
    checked_files.extend((ROOT / "docs").rglob("*.json"))

    offenders: list[str] = []
    for path in checked_files:
        text = path.read_text(encoding="utf-8")
        if "Unreal" in text or "unreal" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders


def test_review_spec_index_json_is_valid() -> None:
    index_path = ROOT / "docs/review_automation/spec_index_groups.json"
    json.loads(index_path.read_text(encoding="utf-8"))
