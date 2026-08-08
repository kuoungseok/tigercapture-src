from __future__ import annotations

from pathlib import Path


def _audit_payload(
    contract: dict,
    *,
    enlarged: bool,
) -> dict:
    geometry_key = "enlarged_geometry" if enlarged else "reference_geometry"
    geometry = contract["fixture"][geometry_key]
    rows = contract["layers"]
    sizes: dict[str, str] = {}
    slots: dict[str, str] = {}
    for role, suffix in contract["expected_audit_suffixes"].items():
        key = suffix
        material = rows[role]["Material"]
        fixed = [material["Size"]["X"], material["Size"]["Y"]]
        live = geometry[role]
        binding = contract["expected_bindings"][role]
        if binding == "FixedSize":
            live = [0.0, 0.0]
            host_geometry = fixed
            mid = "unavailable"
        else:
            host_geometry = live
            mid = f"{live[0]:.3f}x{live[1]:.3f}"
        sizes[key] = (
            f"binding={binding};"
            f"fixed={fixed[0]:.3f}x{fixed[1]:.3f};"
            f"geometry={host_geometry[0]:.3f}x{host_geometry[1]:.3f};"
            f"live={live[0]:.3f}x{live[1]:.3f};mid={mid}"
        )
        padding = material["VisualPadding"]
        left = padding["Left"]
        top = padding["Top"]
        right = padding["Right"]
        bottom = padding["Bottom"]
        surface_basis = geometry[role]
        slots[key] = (
            f"position={-left:.3f},{-top:.3f};"
            f"size={surface_basis[0] + left + right:.3f}x"
            f"{surface_basis[1] + top + bottom:.3f};"
            f"padding={left:.3f},{top:.3f},{right:.3f},{bottom:.3f}"
        )
    width, height = (
        contract["fixture"][
            "enlarged_draw_size" if enlarged else "reference_draw_size"
        ]
    )
    return {
        "ok": True,
        "width": width,
        "height": height,
        "rounded_card_size_audit": sizes,
        "rounded_card_visual_slot_audit": slots,
    }


def test_dynamic_size_fixture_exports_schema19_for_only_live_geometry_cards() -> None:
    from tools.qa_painter_ui_unreal_umg_rounded_card_dynamic_size import (
        build_dynamic_size_contract_evidence,
    )

    contract = build_dynamic_size_contract_evidence()

    assert contract["ok"] is True
    assert contract["umg_document"]["SchemaVersion"] == 19
    assert contract["preflight"]["ok"] is True
    assert contract["preflight"]["blockers"] == []
    assert contract["expected_bindings"] == {
        "canvas_dynamic": "WidgetGeometry",
        "overlay_dynamic": "WidgetGeometry",
        "overlay_fixed": "FixedSize",
        "component_dynamic": "WidgetGeometry",
    }
    assert contract["layers"]["canvas_dynamic"]["CanvasSlot"] == {
        "AnchorMinimum": {"X": 0.0, "Y": 0.0},
        "AnchorMaximum": {"X": 1.0, "Y": 0.0},
        "Offsets": {
            "Left": 32.0,
            "Top": 76.0,
            "Right": 32.0,
            "Bottom": 104.0,
        },
        "Alignment": {"X": 0.5, "Y": 0.5},
    }
    assert contract["layers"]["overlay_dynamic"]["FlowSlot"][
        "HorizontalAlignment"
    ] == "Fill"
    assert contract["layers"]["overlay_dynamic"]["FlowSlot"][
        "VerticalAlignment"
    ] == "Fill"
    assert contract["layers"]["overlay_fixed"]["FlowSlot"][
        "HorizontalAlignment"
    ] == "Right"
    assert contract["layers"]["overlay_fixed"]["FlowSlot"][
        "VerticalAlignment"
    ] == "Bottom"
    assert contract["layers"]["canvas_dynamic"]["Material"][
        "VisualPadding"
    ] == {"Left": 11.0, "Top": 23.0, "Right": 27.0, "Bottom": 15.0}
    assert len(contract["umg_document"]["Components"]) == 1
    assert len(contract["umg_document"]["ComponentInstances"]) == 1
    assert contract["component_instance_layer"]["CanvasSlot"][
        "AnchorMinimum"
    ] == {"X": 0.0, "Y": 1.0}
    assert contract["component_instance_layer"]["CanvasSlot"][
        "AnchorMaximum"
    ] == {"X": 1.0, "Y": 1.0}
    assert contract["fixture"]["reference_geometry"][
        "component_dynamic"
    ] == [220.0, 56.0]
    assert contract["fixture"]["enlarged_geometry"][
        "component_dynamic"
    ] == [540.0, 56.0]
    assert contract["known_gaps"] == [
        "same_instance_zero_collapse_restore_not_exercised",
        "draw_widget_dpi_scale_1_5_2_not_exercised",
        "second_same_class_instance_mid_isolation_not_exercised",
    ]


