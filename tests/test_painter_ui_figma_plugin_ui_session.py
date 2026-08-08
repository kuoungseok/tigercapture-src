from __future__ import annotations

import pytest
import time

from app.painter_ui_document import create_ui_document

from app.painter_ui_figma_plugin_ui_session import (
    PainterFigmaPluginUISession,
    preflight_figma_plugin_ui_source,
)


def test_fp3_session_preserves_showui_and_bidirectional_message_lifecycle() -> None:
    source = """
figma.showUI(__html__, {width:420,height:240,title:'Token maker',themeColors:true});
figma.ui.postMessage({type:'boot',value:1});
figma.ui.onmessage = (message) => {
  figma.ui.postMessage({type:'echo',value:message.value});
};
"""
    html = "<button id='send'>Create</button>"

    with PainterFigmaPluginUISession(source, html, plugin_name="QA") as session:
        assert session.ready["ui"] == {
            "visible": True,
            "width": 420,
            "height": 240,
            "title": "Token maker",
            "themeColors": True,
            "html": html,
            "closed": False,
        }
        assert session.ready["messages"] == [{"type": "boot", "value": 1}]
        state = session.post_ui_message({"type": "create", "value": 7})
        assert state["messages"] == [{"type": "echo", "value": 7}]
        assert state["ui"]["visible"] is True


def test_fp3_session_clamps_ui_size_and_closes_explicitly() -> None:
    session = PainterFigmaPluginUISession(
        "figma.showUI(__html__,{width:10,height:9000,visible:false});",
        "<p>Hidden</p>",
    )
    assert session.ready["ui"]["width"] == 70
    assert session.ready["ui"]["height"] == 1000
    assert session.ready["ui"]["visible"] is False
    closed = session.close()
    assert closed["ui"]["closed"] is True
    assert closed["ui"]["visible"] is False


def test_fp3_preflight_rejects_ambient_authority_and_large_html() -> None:
    assert not preflight_figma_plugin_ui_source("require('fs');figma.showUI('')", "")["ok"]
    report = preflight_figma_plugin_ui_source(
        "figma.showUI(__html__)", "x" * (1024 * 1024 + 1)
    )
    assert report["ok"] is False
    assert "1 MiB" in report["errors"][0]
    with pytest.raises(ValueError, match="must call figma.showUI"):
        PainterFigmaPluginUISession("figma.notify('headless')", "<p>No UI</p>")


def test_fp3_message_handler_timeout_terminates_the_worker() -> None:
    session = PainterFigmaPluginUISession(
        "figma.showUI(__html__);figma.ui.onmessage=()=>{while(true){}};",
        "<button>Hang</button>",
        timeout_ms=100,
    )
    with pytest.raises(RuntimeError, match="timed out"):
        session.post_ui_message({"type": "hang"})
    assert session._process.poll() is not None


def test_fp3_bounded_timer_delivers_async_main_to_ui_push() -> None:
    with PainterFigmaPluginUISession(
        "figma.showUI(__html__);"
        "figma.ui.onmessage=()=>setTimeout(()=>figma.ui.postMessage('later'),25);",
        "<button>Timer</button>",
    ) as session:
        state = session.post_ui_message("go")
        assert state["messages"] == []
        deadline = time.monotonic() + 1.0
        events = []
        while time.monotonic() < deadline and not events:
            events = session.poll_events()
            time.sleep(0.01)
        assert events[0]["event"] == "push"
        assert events[0]["messages"] == ["later"]


def test_fp3_timer_pushes_visibility_changes_without_an_outbound_message() -> None:
    with PainterFigmaPluginUISession(
        "figma.showUI(__html__);"
        "figma.ui.onmessage=()=>{figma.ui.hide();setTimeout(()=>figma.ui.show(),25)};",
        "<button>Blink</button>",
    ) as session:
        hidden = session.post_ui_message("blink")
        assert hidden["ui"]["visible"] is False
        deadline = time.monotonic() + 1.0
        events = []
        while time.monotonic() < deadline and not events:
            events = session.poll_events()
            time.sleep(0.01)
        assert events[0]["event"] == "push"
        assert events[0]["ui"]["visible"] is True
        assert events[0]["messages"] == []


def test_fp3_ui_messages_apply_document_changes_with_stable_created_ids() -> None:
    document = create_ui_document(390, 844)
    source = """
figma.showUI(__html__);
figma.ui.onmessage=(message)=>{
  const node=figma.createRectangle();node.name=message.name;node.resize(80,40);
  figma.currentPage.selection=[node];
};
"""
    with PainterFigmaPluginUISession(source, "<button>Create</button>", document=document) as session:
        first = session.post_ui_message({"name": "First"})
        document, first_report = session.apply_event(document, first)
        second = session.post_ui_message({"name": "Second"})
        document, second_report = session.apply_event(document, second)

    assert [row["name"] for row in document["objects"]] == ["First", "Second"]
    assert len({row["id"] for row in document["objects"]}) == 2
    assert len(first_report["created_object_ids"]) == 1
    assert len(second_report["created_object_ids"]) == 1
    assert document["selection"]["object_ids"] == [document["objects"][1]["id"]]


def test_fp3_plugin_drop_imports_svg_as_frame_with_vector_children() -> None:
    document = create_ui_document(390, 844)
    source = """
figma.showUI(__html__);
figma.on('drop',(event)=>{
  if(event.files[0].type==='image/svg+xml') event.files[0].getTextAsync().then(text=>{
    const node=figma.createNodeFromSvg(text);node.x=event.absoluteX;node.y=event.absoluteY;
    figma.currentPage.selection=[node];
  });
  return false;
});
"""
    svg = '<svg width="24" height="24" fill="none" stroke="#112233" stroke-width="2"><polyline points="2 12 6 12 9 3 15 21 18 12 22 12"/></svg>'
    with PainterFigmaPluginUISession(source, "<p>Drag</p>", document=document) as session:
        state = session.post_plugin_drop({
            "clientX": 120,
            "clientY": 80,
            "files": [{"name": "icon.svg", "type": "image/svg+xml", "text": svg}],
            "dropMetadata": {"parentingStrategy": "page"},
        })
        document, report = session.apply_event(document, state)

    frame = next(row for row in document["objects"] if row["kind"] == "frame")
    vector = next(row for row in document["objects"] if row["kind"] == "path")
    assert (frame["x"], frame["y"], frame["width"], frame["height"]) == (120.0, 80.0, 24.0, 24.0)
    assert vector["parent_id"] == frame["id"]
    assert frame["style"]["fill"] == "#FFFFFFFF"
    assert vector["content"]["vector_paths"][0].startswith("M 2 12")
    assert vector["style"]["stroke"] == "#112233FF"
    assert report["created_object_ids"] == [frame["id"], vector["id"]]
    assert document["selection"]["object_ids"] == [frame["id"]]
