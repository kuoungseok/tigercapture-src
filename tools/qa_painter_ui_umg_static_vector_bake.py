"""Fast per-object audit for the conservative UMG static-vector bake gate."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


VECTOR_GATE = "figma_vector_geometry_requires_deterministic_bake"


def _select_manifest_cases(
    manifest: dict[str, Any],
    case_ids: set[str] | None,
) -> dict[str, Any]:
    """Return a manifest narrowed to explicit case IDs, failing closed."""

    if not case_ids:
        return manifest
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Static-vector audit manifest cases must be an array")
    available_ids = {
        str(row.get("id") or "")
        for row in cases
        if isinstance(row, dict)
    }
    missing_ids = sorted(case_ids - available_ids)
    if missing_ids:
        raise ValueError(
            "Unknown static-vector audit case id(s): "
            + ", ".join(missing_ids)
        )
    return {
        **manifest,
        "cases": [
            row
            for row in cases
            if isinstance(row, dict) and str(row.get("id") or "") in case_ids
        ],
    }


def _load_audit_case_source(
    case: dict[str, Any],
    source_path: Path,
    selector_artifact_cache: dict[tuple[str, str], dict[str, Any]],
    *,
    load_case_source: Any,
    load_selector_case_source: Any,
    verify_case_artifact: Any,
) -> tuple[Any, dict[str, str], dict[str, Any]]:
    """Load the exact manifest workload, including selector subtrees."""

    selector = case.get("selector")
    if isinstance(selector, dict):
        payload, image_paths, details, _selector_evidence = (
            load_selector_case_source(
                source_path,
                case["artifact"],
                selector,
                selector_artifact_cache,
            )
        )
        return payload, image_paths, details
    verify_case_artifact(source_path, case["artifact"])
    return load_case_source(source_path)


def _canonical_reason_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or any(
        not isinstance(reason, str) or not reason for reason in value
    ):
        return None
    canonical = sorted(set(value))
    return canonical if value == canonical else None


def _gate_transition_evidence(
    layer: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Verify the serialized transition against the layer's final result.

    This deliberately does not reconstruct a hypothetical transition from the
    current disposition or from corpus totals.  The adapter owns the actual
    before/after diagnostic lists and persists them in ``PayloadJson``; QA only
    accepts that evidence when it exactly agrees with the final layer.
    """

    transition = plan.get("gate_transition")
    errors: list[str] = []
    if not isinstance(transition, dict):
        return {
            "valid": False,
            "before": [],
            "after": [],
            "satisfied": [],
            "errors": ["gate_transition_missing"],
        }
    before = _canonical_reason_list(transition.get("before"))
    after = _canonical_reason_list(transition.get("after"))
    satisfied = _canonical_reason_list(transition.get("satisfied"))
    if before is None:
        errors.append("gate_transition_before_noncanonical")
        before = []
    if after is None:
        errors.append("gate_transition_after_noncanonical")
        after = []
    if satisfied is None:
        errors.append("gate_transition_satisfied_noncanonical")
        satisfied = []

    final_reasons = _canonical_reason_list(layer.get("BlockReasons"))
    if final_reasons is None:
        errors.append("layer_block_reasons_noncanonical")
        final_reasons = []
    if after != final_reasons:
        errors.append("gate_transition_after_not_final_layer_reasons")
    removed = sorted(set(before) - set(after))
    if satisfied != removed:
        errors.append("gate_transition_satisfied_not_exact_difference")
    if any(reason != VECTOR_GATE for reason in satisfied):
        errors.append("gate_transition_removed_unrelated_reason")

    available = plan.get("available") is True
    if available and (
        VECTOR_GATE not in before or VECTOR_GATE not in satisfied
    ):
        errors.append("available_plan_did_not_satisfy_exact_vector_gate")
    if not available and VECTOR_GATE in satisfied:
        errors.append("unavailable_plan_satisfied_vector_gate")
    disposition = str(layer.get("Disposition") or "Blocked")
    if after and disposition != "Blocked":
        errors.append("final_reasons_require_blocked_disposition")
    if available and not after and disposition != "Baked":
        errors.append("available_clear_transition_requires_baked_disposition")
    return {
        "valid": not errors,
        "before": before,
        "after": after,
        "satisfied": satisfied,
        "errors": errors,
    }