def test_dynamic_size_render_contract_requires_first_pass_live_mid_and_slot() -> None:
    from tools.qa_painter_ui_unreal_umg_rounded_card_dynamic_size import (
        build_dynamic_size_contract_evidence,
        validate_dynamic_size_render_pair,
    )

    contract = build_dynamic_size_contract_evidence()
    reference = _audit_payload(contract, enlarged=False)
    enlarged = _audit_payload(contract, enlarged=True)

    result = validate_dynamic_size_render_pair(reference, enlarged, contract)

    assert result["ok"] is True
    assert all(row["ok"] for row in result["roles"].values())
    assert result["roles"]["canvas_dynamic"]["reference"]["size"] == {
        "binding": "WidgetGeometry",
        "fixed": [576.0, 104.0],
        "geometry": [576.0, 104.0],
        "live": [576.0, 104.0],
        "mid": [576.0, 104.0],
    }
    assert result["roles"]["canvas_dynamic"]["enlarged"][
        "visual_slot"
    ] == {
        "position": [-11.0, -23.0],
        "size": [934.0, 142.0],
        "padding": [11.0, 23.0, 27.0, 15.0],
    }
    assert result["roles"]["overlay_fixed"]["reference"]["size"][
        "mid"
    ] is None
    assert result["roles"]["overlay_fixed"]["enlarged"]["size"][
        "geometry"
    ] == [160.0, 42.0]
    assert result["roles"]["overlay_fixed"]["checks"][
        "fixed_slot_unchanged"
    ] is True
    assert result["roles"]["component_dynamic"]["reference"]["size"][
        "live"
    ] == [220.0, 56.0]
    assert result["roles"]["component_dynamic"]["enlarged"]["size"][
        "live"
    ] == [540.0, 56.0]


def test_dynamic_size_render_contract_rejects_empty_audit_even_when_png_says_ok() -> None:
    from tools.qa_painter_ui_unreal_umg_rounded_card_dynamic_size import (
        build_dynamic_size_contract_evidence,
        validate_dynamic_size_render_pair,
    )

    contract = build_dynamic_size_contract_evidence()
    empty_reference = {
        "ok": True,
        "width": 640,
        "height": 420,
        "rounded_card_size_audit": {},
        "rounded_card_visual_slot_audit": {},
    }
    empty_enlarged = {
        "ok": True,
        "width": 960,
        "height": 600,
        "rounded_card_size_audit": {},
        "rounded_card_visual_slot_audit": {},
    }

    result = validate_dynamic_size_render_pair(
        empty_reference,
        empty_enlarged,
        contract,
    )

    assert result["ok"] is False
    assert result["checks"]["all_roles"] is False
    assert all(
        row["checks"]["audit_paths_present"] is False
        for row in result["roles"].values()
    )


