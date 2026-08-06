from __future__ import annotations

import copy
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.ui_motion_binding import (
    UIMotionBinding,
    set_ui_motion_bindings,
)
from app.painter_ui_document import add_ui_object, create_ui_document
from app.painter_ui_motion_bridge import attach_motion_composition


def _app() -> QApplication:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def _linked_case(
    *,
    kind: str = "rectangle",
    autoplay: bool = True,
    loop: bool = True,
    trigger: str = "",
) -> tuple[dict, MotionComposition, UIMotionBinding]:
    document = create_ui_document(160, 90, name="Flipbook Workflow")
    document, target = add_ui_object(
        document,
        kind=kind,
        name="Animated Card",
        x=10,
        y=12,
        width=32,
        height=24,
    )
    document["selection"] = {"object_id": target["id"]}
    layer = MotionLayer(
        id=target["id"],
        name="Animated Card",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "shape": "rectangle",
                "width": 8,
                "height": 8,
                "fill": "#37A0FF",
                "stroke": "transparent",
                "stroke_width": 0,
            },
        ),
        out_ms=1000,
    )
    layer.transform.position.default = [4, 4]
    composition = MotionComposition(
        id="workflow-composition",
        name="Workflow Composition",
        width=8,
        height=8,
        fps=2.0,
        duration_ms=1000,
        revision=5,
        layers=[layer],
    )
    binding = UIMotionBinding(
        id="workflow-binding",
        source_document_id=str(document["document_id"]),
        source_object_id=target["id"],
        host_layer_id=target["id"],
        layer_ids=[target["id"]],
        property_names=["opacity"],
        scope="loop" if loop else "transition",
        trigger=trigger,
        autoplay=autoplay,
        loop=loop,
    )
    set_ui_motion_bindings(composition, [binding])
    document = attach_motion_composition(
        document,
        target["id"],
        composition.id,
        binding_id=binding.id,
        composition_revision=composition.revision,
    )
    return document, composition, binding


def test_true_untriggered_autoplay_loop_bakes_as_ambient(
    tmp_path: Path,
) -> None:
    _app()
    from app.painter_ui_flipbook_workflow import bake_linked_motion_flipbook

    document, composition, binding = _linked_case()
    original = copy.deepcopy(document)

    updated, report = bake_linked_motion_flipbook(
        document,
        {composition.id: composition},
        tmp_path,
    )

    assert document == original
    assert updated is not document
    assert report["ok"] is True
    assert report["changed"] is True
    assert report["binding_id"] == binding.id
    assert report["playback_scope"] == "ambient_loop"
    assert report["playback_decision"] == {
        "autoplay": True,
        "loop": True,
        "binding_trigger": "",
        "interaction_trigger_ids": [],
        "ambient_requires": "autoplay_and_loop_without_interaction_trigger",
    }
    assert report["material_ready"] is True
    assert report["block_reasons"] == []
    assert report["shader_policy"]["arbitrary_hlsl"] == "forbidden"


@pytest.mark.parametrize(
    ("autoplay", "loop", "trigger"),
    [
        (False, True, ""),
        (True, False, ""),
        (True, True, "click"),
    ],
)
def test_non_ambient_binding_classifies_as_event_triggered(
    autoplay: bool,
    loop: bool,
    trigger: str,
) -> None:
    from app.painter_ui_flipbook_workflow import (
        classify_flipbook_playback_scope,
    )

    binding = UIMotionBinding(
        autoplay=autoplay,
        loop=loop,
        trigger=trigger,
    )
    assert classify_flipbook_playback_scope(binding) == "event_triggered"


def test_native_interaction_keeps_event_time_origin_blocker(
    tmp_path: Path,
) -> None:
    _app()
    from app.painter_ui_flipbook_workflow import bake_linked_motion_flipbook

    document, composition, binding = _linked_case()
    object_id = str(document["selection"]["object_id"])
    document["interactions"].append(
        {
            "id": "trigger-animation",
            "name": "Play on click",
            "source_object_id": object_id,
            "trigger": "click",
            "action": "play_animation",
            "motion_clip_id": binding.id,
            "enabled": True,
        }
    )

    updated, report = bake_linked_motion_flipbook(
        document,
        {composition.id: composition},
        tmp_path,
    )

    blocker = "flipbook_trigger_requires_dynamic_material_time_origin"
    assert report["playback_scope"] == "event_triggered"
    assert report["playback_decision"]["interaction_trigger_ids"] == [
        "trigger-animation"
    ]
    assert report["material_ready"] is False
    assert report["block_reasons"] == [blocker]
    target = next(row for row in updated["objects"] if row["id"] == object_id)
    assert target["content"]["flipbook_bake"]["block_reasons"] == [blocker]
    assert updated["interactions"] == document["interactions"]


