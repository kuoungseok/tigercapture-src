from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from PIL import Image


CLEAN_CASE_IDS = (
    "figma-rust.tag.fragment",
    "figpot.rectangle.file",
    "vue-low-code.gradient.file",
)


def _write_png(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (240, 140), color).save(path)


def test_release_manifest_resolves_100_cases_and_current_clean_three() -> None:
    import tools.qa_painter_ui_figma_corpus_unreal_umg as corpus_ue

    manifest, selected = corpus_ue.load_release_cases(
        corpus_ue.DEFAULT_MANIFEST,
        case_ids=CLEAN_CASE_IDS,
    )

    assert len(manifest["cases"]) == 100
    assert [row["id"] for row in selected] == list(CLEAN_CASE_IDS)
    selector_cache: dict[tuple[str, str], dict[str, Any]] = {}
    assets_root = (corpus_ue.ROOT / manifest["storage_root"]).resolve()
    for item in selected:
        loaded = corpus_ue._load_imported_case(
            item,
            assets_root,
            selector_cache,
        )
        preflight = corpus_ue._preflight_document(loaded["document"])
        assert preflight["clean"] is True
        assert preflight["artboard_count"] >= 1
        assert preflight["blocker_reasons"] == {}


def test_unreal_case_reuses_generation_reopen_render_and_capture_helpers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import tools.qa_painter_ui_figma_corpus_unreal_umg as corpus_ue
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(320, 180, name="Focused UE QA")
    document, _text = add_ui_object(
        document,
        kind="text",
        name="Evidence",
        x=24,
        y=32,
        width=180,
        height=40,
        content={"text": "Figma corpus"},
    )
    calls: list[str] = []

    monkeypatch.setattr(
        corpus_ue,
        "_ensure_project",
        lambda workspace: workspace / "UnrealProject" / "QA.uproject",
    )

    def fake_generate(
        value: Mapping[str, Any],
        **_kwargs,
    ) -> dict[str, Any]:
        calls.append("generate")
        exported, expectations = corpus_ue._umg_document_expectations(
            value,
            layout_expectations=[],
        )
        return {
            "ok": True,
            "generated_asset_path": "/Game/QA/WBP.WBP",
            "generated_asset_loaded": True,
            "generated_asset_class": "WidgetBlueprint",
            "generated_widget_count": expectations["expected_widget_count"],
            "generated_material_paths": [],
            "imported_asset_paths": [],
            "generated_component_count": len(exported.get("Components") or []),
            "generated_component_asset_paths": {},
            "generated_component_class_paths": {},
            "generated_widget_classes": dict(
                expectations["expected_widget_classes"]
            ),
        }

    def fake_reopen(
        _project: Path,
        _asset_path: str,
        **kwargs,
    ) -> dict[str, Any]:
        calls.append("reopen")
        return {
            "ok": True,
            "expected_widget_classes": kwargs["expected_widget_classes"],
        }

    def fake_render(
        _project: Path,
        _asset_path: str,
        output_path: Path,
        *,
        width: int,
        height: int,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        calls.append("render")
        _write_png(output_path, (35, 85, 150))
        return {
            "ok": True,
            "output_path": str(output_path),
            "width": width,
            "height": height,
            "pixel_evidence": {"visible_content": True},
        }

    def fake_capture(
        _project: Path,
        _asset_path: str,
        output_path: Path,
        **_kwargs,
    ) -> dict[str, Any]:
        calls.append("capture")
        _write_png(output_path, (30, 120, 75))
        return {
            "ok": True,
            "status": "captured",
            "path": str(output_path),
            "backend": "wgc_window",
        }

    monkeypatch.setattr(corpus_ue, "generate_painter_umg", fake_generate)
    monkeypatch.setattr(corpus_ue, "_reopen_generated_asset", fake_reopen)
    monkeypatch.setattr(corpus_ue, "_render_generated_asset", fake_render)
    monkeypatch.setattr(corpus_ue, "_capture_generated_asset", fake_capture)

    result = corpus_ue._run_unreal_case(
        {"id": "clean.case"},
        document,
        tmp_path / "case",
        90,
        True,
    )

    assert result["ok"] is True
    assert calls == ["generate", "reopen", "render", "capture"]
    assert result["generation_contract"]["ok"] is True
    assert Path(result["paths"]["renderer"]).is_file()
    assert Path(result["paths"]["editor_screenshot"]).is_file()
    assert Path(result["paths"]["report"]).is_file()


def test_unreal_case_reopen_uses_component_resource_owner_assets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import tools.qa_painter_ui_figma_corpus_unreal_umg as corpus_ue

    component_id = "component-switch"
    root_asset = "/Game/QA/WBP_Root.WBP_Root"
    component_asset = "/Game/QA/Components/WBP_Switch.WBP_Switch"
    material_asset = "/Game/QA/Materials/M_Switch.M_Switch"
    texture_asset = "/Game/QA/Textures/T_Switch.T_Switch"
    document = {
        "document_id": "component-resource-owner",
        "active_artboard_id": "artboard",
        "artboards": [
            {
                "id": "artboard",
                "name": "Artboard",
                "width": 320,
                "height": 180,
            }
        ],
        "objects": [],
    }
    exported = {
        "Layers": [],
        "Components": [{"Id": component_id, "Layers": []}],
        "ComponentInstances": [],
    }
    expectations = {
        "active_artboard_id": "artboard",
        "expected_widget_count": 0,
        "expected_material_count": 1,
        "expected_texture_count": 1,
        "expected_widget_classes": {},
        "material_layers": [
            {
                "id": "switch-track",
                "component_id": component_id,
                "generator": "tiger_ui_rounded_card_sdf_custom_hlsl_v1",
                "stop_count": 2,
            }
        ],
        "image_fill_layers": [
            {
                "id": "switch-icon",
                "component_id": component_id,
                "asset_id": "switch-texture",
            }
        ],
    }
    monkeypatch.setattr(
        corpus_ue,
        "_umg_document_expectations",
        lambda *_args, **_kwargs: (exported, expectations),
    )
    monkeypatch.setattr(
        corpus_ue,
        "_ensure_project",
        lambda workspace: workspace / "UnrealProject" / "QA.uproject",
    )
    monkeypatch.setattr(
        corpus_ue,
        "generate_painter_umg",
        lambda *_args, **_kwargs: {
            "ok": True,
            "generated_asset_path": root_asset,
            "generated_asset_loaded": True,
            "generated_asset_class": "WidgetBlueprint",
            "generated_widget_count": 0,
            "generated_widget_classes": {},
            "generated_material_paths": [material_asset],
            "imported_asset_paths": [texture_asset],
            "generated_component_count": 1,
            "generated_component_asset_paths": {
                component_id: component_asset
            },
            "generated_component_class_paths": {
                component_id: component_asset + "_C"
            },
        },
    )
    reopen_kwargs: dict[str, Any] = {}

    def fake_reopen(_project: Path, _asset_path: str, **kwargs) -> dict:
        reopen_kwargs.update(kwargs)
        return {"ok": True}

    def fake_render(
        _project: Path,
        _asset_path: str,
        output_path: Path,
        **_kwargs,
    ) -> dict:
        _write_png(output_path, (45, 90, 135))
        return {"ok": True, "output_path": str(output_path)}

    monkeypatch.setattr(corpus_ue, "_reopen_generated_asset", fake_reopen)
    monkeypatch.setattr(corpus_ue, "_render_generated_asset", fake_render)

    result = corpus_ue._run_unreal_case(
        {"id": "component.resource.owner"},
        document,
        tmp_path / "case",
        90,
        False,
    )

    assert result["ok"] is True
    assert reopen_kwargs["material_owner_asset_paths"] == [component_asset]
    assert reopen_kwargs["texture_owner_asset_paths"] == [component_asset]
    assert reopen_kwargs["material_paths"] == [material_asset]
    assert reopen_kwargs["texture_paths"] == [texture_asset]


def test_batch_records_blocked_reasons_links_painter_and_continues_failures(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import tools.qa_painter_ui_figma_corpus_unreal_umg as corpus_ue

    items = [
        {"id": "clean.one", "title": "Clean One", "format": "file"},
        {"id": "blocked.one", "title": "Blocked One", "format": "file"},
        {"id": "clean.two", "title": "Clean Two", "format": "file"},
    ]
    monkeypatch.setattr(
        corpus_ue,
        "load_release_cases",
        lambda *_args, **_kwargs: (
            {"cases": items, "storage_root": str(tmp_path)},
            items,
        ),
    )

    def fake_load(
        item: Mapping[str, Any],
        _assets_root: Path,
        _selector_cache,
    ) -> dict[str, Any]:
        case_id = str(item["id"])
        return {
            "document": {
                "document_id": case_id,
                "active_artboard_id": "artboard",
                "artboards": [
                    {
                        "id": "artboard",
                        "name": "Artboard",
                        "width": 240,
                        "height": 140,
                    }
                ],
                "objects": [],
            },
            "import_report": {"object_count": 0},
            "source_path": str(tmp_path / f"{case_id}.json"),
            "source_details": {"kind": "json"},
            "artifact": {},
            "selector": {},
        }

    def fake_preflight(document: Mapping[str, Any]) -> dict[str, Any]:
        blocked = document["document_id"] == "blocked.one"
        reasons = {"unsupported_blur": 1} if blocked else {}
        return {
            "clean": not blocked,
            "artboard_count": 1,
            "clean_artboard_count": 0 if blocked else 1,
            "counts": {"Blocked": 1} if blocked else {"Native": 1},
            "blocker_reasons": reasons,
            "errors": [],
            "artboards": [
                {
                    "id": "artboard",
                    "ok": not blocked,
                    "blocker_reasons": reasons,
                }
            ],
        }

    monkeypatch.setattr(corpus_ue, "_load_imported_case", fake_load)
    monkeypatch.setattr(corpus_ue, "_preflight_document", fake_preflight)

    painter_render = tmp_path / "painter_renders" / "blocked.one.png"
    _write_png(painter_render, (120, 75, 40))
    painter_report = tmp_path / "painter_report.json"
    painter_report.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "blocked.one",
                        "render_smoke": {
                            "passed": True,
                            "png_path": str(painter_render),
                            "artboards": [],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_unreal(
        item: Mapping[str, Any],
        _document: Mapping[str, Any],
        case_dir: Path,
        _timeout_seconds: int,
        _capture_ui: bool,
    ) -> dict[str, Any]:
        case_id = str(item["id"])
        calls.append(case_id)
        renderer = case_dir / "painter_umg_fwidget_renderer.png"
        editor = case_dir / "painter_umg_unreal_editor.png"
        _write_png(renderer, (40, 70, 150))
        _write_png(editor, (35, 115, 75))
        return {
            "ok": case_id == "clean.one",
            "paths": {
                "renderer": str(renderer),
                "editor_screenshot": str(editor),
            },
            "renderer": {"ok": True, "output_path": str(renderer)},
            "editor_capture": {"ok": True, "path": str(editor)},
        }

    report = corpus_ue.run_figma_corpus_unreal_umg_qa(
        tmp_path / "manifest.json",
        tmp_path / "output",
        painter_report_path=painter_report,
        painter_renders_root=painter_render.parent,
        unreal_runner=fake_unreal,
    )

    assert calls == ["clean.one", "clean.two"]
    assert report["ok"] is False
    assert report["summary"]["clean_cases"] == 2
    assert report["summary"]["blocked_cases"] == 1
    assert report["summary"]["unreal_passed"] == 1
    assert report["summary"]["unreal_failed"] == 1
    assert report["summary"]["blocker_reason_totals"] == {
        "unsupported_blur": 1
    }
    blocked = next(row for row in report["cases"] if row["id"] == "blocked.one")
    assert blocked["status"] == "skipped_blocked"
    assert blocked["preflight"]["blocker_reasons"] == {
        "unsupported_blur": 1
    }
    assert blocked["painter_evidence"]["exists"] is True
    assert blocked["painter_evidence"]["is_unreal_evidence"] is False
    assert report["contact_sheet"]["unreal_fwidget_renderer_cells"] == 2
    assert report["contact_sheet"]["painter_blocked_cells"] == 1
    assert report["contact_sheet"][
        "painter_cells_are_not_unreal_evidence"
    ] is True
    for key in ("report", "index", "contact_sheet"):
        assert Path(report["paths"][key]).is_file()
    index = Path(report["paths"]["index"]).read_text(encoding="utf-8")
    assert "unsupported_blur×1" in index
    assert "Painter preview" in index
    assert "not Unreal" in index