def _foundation_probe() -> dict[str, Any]:
    import copy

    from PySide6.QtGui import QImage

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import (
        _apply_static_vector_gate_transition,
        package_painter_umg,
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, _row = add_ui_object(
        create_ui_document(128, 128),
        kind="path",
        x=16,
        y=20,
        width=32,
        height=24,
        content={
            "figma_type": "VECTOR",
            "vector_fill_geometry": [
                {"path": "M 0 24 L 16 0 L 32 24 Z", "winding_rule": "nonzero"}
            ],
            "vector_paths": ["M 0 24 L 16 0 L 32 24 Z"],
        },
        style={
            "fill": "#3B82F6FF",
            "fills": [
                {
                    "type": "solid",
                    "visible": True,
                    "color": "#3B82F6FF",
                    "opacity": 1.0,
                    "blend_mode": "normal",
                }
            ],
            "stroke": "#00000000",
            "stroke_width": 0.0,
            "strokes": [],
        },
    )
    document["artboards"][0]["background"] = "#00000000"
    planned_document = painter_ui_to_umg_document(document)
    planned_layer = planned_document["Layers"][0]
    planned_payload = json.loads(planned_layer["PayloadJson"])
    transition = planned_payload["static_vector_bake"]["gate_transition"]
    transition_evidence = _gate_transition_evidence(
        planned_layer,
        planned_payload["static_vector_bake"],
    )
    after = preflight_painter_umg(document)
    with tempfile.TemporaryDirectory(prefix="tiger_static_vector_probe_") as temp:
        package_root = Path(temp) / "package"
        package = package_painter_umg(document, package_root)
        artifact = package["static_bakes"][0] if package["static_bakes"] else {}
        image = QImage(str(artifact.get("png_path") or ""))
        visible_pixels = (
            not image.isNull()
            and any(
                image.pixelColor(x, y).alpha() > 0
                for y in range(image.height())
                for x in range(image.width())
            )
        )
        packaged_layer = package["document"]["Layers"][0]
        resource = next(
            (
                row
                for row in package["document"]["Resources"]
                if row["Id"] == packaged_layer["AssetId"]
            ),
            {},
        )
        persisted = json.loads(
            Path(package["document_path"]).read_text(encoding="utf-8")
        )
        persisted_layer = persisted["Layers"][0]
        packaged_payload = json.loads(packaged_layer["PayloadJson"])
        persisted_payload = json.loads(persisted_layer["PayloadJson"])
        packaged_transition = packaged_payload["static_vector_bake"].get(
            "gate_transition"
        )
        persisted_transition = persisted_payload["static_vector_bake"].get(
            "gate_transition"
        )
        persisted_resource = next(
            (
                row
                for row in persisted["Resources"]
                if row["Id"] == persisted_layer["AssetId"]
            ),
            {},
        )
        materialization = {
            "ok": (
                package["ok"]
                and visible_pixels
                and packaged_layer["Disposition"] == "Baked"
                and bool(resource)
                and persisted_layer == packaged_layer
                and persisted_resource == resource
                and transition_evidence["valid"]
                and packaged_transition == transition
                and persisted_transition == transition
                and transition["after"] == packaged_layer["BlockReasons"]
            ),
            "source_preflight_counts": package["preflight"]["counts"],
            "packaged_preflight_counts": package["packaged_preflight"]["counts"],
            "packaged_disposition": packaged_layer["Disposition"],
            "asset_id": packaged_layer["AssetId"],
            "resource_id": str(resource.get("Id") or ""),
            "persisted_document_matches": persisted_layer == packaged_layer,
            "persisted_resource_matches": persisted_resource == resource,
            "planned_transition_evidence": transition_evidence,
            "packaged_transition_matches": packaged_transition == transition,
            "persisted_transition_matches": persisted_transition == transition,
            "packaged_after_matches_final_reasons": (
                transition["after"] == packaged_layer["BlockReasons"]
            ),
            "visible_pixels": visible_pixels,
            "content_hash": str(artifact.get("content_hash") or ""),
            "pixel_rgba_sha256": str(
                artifact.get("pixel_rgba_sha256") or ""
            ),
        }
    unrelated_document = copy.deepcopy(document)
    unrelated_document["objects"][0]["component_property_bindings"] = {
        "Label": "property-1"
    }
    unrelated = preflight_painter_umg(unrelated_document)
    unrelated_reasons = unrelated["blockers"][0]["reasons"]
    unrelated_gate = (
        "figma_component_property_binding_requires_umg_component_parameter_binding"
    )
    unrelated_gate_preserved = (
        unrelated_gate in unrelated_reasons
        and VECTOR_GATE not in unrelated_reasons
        and unrelated["counts"]["Blocked"] == 1
    )

    # This diagnostic is appended after the base disposition analysis.  It is
    # a regression probe for the exact bug where a transition was once
    # captured too early and therefore omitted later layout/sticky blockers.
    later_blocker_document = copy.deepcopy(document)
    later_blocker_document["objects"][0]["scroll"] = {
        "position": "sticky"
    }
    later_document = painter_ui_to_umg_document(later_blocker_document)
    later_layer = later_document["Layers"][0]
    later_payload = json.loads(later_layer["PayloadJson"])
    later_transition_evidence = _gate_transition_evidence(
        later_layer,
        later_payload["static_vector_bake"],
    )
    later_report = preflight_painter_umg(later_blocker_document)
    later_reason = "prototype_sticky_requires_umg_runtime_binding"
    later_gate_preserved = (
        later_transition_evidence["valid"]
        and later_transition_evidence["before"]
        == sorted([VECTOR_GATE, later_reason])
        and later_transition_evidence["after"] == [later_reason]
        and later_transition_evidence["satisfied"] == [VECTOR_GATE]
        and later_layer["Disposition"] == "Blocked"
        and later_layer["BlockReasons"] == [later_reason]
        and later_report["counts"]["Blocked"] == 1
        and later_report["blockers"][0]["reasons"] == [later_reason]
    )
    sentinel_reasons = [
        "sentinel_00",
        "sentinel-with-dash",
        "sentinel.namespace/value",
        "한글_센티널",
    ]
    _sentinel_after, sentinel_transition = (
        _apply_static_vector_gate_transition(
            [VECTOR_GATE, *sentinel_reasons],
            {"status": "available", "available": True, "reasons": []},
        )
    )
    sentinel_preserved = (
        sentinel_transition["after"] == sorted(sentinel_reasons)
        and sentinel_transition["satisfied"] == [VECTOR_GATE]
    )
    return {
        "geometry": "M 0 24 L 16 0 L 32 24 Z",
        "before": {
            "disposition": (
                "Blocked" if transition["before"] else planned_layer["Disposition"]
            ),
            "reasons": transition["before"],
        },
        "after": {
            "disposition": planned_layer["Disposition"],
            "reasons": transition["after"],
            "satisfied": transition["satisfied"],
            "counts": after["counts"],
            "plan": after["bake_plans"][0],
        },
        "measurement": {
            "before_vector_gate_count": int(
                VECTOR_GATE in transition["before"]
            ),
            "after_vector_gate_count": int(
                VECTOR_GATE in transition["after"]
            ),
            "exact_vector_gate_reduction": int(
                VECTOR_GATE in transition["satisfied"]
            ),
            "before_dispositions": {
                "Baked": 0,
                "Blocked": int(bool(transition["before"])),
            },
            "after_dispositions": {
                "Baked": int(after["counts"]["Baked"]),
                "Blocked": int(after["counts"]["Blocked"]),
            },
        },
        "materialization": materialization,
        "unrelated_gate_probe": {
            "expected_reason": unrelated_gate,
            "actual_reasons": unrelated_reasons,
            "preserved": unrelated_gate_preserved,
        },
        "later_blocker_probe": {
            "expected_reason": later_reason,
            "layer_disposition": later_layer["Disposition"],
            "layer_reasons": later_layer["BlockReasons"],
            "transition": later_transition_evidence,
            "preflight_counts": later_report["counts"],
            "preserved": later_gate_preserved,
        },
        "arbitrary_sentinel_probe": {
            "sentinels": sentinel_reasons,
            "transition": sentinel_transition,
            "preserved": sentinel_preserved,
        },
        "passed": (
            after["ok"]
            and after["counts"]["Baked"] == 1
            and transition == {
                "before": [VECTOR_GATE],
                "after": [],
                "satisfied": [VECTOR_GATE],
            }
            and materialization["ok"]
            and unrelated_gate_preserved
            and later_gate_preserved
            and sentinel_preserved
        ),
    }


def audit_static_vector_bake(
    manifest_path: str | Path,
    assets_root: str | Path,
    *,
    case_ids: set[str] | None = None,
) -> dict[str, Any]:
    from app.painter_ui_figma import import_figma_payload
    from app.painter_ui_umg_adapter import PainterUMGConversionSession
    from tools.qa_painter_ui_figma_document_corpus import (
        _load_case_source,
        _load_manifest,
        _load_selector_case_source,
        _safe_relative_path,
        _verify_case_artifact,
    )

    manifest_path = Path(manifest_path).expanduser().resolve()
    assets_root = Path(assets_root).expanduser().resolve()
    manifest = _select_manifest_cases(_load_manifest(manifest_path), case_ids)
    workload_rows = [
        {
            "id": str(row.get("id") or ""),
            "artifact": {
                "relative_path": str(
                    (row.get("artifact") or {}).get("relative_path") or ""
                ),
                "sha256": str(
                    (row.get("artifact") or {}).get("sha256") or ""
                ).casefold(),
            },
            "selector": row.get("selector") or None,
        }
        for row in manifest["cases"]
    ]
    workload_fingerprint = hashlib.sha256(
        json.dumps(
            workload_rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    after_dispositions: Counter[str] = Counter()
    after_reasons: Counter[str] = Counter()
    transition_before_reasons: Counter[str] = Counter()
    transition_after_reasons: Counter[str] = Counter()
    transition_errors: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    selector_artifact_cache: dict[tuple[str, str], dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="tiger_static_vector_audit_") as temp:
        from app.unreal_umg_static_vector_bake import write_static_vector_bake

        materialization_root = Path(temp)
        for case in manifest["cases"]:
            case_id = str(case["id"])
            source_path = (
                assets_root / _safe_relative_path(case["artifact"]["relative_path"])
            ).resolve()
            payload, image_paths, _details = _load_audit_case_source(
                case,
                source_path,
                selector_artifact_cache,
                load_case_source=_load_case_source,
                load_selector_case_source=_load_selector_case_source,
                verify_case_artifact=_verify_case_artifact,
            )
            document, _import_report = import_figma_payload(
                payload,
                source=str(source_path),
                image_paths=image_paths,
            )
            session = PainterUMGConversionSession(document)
            for artboard_id in session.artboard_ids:
                umg = session.to_umg_document(artboard_id=artboard_id)
                for layer in umg["Layers"]:
                    disposition = str(layer.get("Disposition") or "Blocked")
                    after_dispositions[disposition] += 1
                    reasons = [
                        str(reason)
                        for reason in layer.get("BlockReasons", [])
                    ]
                    after_reasons.update(reasons)
                    try:
                        layer_payload = json.loads(
                            str(layer.get("PayloadJson") or "{}")
                        )
                    except (TypeError, ValueError, json.JSONDecodeError):
                        layer_payload = {}
                    plan = layer_payload.get("static_vector_bake")
                    if not isinstance(plan, dict):
                        transition_errors.append(
                            {
                                "case_id": case_id,
                                "artboard_id": artboard_id,
                                "object_id": str(layer.get("Id") or ""),
                                "errors": ["static_vector_plan_missing"],
                            }
                        )
                        continue
                    transition_evidence = _gate_transition_evidence(layer, plan)
                    transition_before_reasons.update(
                        transition_evidence["before"]
                    )
                    transition_after_reasons.update(
                        transition_evidence["after"]
                    )
                    if not transition_evidence["valid"]:
                        transition_errors.append(
                            {
                                "case_id": case_id,
                                "artboard_id": artboard_id,
                                "object_id": str(layer.get("Id") or ""),
                                "errors": transition_evidence["errors"],
                                "transition": transition_evidence,
                            }
                        )
                    if plan.get("status") == "not_applicable":
                        continue
                    record = {
                        "case_id": case_id,
                        "artboard_id": artboard_id,
                        "object_id": str(layer["Id"]),
                        "name": str(layer["Name"]),
                        "after_disposition": disposition,
                        "remaining_reasons": reasons,
                        "gate_transition": transition_evidence,
                    }
                    if plan.get("available"):
                        record["source_hash"] = str(plan["source_hash"])
                        try:
                            artifact = write_static_vector_bake(
                                plan,
                                materialization_root / case_id,
                            )
                            record["materialized"] = True
                            record["content_hash"] = artifact["content_hash"]
                            record["pixel_rgba_sha256"] = artifact[
                                "pixel_rgba_sha256"
                            ]
                        except (OSError, TypeError, ValueError) as exc:
                            record["materialized"] = False
                            record["materialize_error"] = str(exc)
                        if VECTOR_GATE in transition_evidence["satisfied"]:
                            removed.append(record)
                        else:
                            transition_errors.append(
                                {
                                    "case_id": case_id,
                                    "artboard_id": artboard_id,
                                    "object_id": str(layer.get("Id") or ""),
                                    "errors": [
                                        "available_plan_has_no_actual_gate_reduction"
                                    ],
                                    "transition": transition_evidence,
                                }
                            )
                    else:
                        record["unsafe_reasons"] = list(plan.get("reasons") or [])
                        unavailable.append(record)

    before_dispositions = Counter(after_dispositions)
    before_dispositions["Baked"] = max(0, before_dispositions["Baked"] - sum(
        1 for row in removed if row["after_disposition"] == "Baked"
    ))
    before_dispositions["Blocked"] += sum(
        1 for row in removed if row["after_disposition"] == "Baked"
    )
    before_vector_gate_count = int(transition_before_reasons[VECTOR_GATE])
    after_vector_gate_count = int(transition_after_reasons[VECTOR_GATE])
    foundation_probe = _foundation_probe()
    other_gates_preserved = bool(
        foundation_probe["unrelated_gate_probe"]["preserved"]
    )
    return {
        "schema": "tigercapture.painter.ui.umg_static_vector_bake_audit.v2",
        "case_count": len(manifest["cases"]),
        "selected_case_ids": [str(row["id"]) for row in manifest["cases"]],
        "selector_case_count": sum(
            isinstance(row.get("selector"), dict) for row in manifest["cases"]
        ),
        "workload_fingerprint": workload_fingerprint,
        "before": {
            "dispositions": dict(sorted(before_dispositions.items())),
            "vector_gate_count": before_vector_gate_count,
            "evidence": "actual_serialized_gate_transition_before",
        },
        "after": {
            "dispositions": dict(sorted(after_dispositions.items())),
            "vector_gate_count": after_vector_gate_count,
            "evidence": "actual_final_layer_reasons_and_serialized_transition_after",
        },
        "public_corpus_vector_gate_reduction": len(removed),
        "selected_workload_vector_gate_reduction": len(removed),
        "removed_gate_objects": removed,
        "unsafe_or_unavailable_objects": unavailable,
        "gate_transition_errors": transition_errors,
        "transition_after_matches_final_reason_counts": (
            transition_after_reasons == after_reasons
        ),
        "other_gates_preserved": other_gates_preserved,
        "foundation_probe": foundation_probe,
        "passed": (
            before_vector_gate_count - after_vector_gate_count == len(removed)
            and not transition_errors
            and transition_after_reasons == after_reasons
            and all(VECTOR_GATE not in row["remaining_reasons"] for row in removed)
            and all(row.get("materialized") for row in removed)
            and all(
                VECTOR_GATE in row["remaining_reasons"]
                for row in unavailable
                if row["unsafe_reasons"]
            )
            and foundation_probe["passed"]
            and other_gates_preserved
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default=str(ROOT / "qa_corpus" / "painter_ui_figma_documents" / "manifest.json"),
    )
    parser.add_argument(
        "--assets-root",
        default=str(ROOT / "external" / "assets" / "figma" / "compat_corpus"),
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Audit only this resolved manifest case ID; may be repeated.",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit_static_vector_bake(
        args.manifest,
        args.assets_root,
        case_ids=set(args.case) or None,
    )
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["passed"],
                "case_count": report["case_count"],
                "before_vector_gate_count": report["before"]["vector_gate_count"],
                "after_vector_gate_count": report["after"]["vector_gate_count"],
                "public_corpus_vector_gate_reduction": report[
                    "public_corpus_vector_gate_reduction"
                ],
                "focused_exact_vector_gate_reduction": report[
                    "foundation_probe"
                ]["measurement"]["exact_vector_gate_reduction"],
                "after_baked_count": report["after"]["dispositions"].get("Baked", 0),
                "foundation_probe_baked": report["foundation_probe"]["after"]["counts"]["Baked"],
                "report": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
