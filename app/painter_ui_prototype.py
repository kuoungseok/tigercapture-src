"""Deterministic Painter UI prototype runtime and self-contained HTML export."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document, validate_ui_document


PROTOTYPE_SCHEMA = "tigerstudio.painter.ui.prototype.v1"
PROTOTYPE_PACKAGE_SCHEMA = "tigerstudio.painter.ui.prototype_package.v1"


def prototype_initial_state(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    return {
        "schema": PROTOTYPE_SCHEMA,
        "document_id": document["document_id"],
        "artboard_id": document["active_artboard_id"],
        "history": [],
        "overlay_artboard_ids": [],
        "object_states": {},
        "object_visibility": {
            row["id"]: bool(row["visible"]) for row in document["objects"]
        },
        "object_opacity": {
            row["id"]: float(row["opacity"]) for row in document["objects"]
        },
        "material_scalars": {},
        "variables": {},
        "variable_modes": {},
        "events": [],
    }


def execute_ui_prototype_trigger(
    value: Mapping[str, Any],
    state: Mapping[str, Any] | None,
    *,
    source_object_id: str,
    trigger: str,
    key: str = "",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    runtime = dict(state or prototype_initial_state(document))
    runtime["history"] = list(runtime.get("history") or [])
    runtime["overlay_artboard_ids"] = list(
        runtime.get("overlay_artboard_ids") or []
    )
    runtime["object_states"] = dict(runtime.get("object_states") or {})
    runtime["object_visibility"] = dict(runtime.get("object_visibility") or {})
    runtime["object_opacity"] = dict(runtime.get("object_opacity") or {})
    runtime["material_scalars"] = dict(runtime.get("material_scalars") or {})
    runtime["variables"] = dict(runtime.get("variables") or {})
    runtime["variable_modes"] = dict(runtime.get("variable_modes") or {})
    runtime["events"] = list(runtime.get("events") or [])
    matched = []
    for interaction in document["interactions"]:
        if not interaction["enabled"]:
            continue
        if interaction["source_object_id"] != str(source_object_id):
            continue
        if interaction["trigger"] != str(trigger).strip().casefold():
            continue
        parameters = dict(interaction.get("parameters") or {})
        required_key = str(parameters.get("key") or "")
        if required_key and required_key.casefold() != str(key).casefold():
            continue
        action = interaction["action"]
        target_artboard = interaction["target_artboard_id"]
        target_object = interaction["target_object_id"]
        if action == "navigate" and target_artboard:
            runtime["history"].append(runtime["artboard_id"])
            runtime["artboard_id"] = target_artboard
        elif action == "back" and runtime["history"]:
            runtime["artboard_id"] = runtime["history"].pop()
        elif action == "open_overlay" and target_artboard:
            if target_artboard not in runtime["overlay_artboard_ids"]:
                runtime["overlay_artboard_ids"].append(target_artboard)
        elif action == "close_overlay":
            if target_artboard:
                runtime["overlay_artboard_ids"] = [
                    row
                    for row in runtime["overlay_artboard_ids"]
                    if row != target_artboard
                ]
            elif runtime["overlay_artboard_ids"]:
                runtime["overlay_artboard_ids"].pop()
        elif action == "swap_overlay" and target_artboard:
            if runtime["overlay_artboard_ids"]:
                runtime["overlay_artboard_ids"][-1] = target_artboard
            else:
                runtime["overlay_artboard_ids"].append(target_artboard)
        elif action in {"change_state", "change_variant"} and target_object:
            runtime["object_states"][target_object] = str(
                parameters.get("state")
                or parameters.get("variant")
                or interaction.get("name")
                or ""
            )
        elif action == "set_visibility" and target_object:
            runtime["object_visibility"][target_object] = bool(
                parameters.get("visible", True)
            )
        elif action == "set_opacity" and target_object:
            runtime["object_opacity"][target_object] = min(
                1.0,
                max(0.0, float(parameters.get("opacity", 1.0))),
            )
        elif action == "set_material_scalar" and target_object:
            scalar = str(parameters.get("name") or "value")
            runtime["material_scalars"].setdefault(target_object, {})[
                scalar
            ] = float(parameters.get("value", 0.0))
        elif action == "set_variable":
            variable_id = str(parameters.get("variable_id") or "")
            if variable_id:
                runtime["variables"][variable_id] = parameters.get("value")
        elif action == "set_variable_mode":
            collection_id = str(parameters.get("collection_id") or "")
            if collection_id:
                runtime["variable_modes"][collection_id] = str(
                    parameters.get("mode_id") or ""
                )
        elif action in {"scroll_to", "conditional_branch"}:
            runtime["events"].append(
                {
                    "action": action,
                    "source_object_id": source_object_id,
                    "target_object_id": target_object,
                    "target_artboard_id": target_artboard,
                    "parameters": parameters,
                }
            )
        elif action in {"play_animation", "play_sound"}:
            runtime["events"].append(
                {
                    "action": action,
                    "source_object_id": source_object_id,
                    "target_object_id": target_object,
                    "parameters": parameters,
                }
            )
        matched.append(interaction["id"])
    runtime["matched_interaction_ids"] = matched
    return runtime


def inspect_ui_prototype(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    validation = validate_ui_document(document)
    from app.painter_ui_document import (
        UI_INTERACTION_ACTIONS,
        UI_INTERACTION_TRIGGERS,
    )

    supported_triggers = set(UI_INTERACTION_TRIGGERS)
    supported_actions = set(UI_INTERACTION_ACTIONS)
    unsupported = [
        row["id"]
        for row in document["interactions"]
        if row["trigger"] not in supported_triggers
        or row["action"] not in supported_actions
    ]
    return {
        "schema": PROTOTYPE_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "interaction_count": len(document["interactions"]),
        "unsupported_interaction_ids": unsupported,
        "validation_errors": validation["errors"],
        "ok": validation["ok"] and not unsupported,
    }


def _object_html(row: Mapping[str, Any]) -> str:
    style = dict(row.get("style") or {})
    content = dict(row.get("content") or {})
    fill = html.escape(str(style.get("fill") or "transparent"))
    stroke = html.escape(str(style.get("stroke") or "transparent"))
    radius = float(style.get("radius", 0.0) or 0.0)
    text = html.escape(str(content.get("text") or row["name"]))
    role = html.escape(
        str((row.get("accessibility") or {}).get("role") or "group")
    )
    label = html.escape(
        str((row.get("accessibility") or {}).get("label") or row["name"])
    )
    return (
        '<div class="ui-object kind-%s" id="%s" role="%s" aria-label="%s" '
        'tabindex="0" style="left:%spx;top:%spx;width:%spx;height:%spx;'
        'opacity:%s;display:%s;background:%s;border:%spx solid %s;'
        'border-radius:%spx;transform:rotate(%sdeg)">%s</div>'
        % (
            html.escape(str(row["kind"])),
            html.escape(str(row["id"])),
            role,
            label,
            float(row["x"]),
            float(row["y"]),
            float(row["width"]),
            float(row["height"]),
            float(row["opacity"]),
            "block" if row["visible"] else "none",
            fill,
            float(style.get("stroke_width", 0.0) or 0.0),
            stroke,
            radius,
            float(row["rotation"]),
            text if row["kind"] in {"text", "button"} else "",
        )
    )


def export_ui_prototype(
    value: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    inspection = inspect_ui_prototype(document)
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    data_json = json.dumps(
        {
            "document": document,
            "initial_state": prototype_initial_state(document),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    artboards = []
    for artboard in document["artboards"]:
        children = "".join(
            _object_html(row)
            for row in sorted(
                (
                    row
                    for row in document["objects"]
                    if row["artboard_id"] == artboard["id"]
                ),
                key=lambda row: (row["z_index"], row["id"]),
            )
        )
        artboards.append(
            '<section class="artboard" id="artboard-%s" '
            'style="width:%spx;height:%spx">%s</section>'
            % (
                html.escape(artboard["id"]),
                int(artboard["width"]),
                int(artboard["height"]),
                children,
            )
        )
    page = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Tiger Studio UI Prototype</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#17191d;color:#f4f5f7;font:14px system-ui}
#stage{min-height:100vh;display:grid;place-items:center;padding:24px;overflow:auto}
.artboard{display:none;position:relative;background:#fff;color:#111;overflow:hidden;
box-shadow:0 16px 60px #0008;transform-origin:top left}
.artboard.active{display:block}.artboard.overlay{display:block;position:absolute;z-index:100}
.ui-object{position:absolute;overflow:hidden;display:grid;place-items:center}
.ui-object:focus{outline:3px solid #4da3ff;outline-offset:2px}
</style></head><body><main id="stage">%s</main>
<script id="tiger-data" type="application/json">%s</script>
<script>
const data=JSON.parse(document.getElementById("tiger-data").textContent);
let state=data.initial_state;
const rows=data.document.interactions.filter(x=>x.enabled);
function render(){
 document.querySelectorAll(".artboard").forEach(el=>{
  const id=el.id.replace("artboard-","");
  el.classList.toggle("active",id===state.artboard_id);
  el.classList.toggle("overlay",state.overlay_artboard_ids.includes(id));
 });
 Object.entries(state.object_visibility).forEach(([id,v])=>{
  const el=document.getElementById(id);if(el)el.style.display=v?"grid":"none";
 });
 Object.entries(state.object_opacity).forEach(([id,v])=>{
  const el=document.getElementById(id);if(el)el.style.opacity=v;
 });
}
function fire(id,trigger,key=""){
 rows.filter(x=>x.source_object_id===id&&x.trigger===trigger).forEach(x=>{
  const p=x.parameters||{};if(p.key&&p.key.toLowerCase()!==key.toLowerCase())return;
  if(x.action==="navigate"&&x.target_artboard_id){state.history.push(state.artboard_id);state.artboard_id=x.target_artboard_id}
  else if(x.action==="back"&&state.history.length)state.artboard_id=state.history.pop();
  else if(x.action==="open_overlay"&&x.target_artboard_id&&!state.overlay_artboard_ids.includes(x.target_artboard_id))state.overlay_artboard_ids.push(x.target_artboard_id);
  else if(x.action==="close_overlay")state.overlay_artboard_ids.pop();
  else if(x.action==="set_visibility"&&x.target_object_id)state.object_visibility[x.target_object_id]=p.visible!==false;
  else if(x.action==="set_opacity"&&x.target_object_id)state.object_opacity[x.target_object_id]=Number(p.opacity??1);
  else if(x.action==="play_sound"&&p.uri)new Audio(p.uri).play();
  else if(x.action==="play_animation"&&x.target_object_id){const el=document.getElementById(x.target_object_id);if(el)el.animate([{opacity:.4,transform:"scale(.98)"},{opacity:1,transform:"scale(1)"}],{duration:Number(p.duration_ms||250)})}
 });render();
}
document.querySelectorAll(".ui-object").forEach(el=>{
 el.onclick=()=>fire(el.id,"click");el.ondblclick=()=>fire(el.id,"double_click");
 el.onmouseenter=()=>fire(el.id,"hover");el.onpointerdown=()=>fire(el.id,"press");
 el.onfocus=()=>fire(el.id,"focus");el.onkeydown=e=>fire(el.id,"keyboard",e.key);
});render();
</script></body></html>""" % ("".join(artboards), data_json.replace("</", "<\\/"))
    index = root / "index.html"
    index.write_text(page, encoding="utf-8")
    document_path = root / "design_document.json"
    document_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema": PROTOTYPE_PACKAGE_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "entrypoint": "index.html",
        "inspection": inspection,
        "files": ["index.html", "design_document.json", "manifest.json"],
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": inspection["ok"],
        "root": str(root),
        "entrypoint": str(index),
        "manifest_path": str(manifest_path),
        "inspection": inspection,
    }


__all__ = [
    "PROTOTYPE_PACKAGE_SCHEMA",
    "PROTOTYPE_SCHEMA",
    "execute_ui_prototype_trigger",
    "export_ui_prototype",
    "inspect_ui_prototype",
    "prototype_initial_state",
]
