"""Deterministic Painter UI exchange and delivery round-trip corpus."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Mapping


SCHEMA = "tigerstudio.painter.ui.release_corpus.v1"


def _fingerprint(value: Mapping[str, Any]) -> str:
    from app.painter_ui_document import normalize_ui_document

    encoded = json.dumps(
        normalize_ui_document(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_painter_ui_release_document() -> dict[str, Any]:
    """Build one small but contract-rich editable UI document."""

    from app.painter_ui_components import convert_ui_object_to_component
    from app.painter_ui_dev_handoff import (
        add_ui_dev_annotation,
        set_ui_dev_ready,
    )
    from app.painter_ui_document import (
        add_ui_interaction,
        add_ui_object,
        add_ui_token,
        create_ui_document,
        normalize_ui_document,
    )
    from app.painter_ui_review import add_ui_review_comment

    document = create_ui_document(390, 844, name="Release Mobile")
    document, card = add_ui_object(
        document,
        kind="frame",
        name="Release Card",
        x=24,
        y=80,
        width=342,
        height=220,
    )
    # Containers remain structural in the provider-neutral UMG contract.
    # Keep the card appearance on an editable leaf rectangle so the corpus
    # exercises rounded/stroked material conversion without silently asking a
    # Group widget to render appearance that TigerStudioUMG cannot preserve.
    document, _card_surface = add_ui_object(
        document,
        kind="rectangle",
        name="Release Card Surface",
        parent_id=card["id"],
        x=0,
        y=0,
        width=342,
        height=220,
        style={
            "fill": "#17212D",
            "stroke": "#40536A",
            "stroke_width": 1,
            "radius": 12,
        },
    )
    document, heading = add_ui_object(
        document,
        kind="text",
        name="Release Heading",
        parent_id=card["id"],
        x=24,
        y=24,
        width=294,
        height=42,
        content={"text": "Tiger Studio Release"},
        style={"fill": "#EAF2FA"},
    )
    document, button = add_ui_object(
        document,
        kind="button",
        name="Continue Button",
        parent_id=card["id"],
        x=24,
        y=144,
        width=180,
        height=48,
        content={"text": "Continue"},
        style={"fill": "#437BB6"},
    )
    document, _component = convert_ui_object_to_component(
        document,
        root_object_id=button["id"],
        name="Continue Button",
    )
    document, _token = add_ui_token(
        document,
        name="Action / Primary",
        kind="color",
        token_value="#437BB6",
        theme_values={"dark": "#6E9ED0"},
    )
    document, _interaction = add_ui_interaction(
        document,
        name="Continue",
        source_object_id=button["id"],
        trigger="click",
        action="navigate",
        target_artboard_id=document["active_artboard_id"],
    )
    document, _comment = add_ui_review_comment(
        document,
        text="Verify keyboard and touch activation.",
        object_id=button["id"],
        author="Release QA",
    )
    comment = document["linked_targets"]["review"]["comments"][0]
    comment["created_at"] = "2026-07-29T00:00:00+00:00"
    comment["updated_at"] = "2026-07-29T00:00:00+00:00"
    document, _ready = set_ui_dev_ready(
        document,
        target_type="object",
        target_id=button["id"],
        ready=True,
        note="Native behavior and focus state reviewed.",
    )
    document, _annotation = add_ui_dev_annotation(
        document,
        target_type="object",
        target_id=heading["id"],
        text="Preserve semantic heading order.",
    )
    return normalize_ui_document(document)


def _case(
    case_id: str,
    label: str,
    callback: Callable[[], Mapping[str, Any]],
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        detail = dict(callback())
        passed = bool(detail.pop("passed", True))
        return {
            "id": case_id,
            "label": label,
            "status": "passed" if passed else "blocked",
            "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "reason": "" if passed else str(detail.get("reason") or "mismatch"),
            "detail": detail,
        }
    except Exception as exc:
        return {
            "id": case_id,
            "label": label,
            "status": "blocked",
            "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "reason": f"{type(exc).__name__}: {exc}",
            "detail": {},
        }


def run_painter_ui_release_corpus(
    output_dir: str | Path,
) -> dict[str, Any]:
    """Run semantic round trips and preserve regenerable release evidence."""

    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    document = build_painter_ui_release_document()
    expected = _fingerprint(document)

    def native_case() -> dict[str, Any]:
        from app.painter_document_io import (
            load_painter_document,
            save_painter_document,
        )

        target = root / "native" / "release_corpus.tspaint"
        target.parent.mkdir(parents=True, exist_ok=True)
        save_report = save_painter_document(
            target,
            {
                "document": {"width": 390, "height": 844},
                "ui_document": document,
            },
        )
        loaded, load_report = load_painter_document(target)
        actual = _fingerprint(loaded["ui_document"])
        return {
            "passed": actual == expected,
            "artifact": str(target),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "save": save_report,
            "load": load_report,
        }

    def figma_case() -> dict[str, Any]:
        from app.painter_ui_figma import export_figma_plugin_package

        report = export_figma_plugin_package(document, root / "figma")
        exchange_path = Path(report["exchange_path"])
        exchange = json.loads(exchange_path.read_text(encoding="utf-8"))
        actual = _fingerprint(exchange["document"])
        return {
            "passed": actual == expected,
            "artifact": str(exchange_path),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "compatibility": report["compatibility"],
            "scope": "editable_plugin_exchange_not_native_fig",
        }

    def template_case() -> dict[str, Any]:
        from app.painter_ui_template_store import (
            export_ui_template_package,
            read_ui_template_package,
        )

        target = root / "template" / "release_ui.tstemplate"
        exported = export_ui_template_package(
            document,
            target,
            template_id="release-ui",
            name="Release UI",
            category="QA",
        )
        loaded = read_ui_template_package(target)
        actual = _fingerprint(loaded["document"])
        return {
            "passed": actual == expected,
            "artifact": exported["path"],
            "expected_sha256": expected,
            "actual_sha256": actual,
            "package_sha256": loaded["document_sha256"],
        }

    def handoff_case() -> dict[str, Any]:
        from app.painter_ui_delivery import package_design_handoff

        report = package_design_handoff(document, root / "handoff")
        target = Path(report["output_dir"]) / "design_document.json"
        restored = json.loads(target.read_text(encoding="utf-8"))
        actual = _fingerprint(restored)
        return {
            "passed": bool(report["ok"]) and actual == expected,
            "artifact": str(target),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "artifact_count": len(report["artifacts"]),
        }

    def prototype_case() -> dict[str, Any]:
        from app.painter_ui_prototype import export_ui_prototype

        report = export_ui_prototype(document, root / "prototype")
        target = Path(report["root"]) / "design_document.json"
        restored = json.loads(target.read_text(encoding="utf-8"))
        actual = _fingerprint(restored)
        return {
            "passed": bool(report["ok"]) and actual == expected,
            "artifact": str(report["entrypoint"]),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "inspection": report["inspection"],
        }

    def review_case() -> dict[str, Any]:
        from app.painter_ui_review import export_ui_review_package

        report = export_ui_review_package(document, root / "review")
        target = Path(report["root"]) / "design_document.json"
        restored = json.loads(target.read_text(encoding="utf-8"))
        actual = _fingerprint(restored)
        return {
            "passed": bool(report["ok"]) and actual == expected,
            "artifact": str(report["entrypoint"]),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "artifact_count": len(report["artifacts"]),
        }

    def umg_case() -> dict[str, Any]:
        from app.painter_ui_umg_adapter import package_painter_umg

        report = package_painter_umg(document, root / "umg")
        target = Path(report["document_path"])
        restored = json.loads(target.read_text(encoding="utf-8"))
        passed = bool(report["ok"]) and restored == report["document"]
        return {
            "passed": passed,
            "artifact": str(target),
            "counts": report["preflight"]["counts"],
            "scope": "provider_neutral_contract_only",
            "unreal_compile_and_capture": "not_run",
        }

    cases = [
        _case("native_tspaint", "Native .tspaint", native_case),
        _case("figma_exchange", "Figma plugin exchange", figma_case),
        _case("template_package", "Template package", template_case),
        _case("design_handoff", "Design handoff", handoff_case),
        _case("prototype_package", "Interactive prototype", prototype_case),
        _case("review_package", "Offline review", review_case),
        _case("umg_contract", "Tiger UMG contract", umg_case),
    ]
    passed_count = sum(row["status"] == "passed" for row in cases)
    report = {
        "schema": SCHEMA,
        "ok": passed_count == len(cases),
        "status": "covered" if passed_count == len(cases) else "blocked",
        "output_dir": str(root),
        "document_id": document["document_id"],
        "document_sha256": expected,
        "case_count": len(cases),
        "passed_count": passed_count,
        "blocked_count": len(cases) - passed_count,
        "cases": cases,
        "runtime_claims": {
            "figma_native_file": "not_claimed",
            "unreal_widget_blueprint_compile": "not_run",
            "unreal_real_capture": "not_run",
        },
    }
    report_path = root / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report["report_path"] = str(report_path)
    return report


__all__ = [
    "SCHEMA",
    "build_painter_ui_release_document",
    "run_painter_ui_release_corpus",
]
