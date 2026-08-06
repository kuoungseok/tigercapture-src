from __future__ import annotations

import json
import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _template_document():
    from app.painter_ui_templates import instantiate_ui_template

    document, _report = instantiate_ui_template("mobile_onboarding")
    return document


def test_template_package_store_recent_favorite_and_update_review(
    tmp_path: Path,
) -> None:
    from app.painter_ui_template_store import (
        compare_ui_template_update,
        export_ui_template_package,
        inspect_ui_template_store,
        install_ui_template_package,
        instantiate_stored_ui_template,
        save_user_ui_template,
        set_ui_template_favorite,
    )

    document = _template_document()
    package = export_ui_template_package(
        document,
        tmp_path / "exported.tstemplate",
        template_id="team-mobile",
        name="Team Mobile",
        version=2,
        author="Tiger Team",
    )
    assert Path(package["path"]).is_file()
    installed = install_ui_template_package(
        package["path"],
        store_root=tmp_path / "store",
    )
    assert Path(installed["installed_path"]).is_file()
    store = inspect_ui_template_store(store_root=tmp_path / "store")
    assert any(row["id"] == "team-mobile" for row in store["installed"])

    set_ui_template_favorite(
        "team-mobile",
        True,
        store_root=tmp_path / "store",
    )
    restored, report = instantiate_stored_ui_template(
        "team-mobile",
        store_root=tmp_path / "store",
    )
    assert restored["artboards"]
    assert report["template_version"] == 2
    store = inspect_ui_template_store(store_root=tmp_path / "store")
    assert store["favorites"] == ["team-mobile"]
    assert store["recent"][0] == "team-mobile"

    update = compare_ui_template_update(
        {"id": "team-mobile", "version": 1, "document_sha256": ""},
        package["path"],
    )
    assert update["update_available"] is True
    saved = save_user_ui_template(
        document,
        template_id="saved-screen",
        name="Saved Screen",
        store_root=tmp_path / "store",
    )
    assert Path(saved["installed_path"]).is_file()


def test_review_comments_checkpoints_diff_and_offline_package(
    tmp_path: Path,
) -> None:
    from app.painter_ui_review import (
        add_ui_review_comment,
        create_ui_review_checkpoint,
        diff_ui_checkpoint,
        export_ui_review_package,
        inspect_ui_review,
        update_ui_review_comment,
    )

    document = _template_document()
    object_id = document["objects"][0]["id"]
    document, comment = add_ui_review_comment(
        document,
        object_id=object_id,
        text="Increase contrast",
        author="Reviewer",
    )
    document, checkpoint = create_ui_review_checkpoint(
        document,
        name="Before polish",
    )
    document, updated = update_ui_review_comment(
        document,
        comment["id"],
        {"resolved": True, "reply": "Fixed", "author": "Designer"},
    )
    assert updated["resolved"] is True
    review = inspect_ui_review(document)
    assert review["comment_count"] == 1
    assert review["unresolved_count"] == 0
    diff = diff_ui_checkpoint(document, checkpoint["id"])
    assert diff["after_revision"] >= diff["before_revision"]
    package = export_ui_review_package(document, tmp_path / "review")
    assert Path(package["entrypoint"]).is_file()
    assert (tmp_path / "review" / "inspection.json").is_file()
    assert (tmp_path / "review" / "dev_handoff.json").is_file()


def test_prototype_runtime_and_self_contained_export(tmp_path: Path) -> None:
    from app.painter_ui_prototype import (
        execute_ui_prototype_trigger,
        export_ui_prototype,
        inspect_ui_prototype,
        prototype_initial_state,
    )

    document = _template_document()
    inspection = inspect_ui_prototype(document)
    assert inspection["ok"] is True
    interaction = document["interactions"][0]
    state = execute_ui_prototype_trigger(
        document,
        prototype_initial_state(document),
        source_object_id=interaction["source_object_id"],
        trigger=interaction["trigger"],
    )
    assert interaction["id"] in state["matched_interaction_ids"]
    package = export_ui_prototype(document, tmp_path / "prototype")
    assert package["ok"] is True
    assert Path(package["entrypoint"]).is_file()
    assert "tiger-data" in Path(package["entrypoint"]).read_text(encoding="utf-8")


def test_asset_export_density_svg_atlas_and_manifest(tmp_path: Path) -> None:
    from app.painter_ui_asset_export import export_ui_assets

    _app()
    report = export_ui_assets(
        _template_document(),
        tmp_path / "assets",
        formats=["png", "svg"],
        densities=[1.0, 2.0],
        create_atlas=True,
    )
    assert report["ok"] is True
    manifest = json.loads(
        Path(report["manifest_path"]).read_text(encoding="utf-8")
    )
    assert manifest["schema"] == "tigerstudio.painter.ui.asset_export.v1"
    assert any(row["density"] == 2.0 for row in manifest["artifacts"])
    assert Path(manifest["atlas"]["image"]).is_file()