def test_unsupported_target_fails_before_output_and_never_mutates(
    tmp_path: Path,
) -> None:
    from app.painter_ui_flipbook_workflow import (
        PainterUIFlipbookWorkflowError,
        bake_linked_motion_flipbook,
    )

    document, composition, _binding = _linked_case(kind="text")
    original = copy.deepcopy(document)

    with pytest.raises(PainterUIFlipbookWorkflowError) as caught:
        bake_linked_motion_flipbook(
            document,
            {composition.id: composition},
            tmp_path,
        )

    assert caught.value.block_reasons == (
        "motion_flipbook_workflow_object_kind_unsupported:text",
    )
    assert document == original
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("stable_id", ["1:2", "section/card", ".."])
def test_storage_segment_is_stable_windows_safe_and_not_traversable(
    stable_id: str,
) -> None:
    from app.painter_ui_flipbook_workflow import (
        painter_ui_flipbook_storage_segment,
    )

    first = painter_ui_flipbook_storage_segment(stable_id)
    second = painter_ui_flipbook_storage_segment(stable_id)

    assert first == second
    assert first not in {".", ".."}
    assert not any(character in first for character in '<>:"/\\|?*')
    assert len(first.rsplit("-", 1)[-1]) == 12


def test_output_directory_is_resolved_inside_app_data_and_rejects_empty_root(
    tmp_path: Path,
) -> None:
    from app.painter_ui_flipbook_workflow import (
        PainterUIFlipbookWorkflowError,
        painter_ui_flipbook_output_directory,
    )

    root = (tmp_path / "app-data").resolve()
    output = painter_ui_flipbook_output_directory(
        root,
        "figma-document:1/2",
        "../object:3/4",
    )

    assert root in output.parents
    assert output.parents[1].name == "painter_ui_flipbooks"
    assert not any(character in output.name for character in '<>:"/\\|?*')
    assert ".." not in output.parts[len(root.parts) :]
    with pytest.raises(PainterUIFlipbookWorkflowError) as caught:
        painter_ui_flipbook_output_directory("", "document", "object")
    assert caught.value.block_reasons == (
        "motion_flipbook_workflow_app_data_location_missing",
    )
    with pytest.raises(PainterUIFlipbookWorkflowError) as caught:
        painter_ui_flipbook_output_directory(
            tmp_path / "debugCapture",
            "document",
            "object",
        )
    assert caught.value.block_reasons == (
        "motion_flipbook_workflow_app_data_location_disposable",
    )


def test_drawing_wiring_uses_durable_object_directory_and_undo_before_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _app()
    from app.drawing import PaintDialog
    import app.painter_ui_flipbook_workflow as workflow_module

    original = {
        "document_id": "ui-doc-runtime",
        "revision": 4,
        "selection": {"object_id": "ui-object-runtime"},
        "objects": [],
    }
    updated = {**original, "revision": 5}
    calls: list[tuple[str, object]] = []

    def fake_workflow(document, compositions, output_dir, *, object_id):
        assert document is original
        assert set(compositions) == {"motion-runtime"}
        assert object_id == "ui-object-runtime"
        assert Path(output_dir).parents[1].name == "painter_ui_flipbooks"
        assert Path(output_dir).parent.name.startswith("ui-doc-runtime-")
        assert Path(output_dir).name.startswith("ui-object-runtime-")
        calls.append(("workflow", Path(output_dir)))
        return updated, {
            "ok": True,
            "changed": True,
            "block_reasons": [],
            "atlas_path": str(Path(output_dir) / "atlas.png"),
        }

    monkeypatch.setattr(
        workflow_module,
        "bake_linked_motion_flipbook",
        fake_workflow,
    )

    class Owner:
        _bake_selected_painter_ui_flipbook = (
            PaintDialog._bake_selected_painter_ui_flipbook
        )

        def __init__(self) -> None:
            self._painter_ui_document = original
            self._painter_ui_motion_compositions = {"motion-runtime": object()}
            self._painter_document_dirty = False

        def _painter_ui_production_status(self, text: str) -> None:
            calls.append(("status", text))

        def _push_undo_state(self, label: str) -> None:
            assert self._painter_ui_document is original
            calls.append(("undo", label))

        def _refresh_painter_ui_overlay(self) -> None:
            assert self._painter_ui_document is updated
            assert self._painter_document_dirty is True
            calls.append(("refresh", True))

    owner = Owner()
    report = owner._bake_selected_painter_ui_flipbook()

    assert report["ok"] is True
    assert owner._painter_ui_document is updated
    assert owner._painter_document_dirty is True
    assert [name for name, _value in calls].index("undo") < [
        name for name, _value in calls
    ].index("refresh")
