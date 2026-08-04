from __future__ import annotations

import copy

import pytest

from app.painter_ui_document import add_ui_object, create_ui_document
from app.painter_ui_figma_plugin_runtime import (
    apply_figma_plugin_result,
    run_figma_plugin_script,
    run_installed_figma_plugin,
)
from app.painter_ui_figma_plugin_registry import PainterFigmaPluginRegistry


def test_fp2_runtime_creates_frame_shapes_and_text_atomically() -> None:
    document = create_ui_document(390, 844)
    source = """
const frame = figma.createFrame();
frame.name = 'Card'; frame.x = 20; frame.y = 30; frame.resize(240, 160);
const rect = figma.createRectangle();
rect.name = 'Surface'; rect.x = 8; rect.y = 8; rect.resize(224, 144);
frame.appendChild(rect);
const ellipse = figma.createEllipse(); ellipse.name = 'Avatar'; ellipse.resize(48, 48);
const text = figma.createText(); await figma.loadFontAsync({family:'Inter',style:'Regular'});
text.characters = 'Hello'; text.name = 'Label';
figma.currentPage.selection = [frame, text];
figma.notify('Created card'); figma.closePlugin();
"""

    result = run_figma_plugin_script(source, document)
    updated, report = apply_figma_plugin_result(document, result)

    assert len(document["objects"]) == 0
    assert [row["kind"] for row in updated["objects"]] == [
        "frame", "rectangle", "ellipse", "text"
    ]
    frame, rectangle, _ellipse, text = updated["objects"]
    assert rectangle["parent_id"] == frame["id"]
    assert frame["style"]["fill"] == "#FFFFFFFF"
    assert text["content"]["text"] == "Hello"
    assert report["notices"] == ["Created card"]
    assert updated["selection"]["object_ids"] == [frame["id"], text["id"]]


def test_fp2_runtime_updates_existing_selection() -> None:
    document, row = add_ui_object(
        create_ui_document(390, 844), kind="rectangle", name="Before", width=40, height=30,
        style={"fills": [{"type": "solid", "color": "#336699CC", "opacity": 0.5}]},
    )
    source = """
const node = figma.currentPage.selection[0];
node.name = 'After'; node.x = 91; node.opacity = 0.5; node.resize(120, 80);
"""

    result = run_figma_plugin_script(source, document)
    updated, report = apply_figma_plugin_result(document, result)
    changed = next(item for item in updated["objects"] if item["id"] == row["id"])

    assert changed["name"] == "After"
    assert changed["x"] == 91
    assert changed["width"] == 120
    assert changed["opacity"] == 0.5
    assert changed["style"]["fills"][0]["color"] == "#336699CC"
    assert changed["style"]["fills"][0]["opacity"] == 0.5
    assert report["created_object_ids"] == []


def test_fp2_runtime_maps_public_fill_stroke_and_text_properties() -> None:
    source = """
const rect=figma.createRectangle();rect.name='Styled';
rect.fills=[{type:'SOLID',color:{r:1,g:0.25,b:0.5},opacity:0.75}];
rect.strokes=[{type:'SOLID',color:{r:0,g:0.5,b:1}}];
rect.strokeWeight=3;rect.strokeAlign='INSIDE';
const text=figma.createText();await figma.loadFontAsync({family:'Inter',style:'Bold'});
text.characters='Type';text.fontName={family:'Inter',style:'Bold'};
text.fontSize=24;text.fontWeight=700;text.textAlignHorizontal='CENTER';
text.lineHeight={unit:'PIXELS',value:32};
text.fills=[{type:'SOLID',color:{r:0.2,g:0.4,b:0.6}}];
"""

    result = run_figma_plugin_script(source, create_ui_document(390, 844))
    updated, _report = apply_figma_plugin_result(create_ui_document(390, 844), result)
    rect, text = updated["objects"]

    assert rect["style"]["fills"][0]["color"] == "#FF4080FF"
    assert rect["style"]["fills"][0]["opacity"] == 0.75
    assert rect["style"]["strokes"][0]["color"] == "#0080FFFF"
    assert rect["style"]["strokes"][0]["width"] == 3
    assert rect["style"]["stroke_align"] == "inside"
    assert text["style"]["font_family"] == "Inter"
    assert text["style"]["font_style"] == "Bold"
    assert text["style"]["font_size"] == 24
    assert text["style"]["font_weight"] == 700
    assert text["style"]["text_align"] == "center"
    assert text["style"]["line_height"] == 32
    assert text["style"]["text_color"] == "#336699FF"


def test_fp2_runtime_blocks_ambient_authority_before_process_start() -> None:
    document = create_ui_document(390, 844)
    for source in (
        "require('fs')",
        "process.exit()",
        "fetch('https://example.com')",
        "Function('return 1')()",
    ):
        with pytest.raises(ValueError, match="Blocked JavaScript capability"):
            run_figma_plugin_script(source, document)


def test_fp2_preflight_routes_plugin_ui_sources_to_fp3() -> None:
    from app.painter_ui_figma_plugin_runtime import preflight_figma_plugin_source

    for source in (
        "figma.showUI(__html__)",
        "figma.ui.postMessage({type:'ready'})",
        "figma.showUI(__uiFiles__.main)",
    ):
        report = preflight_figma_plugin_source(source)
        assert report["ok"] is False
        assert report["requires_plugin_ui"] is True
        assert report["errors"] == ["Figma Plugin UI requires the FP3 message bridge"]


def test_fp2_runtime_timeout_exception_and_unsupported_api_leave_source_unchanged() -> None:
    document = create_ui_document(390, 844)
    before = copy.deepcopy(document)

    with pytest.raises(RuntimeError, match="Unsupported Figma API"):
        run_figma_plugin_script("figma.createPolygon();", document)
    with pytest.raises(RuntimeError, match="timed out"):
        run_figma_plugin_script("while(true){}", document, timeout_ms=100)

    assert document == before


def test_fp2_runs_an_installed_manifest_entry(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "code.js").write_text(
        "const n=figma.createRectangle();n.name='Installed';n.resize(88,44);",
        encoding="utf-8",
    )
    import json
    (source / "manifest.json").write_text(json.dumps({
        "name": "Installed QA", "id": "qa.runtime", "api": "1.0.0",
        "editorType": ["figma"], "main": "code.js",
        "documentAccess": "dynamic-page",
        "networkAccess": {"allowedDomains": ["none"]},
    }), encoding="utf-8")
    installed = tmp_path / "installed"
    registry = PainterFigmaPluginRegistry([installed], install_root=installed)
    registry.install(source)

    updated, report = run_installed_figma_plugin(
        registry, "qa.runtime", create_ui_document(390, 844)
    )

    assert report["plugin_id"] == "qa.runtime"
    assert updated["objects"][0]["name"] == "Installed"
    assert updated["objects"][0]["width"] == 88