def test_dynamic_size_render_contract_rejects_warm_frame_or_stale_mid_size() -> None:
    from tools.qa_painter_ui_unreal_umg_rounded_card_dynamic_size import (
        build_dynamic_size_contract_evidence,
        validate_dynamic_size_render_pair,
    )

    contract = build_dynamic_size_contract_evidence()
    reference = _audit_payload(contract, enlarged=False)
    enlarged = _audit_payload(contract, enlarged=True)
    canvas_key = contract["expected_audit_suffixes"]["canvas_dynamic"]
    enlarged["rounded_card_size_audit"][canvas_key] = (
        "binding=WidgetGeometry;fixed=576.000x104.000;"
        "geometry=896.000x104.000;"
        "live=896.000x104.000;mid=576.000x104.000"
    )

    result = validate_dynamic_size_render_pair(reference, enlarged, contract)

    assert result["ok"] is False
    assert result["roles"]["canvas_dynamic"]["checks"][
        "first_pass_mid_matches_live"
    ] is False


def test_dynamic_size_run_can_request_generation_reopen_two_renders_and_editor_capture(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import tools.qa_painter_ui_unreal_umg_rounded_card_dynamic_size as qa

    contract = qa.build_dynamic_size_contract_evidence()
    fixture = contract["fixture"]
    component_id = fixture["component_id"]
    component_class = "WBP_TS_C_TestComponent_C"
    widget_classes = {
        fixture["canvas_dynamic_id"]: "TigerStudioRoundedCardHost",
        fixture["overlay_dynamic_id"]: "TigerStudioRoundedCardHost",
        fixture["overlay_fixed_id"]: "TigerStudioRoundedCardHost",
        fixture["component_instance_root_id"]: component_class,
        f"component:{component_id}/{fixture['component_definition_root_id']}":
            "TigerStudioRoundedCardHost",
    }
    generation = {
        "ok": True,
        "generated_asset_loaded": True,
        "generated_asset_class": "WidgetBlueprint",
        "generated_asset_path": "/Game/Test/WBP.WBP",
        "generated_component_count": 1,
        "generated_component_asset_paths": {
            component_id: "/Game/Test/WBP_C.WBP_C"
        },
        "generated_component_class_paths": {
            component_id: "/Game/Test/WBP_C.WBP_TS_C_TestComponent_C"
        },
        "generated_widget_classes": widget_classes,
        "generated_material_paths": [],
    }
    calls: list[tuple] = []
    monkeypatch.setattr(qa, "generate_painter_umg", lambda *args, **kwargs: generation)
    monkeypatch.setattr(
        qa,
        "_ensure_project",
        lambda workspace: workspace / "UnrealProject" / "QA.uproject",
    )
    monkeypatch.setattr(
        qa,
        "_reopen_generated_asset",
        lambda project, asset, **kwargs: {
            "ok": True,
            "asset_loaded": True,
            "asset_class": "WidgetBlueprint",
            "generated_class_loaded": True,
        },
    )

    def fake_render(project, asset, output, *, width, height, timeout_seconds):
        enlarged = (width, height) == qa.ENLARGED_DRAW_SIZE
        calls.append(("render", width, height, Path(output).name))
        return _audit_payload(contract, enlarged=enlarged)

    monkeypatch.setattr(qa, "_render_generated_asset", fake_render)
    monkeypatch.setattr(
        qa,
        "_capture_generated_asset",
        lambda project, asset, output, **kwargs: calls.append(
            ("capture", Path(output).name)
        )
        or {"ok": True, "path": str(output)},
    )

    report = qa.run_dynamic_size_qa(
        tmp_path,
        timeout_seconds=17,
        capture_ui=True,
    )

    assert report["ok"] is True
    assert calls == [
        ("render", 640, 420, "rounded_card_dynamic_size_reference.png"),
        ("render", 960, 600, "rounded_card_dynamic_size_enlarged.png"),
        ("capture", "rounded_card_dynamic_size_editor.png"),
    ]
    assert Path(report["paths"]["fixture_document"]).is_file()
    assert Path(report["paths"]["umg_document"]).is_file()