def test_painter_uses_shared_umg_document_and_package(tmp_path: Path) -> None:
    from app.painter_ui_umg_adapter import (
        package_painter_umg,
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )
    from app.painter_ui_umg_adapter import TIGER_UMG_SCHEMA_VERSION

    document = _template_document()
    umg = painter_ui_to_umg_document(document)
    assert TIGER_UMG_SCHEMA_VERSION == 13
    assert umg["SchemaVersion"] == 18
    assert umg["Provider"] == "painter"
    assert umg["Layers"]
    first_payload = json.loads(
        next(
            row
            for row in umg["Layers"]
            if row["Id"] != "__tiger_artboard_background"
        )["PayloadJson"]
    )
    assert "clip_content" in first_payload
    preflight = preflight_painter_umg(document)
    assert umg["Components"]
    assert sum(preflight["counts"].values()) == len(umg["Layers"]) + sum(
        len(component["Layers"]) for component in umg["Components"]
    )
    package = package_painter_umg(document, tmp_path / "umg")
    assert Path(package["document_path"]).is_file()
    assert package["document"]["Provider"] == "painter"


def test_ai_co_design_requires_plan_supports_preview_partial_apply_and_audit() -> None:
    from app.painter_ui_ai_design import (
        apply_ui_co_design,
        audit_ui_design,
        plan_ui_co_design,
    )

    document = _template_document()
    plan = plan_ui_co_design(
        document,
        prompt="한국어 모바일 결제 화면을 만들어줘",
    )
    assert plan["requires_explicit_apply"] is True
    assert plan["preview_diff"]["change_count"] > 0
    updated, report = apply_ui_co_design(
        document,
        plan,
        selected_operation_ids=[
            "apply-template",
            "adapt-headline",
            "repair-accessibility",
        ],
    )
    assert updated["artboards"]
    assert report["plan_id"] == plan["plan_id"]
    audit = audit_ui_design(updated)
    assert audit["schema"] == "tigerstudio.painter.ui.ai_design_audit.v1"
    assert "delivery" in audit


def test_production_milestone_actions_share_document_and_undo(
    tmp_path: Path,
) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()
    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    expected = {
        "paint.ui.template.store.inspect",
        "paint.ui.template.package.export",
        "paint.ui.template.package.install",
        "paint.ui.template.user.save",
        "paint.ui.template.favorite.set",
        "paint.ui.template.stored.apply",
        "paint.ui.template.update.inspect",
        "paint.ui.review.inspect",
        "paint.ui.review.comment.add",
        "paint.ui.review.comment.update",
        "paint.ui.review.comment.remove",
        "paint.ui.review.checkpoint.create",
        "paint.ui.review.checkpoint.diff",
        "paint.ui.review.export",
        "paint.ui.developer.inspect",
        "paint.ui.prototype.inspect",
        "paint.ui.prototype.trigger",
        "paint.ui.prototype.export",
        "paint.ui.assets.export",
        "paint.ui.figma.compatibility.inspect",
        "paint.ui.figma.import",
        "paint.ui.figma.export",
        "paint.ui.umg.preflight",
        "paint.ui.umg.package",
        "paint.ui.umg.generate",
        "paint.ui.ai.plan",
        "paint.ui.ai.apply",
        "paint.ui.ai.audit",
    }
    assert expected.issubset(action_ids)

    applied = registry.execute(
        "paint.ui.template.stored.apply",
        {
            "template_id": "mobile_onboarding",
            "store_root": str(tmp_path / "templates"),
        },
    ).to_dict()
    assert applied["ok"]
    object_id = dialog._painter_ui_document["objects"][0]["id"]
    comment = registry.execute(
        "paint.ui.review.comment.add",
        {"text": "Check contrast", "object_id": object_id},
    ).to_dict()
    assert comment["ok"]
    checkpoint = registry.execute(
        "paint.ui.review.checkpoint.create",
        {"name": "Review 1"},
    ).to_dict()
    assert checkpoint["ok"]
    prototype = registry.execute(
        "paint.ui.prototype.export",
        {"output_dir": str(tmp_path / "prototype-action")},
    ).to_dict()
    assert prototype["ok"]
    assets = registry.execute(
        "paint.ui.assets.export",
        {
            "output_dir": str(tmp_path / "asset-action"),
            "formats": ["png"],
            "densities": [1.0],
        },
    ).to_dict()
    assert assets["ok"]
    figma = registry.execute(
        "paint.ui.figma.export",
        {"output_dir": str(tmp_path / "figma-action")},
    ).to_dict()
    assert figma["ok"]
    assert Path(figma["result"]["manifest_path"]).is_file()
    umg = registry.execute("paint.ui.umg.preflight", {}).to_dict()
    assert umg["ok"]
    plan = registry.execute(
        "paint.ui.ai.plan",
        {"prompt": "방송용 오버레이 UI를 만들어줘"},
    ).to_dict()
    assert plan["ok"]
    applied_ai = registry.execute(
        "paint.ui.ai.apply",
        {"plan": plan["result"]},
    ).to_dict()
    assert applied_ai["ok"]
    audit = registry.execute("paint.ui.ai.audit", {}).to_dict()
    assert audit["ok"]
    dialog.close()
