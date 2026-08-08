"""FP2 restricted, headless subset of the public Figma Plugin API."""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_document import (
    normalize_ui_document,
    update_ui_object,
    validate_ui_document,
)


RUNTIME_SCHEMA = "tigercapture.painter.figma_plugin_runtime.v1"
MAX_SOURCE_BYTES = 512 * 1024
FORBIDDEN_SOURCE = re.compile(
    r"\b(?:require|process|fetch|WebSocket|eval|Function|constructor)\b|\bimport\s*\(",
)
UI_BRIDGE_SOURCE = re.compile(
    r"\bfigma\s*\.\s*(?:showUI|ui)\b|\b__(?:html|uiFiles)__\b",
)


def preflight_figma_plugin_source(source: str) -> dict[str, Any]:
    code = str(source or "")
    errors: list[str] = []
    if len(code.encode("utf-8")) > MAX_SOURCE_BYTES:
        errors.append("Figma plugin source exceeds the 512 KiB FP2 limit")
    match = FORBIDDEN_SOURCE.search(code)
    if match:
        errors.append(f"Blocked JavaScript capability: {match.group(0)}")
    ui_match = UI_BRIDGE_SOURCE.search(code)
    if ui_match:
        errors.append("Figma Plugin UI requires the FP3 message bridge")
    return {
        "ok": not errors,
        "runtime_policy": "isolated_allowlist_fp2",
        "source_bytes": len(code.encode("utf-8")),
        "requires_plugin_ui": bool(ui_match),
        "errors": errors,
    }

_NODE_WORKER = r"""
const vm=require('node:vm');
const {stripTypeScriptTypes}=require('node:module');
let raw=''; process.stdin.setEncoding('utf8');
process.stdin.on('data',c=>raw+=c); process.stdin.on('end',async()=>{
  const input=JSON.parse(raw), all=[], notices=[]; let seq=1, closed=false;
  const page={id:'page:current',type:'PAGE',name:'Page',children:[]};
  function make(type, source={}) {
    const n={id:source.id||`plugin:${seq++}`,type,name:source.name||title(type),
      x:+source.x||0,y:+source.y||0,width:Math.max(0,+source.width||100),
      height:Math.max(0,+source.height||100),rotation:+source.rotation||0,
      visible:source.visible!==false,opacity:source.opacity===undefined?1:+source.opacity,
      fills:Array.isArray(source.fills)?source.fills:(type==='FRAME'?[{type:'SOLID',visible:true,opacity:1,color:{r:1,g:1,b:1}}]:[]),strokes:Array.isArray(source.strokes)?source.strokes:[],
      strokeWeight:Math.max(0,+source.strokeWeight||0),strokeAlign:String(source.strokeAlign||'CENTER'),
      vectorPaths:Array.isArray(source.vectorPaths)?source.vectorPaths:[],
      characters:String(source.characters||''),
      fontName:source.fontName&&typeof source.fontName==='object'?source.fontName:{family:'Inter',style:'Regular'},
      fontSize:Math.max(1,+source.fontSize||16),fontWeight:Math.max(1,+source.fontWeight||400),
      textAlignHorizontal:String(source.textAlignHorizontal||'LEFT'),
      lineHeight:source.lineHeight&&typeof source.lineHeight==='object'?source.lineHeight:{unit:'AUTO'},
      children:[],parent:null,_originId:source.originId||''};
    n.resize=(w,h)=>{n.width=Math.max(0,+w||0);n.height=Math.max(0,+h||0)};
    n.resizeWithoutConstraints=n.resize;
    n.appendChild=child=>{if(!child||!all.includes(child))throw Error('Invalid child');
      if(child.parent&&child.parent.children)child.parent.children=child.parent.children.filter(x=>x!==child);
      child.parent=n;n.children.push(child);return child};
    all.push(n); return n;
  }
  function title(t){return t[0]+t.slice(1).toLowerCase()}
  const byId={};
  for(const row of input.nodes){const n=make(row.type,row);byId[n.id]=n}
  for(const row of input.nodes){const n=byId[row.id],p=byId[row.parentId];(p||page).children.push(n);n.parent=p||page}
  let selection=input.selection.map(id=>byId[id]).filter(Boolean);
  Object.defineProperty(page,'selection',{get:()=>selection,set:v=>{if(!Array.isArray(v))throw Error('selection must be an array');selection=v}});
  page.appendChild=child=>{if(child.parent&&child.parent.children)child.parent.children=child.parent.children.filter(x=>x!==child);
    child.parent=page;page.children.push(child);return child};
  function create(type){const n=make(type);page.appendChild(n);return n}
  const api={currentPage:page,root:{type:'DOCUMENT',children:[page]},editorType:'figma',
    viewport:{center:{x:+input.viewport.width/2,y:+input.viewport.height/2},scrollAndZoomIntoView(){}},
    createRectangle:()=>create('RECTANGLE'),createEllipse:()=>create('ELLIPSE'),
    createFrame:()=>create('FRAME'),createText:()=>create('TEXT'),createVector:()=>create('VECTOR'),
    getNodeByIdAsync:async id=>byId[id]||all.find(n=>n.id===id)||null,
    loadFontAsync:async()=>{},notify:m=>{notices.push(String(m));return {cancel(){}}},
    closePlugin:m=>{closed=true;if(m)notices.push(String(m))}};
  const figma=new Proxy(api,{get:(o,k)=>{if(k in o)return o[k];throw Error(`Unsupported Figma API: ${String(k)}`)},
    set:()=>{throw Error('Figma root is read-only')}});
  const sandbox=Object.create(null);sandbox.figma=figma;
  sandbox.console=Object.freeze({log(){},warn(){},error(){}});
  const context=vm.createContext(sandbox,{codeGeneration:{strings:false,wasm:false}});
  try {
    const pluginCode=stripTypeScriptTypes(input.code,{mode:'strip'});
    const promise=vm.runInContext(`(async()=>{${pluginCode}\n})()`,context,{timeout:input.vmTimeout});
    await promise;
    const rows=all.map(n=>({id:n.id,originId:n._originId,type:n.type,name:n.name,x:n.x,y:n.y,
      width:n.width,height:n.height,rotation:n.rotation,visible:n.visible,opacity:n.opacity,
      fills:n.fills,strokes:n.strokes,strokeWeight:n.strokeWeight,strokeAlign:n.strokeAlign,
      vectorPaths:n.vectorPaths,characters:n.characters,fontName:n.fontName,fontSize:n.fontSize,
      fontWeight:n.fontWeight,textAlignHorizontal:n.textAlignHorizontal,lineHeight:n.lineHeight,
      parentId:n.parent&&n.parent!==page?n.parent.id:''}));
    process.stdout.write(JSON.stringify({ok:true,nodes:rows,selection:selection.map(n=>n.id),notices,closed}));
  } catch(error) {
    process.stdout.write(JSON.stringify({ok:false,error:String(error&&error.message||error),notices}));
  }
});
"""


def _plugin_api_color(value: object) -> dict[str, float]:
    text = str(value or "#000000FF").lstrip("#")
    if len(text) == 6:
        text += "FF"
    if len(text) != 8:
        text = "000000FF"
    try:
        channels = [int(text[index:index + 2], 16) / 255.0 for index in (0, 2, 4, 6)]
    except ValueError:
        channels = [0.0, 0.0, 0.0, 1.0]
    return {"r": channels[0], "g": channels[1], "b": channels[2], "a": channels[3]}


def _plugin_api_paints(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        paint_type = str(raw.get("type") or "").casefold()
        if paint_type != "solid":
            continue
        result.append({
            "type": "SOLID",
            "visible": bool(raw.get("visible", True)),
            "opacity": max(0.0, min(1.0, float(raw.get("opacity", 1) or 0))),
            "color": _plugin_api_color(raw.get("color")),
        })
    return result


def _node_payload(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    active = str(document.get("active_artboard_id") or "")
    rows = []
    for row in document.get("objects", []):
        if row.get("artboard_id") != active:
            continue
        kind = str(row.get("kind") or "rectangle")
        node_type = {"rectangle": "RECTANGLE", "ellipse": "ELLIPSE", "frame": "FRAME", "text": "TEXT", "path": "VECTOR"}.get(kind)
        if node_type is None:
            continue
        rows.append({
            "id": row["id"], "originId": row["id"], "type": node_type,
            "name": row.get("name", ""), "parentId": row.get("parent_id", ""),
            "x": row.get("x", 0), "y": row.get("y", 0),
            "width": row.get("width", 0), "height": row.get("height", 0),
            "rotation": row.get("rotation", 0), "visible": row.get("visible", True),
            "opacity": row.get("opacity", 1),
            "characters": (row.get("content") or {}).get("text", ""),
            "fills": _plugin_api_paints((row.get("style") or {}).get("fills", [])),
            "strokes": _plugin_api_paints((row.get("style") or {}).get("strokes", [])),
            "strokeWeight": (row.get("style") or {}).get("stroke_width", 0),
            "strokeAlign": str((row.get("style") or {}).get("stroke_align", "center")).upper(),
            "fontName": {
                "family": (row.get("style") or {}).get("font_family", "Inter"),
                "style": (row.get("style") or {}).get("font_style", "Regular"),
            },
            "fontSize": (row.get("style") or {}).get("font_size", 16),
            "fontWeight": (row.get("style") or {}).get("font_weight", 400),
            "textAlignHorizontal": str((row.get("style") or {}).get("text_align", "left")).upper(),
            "lineHeight": (
                {"unit": "PIXELS", "value": (row.get("style") or {}).get("line_height")}
                if float((row.get("style") or {}).get("line_height", 0) or 0) > 0
                else {"unit": "AUTO"}
            ),
            "vectorPaths": [
                {"windingRule": "NONZERO", "data": value}
                for value in (row.get("content") or {}).get("vector_paths", [])
            ],
        })
    return rows


def build_figma_plugin_document_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    """Build the shared FP2/FP3 node, selection, and viewport worker payload."""
    normalized = normalize_ui_document(document)
    active = normalized["active_artboard_id"]
    artboard = next(row for row in normalized["artboards"] if row["id"] == active)
    return {
        "nodes": _node_payload(normalized),
        "selection": list(normalized["selection"].get("object_ids") or []),
        "viewport": {"width": artboard["width"], "height": artboard["height"]},
    }


def run_figma_plugin_script(
    source: str,
    document: Mapping[str, Any],
    *,
    timeout_ms: int = 750,
) -> dict[str, Any]:
    code = str(source or "")
    preflight = preflight_figma_plugin_source(code)
    if not preflight["ok"]:
        raise ValueError(preflight["errors"][0])
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for the FP2 isolated runtime")
    normalized = normalize_ui_document(document)
    document_payload = build_figma_plugin_document_payload(normalized)
    payload = {
        "code": code,
        **document_payload,
        "vmTimeout": max(50, min(int(timeout_ms), 2_000)),
    }
    flags = [node, "--permission", "--disable-proto=throw", "-e", _NODE_WORKER]
    environment = {
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
        "WINDIR": os.environ.get("WINDIR", "C:\\Windows"),
    }
    try:
        completed = subprocess.run(
            flags,
            input=json.dumps(payload),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=max(0.2, min(int(timeout_ms), 2_000) / 1000 + 0.5),
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("Figma plugin exceeded the FP2 runtime limit") from exc
    try:
        result = json.loads(completed.stdout)
    except Exception as exc:
        raise RuntimeError(f"Figma plugin worker failed: {completed.stderr[:240]}") from exc
    if not result.get("ok"):
        raise RuntimeError(str(result.get("error") or "Figma plugin failed"))
    return {**result, "schema": RUNTIME_SCHEMA, "runtime_policy": "isolated_allowlist_fp2"}


def apply_figma_plugin_result(
    document: Mapping[str, Any], result: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Atomically map one successful worker result to a copied Painter document."""
    original = normalize_ui_document(document)
    updated = copy.deepcopy(original)
    known = {row["id"] for row in original["objects"]}
    id_map = {node["id"]: node.get("originId", "") for node in result.get("nodes", []) if node.get("originId")}
    created: list[str] = []
    used_ids = {str(row.get("id") or "") for row in updated["objects"]}
    next_object_number = 1

    def next_object_id() -> str:
        nonlocal next_object_number
        while f"ui-object-{next_object_number}" in used_ids:
            next_object_number += 1
        value = f"ui-object-{next_object_number}"
        used_ids.add(value)
        next_object_number += 1
        return value
    type_map = {"RECTANGLE": "rectangle", "ELLIPSE": "ellipse", "FRAME": "frame", "TEXT": "text", "VECTOR": "path"}
    for node in result.get("nodes", []):
        origin = str(node.get("originId") or "")
        changes = {
            "name": str(node.get("name") or ""), "x": float(node.get("x", 0)),
            "y": float(node.get("y", 0)), "width": float(node.get("width", 0)),
            "height": float(node.get("height", 0)), "rotation": float(node.get("rotation", 0)),
            "visible": bool(node.get("visible", True)), "opacity": float(node.get("opacity", 1)),
        }
        from app.painter_ui_figma import map_figma_plugin_paints

        stroke_width = max(0.0, float(node.get("strokeWeight", 0) or 0))
        stroke_align = str(node.get("strokeAlign") or "CENTER").casefold()
        fills = map_figma_plugin_paints(node.get("fills"))
        strokes = map_figma_plugin_paints(
            node.get("strokes"), stroke=True, width=stroke_width, align=stroke_align
        )
        style: dict[str, Any] = {
            "fills": fills,
            "strokes": strokes,
            "stroke_width": stroke_width,
            "stroke_align": stroke_align,
        }
        if fills and fills[0].get("type") == "solid":
            style["fill"] = fills[0]["color"]
        if strokes and strokes[0].get("type") == "solid":
            style["stroke"] = strokes[0]["color"]
        if str(node.get("type") or "") == "TEXT":
            font_name = node.get("fontName")
            font_name = font_name if isinstance(font_name, Mapping) else {}
            line_height = node.get("lineHeight")
            line_height = line_height if isinstance(line_height, Mapping) else {}
            style.update({
                "font_family": str(font_name.get("family") or "Inter"),
                "font_style": str(font_name.get("style") or "Regular"),
                "font_size": max(1.0, float(node.get("fontSize", 16) or 16)),
                "font_weight": max(1, int(float(node.get("fontWeight", 400) or 400))),
                "text_align": str(node.get("textAlignHorizontal") or "LEFT").casefold(),
                "line_height": (
                    max(0.0, float(line_height.get("value", 0) or 0))
                    if str(line_height.get("unit") or "").upper() == "PIXELS"
                    else 0.0
                ),
                "text_color": style.get("fill", "#000000FF"),
            })
        changes["style"] = style
        if origin in known:
            updated, _ = update_ui_object(updated, origin, changes)
            continue
        kind = type_map.get(str(node.get("type") or ""))
        if not kind:
            raise ValueError(f"Unsupported created Figma node type: {node.get('type')}")
        parent_token = str(node.get("parentId") or "")
        parent_id = str(id_map.get(parent_token) or "")
        content = (
            {"text": str(node.get("characters") or "")}
            if kind == "text"
            else {
                "vector_paths": [
                    str(item.get("data") or "")
                    for item in node.get("vectorPaths", [])
                    if isinstance(item, Mapping) and str(item.get("data") or "")
                ]
            }
            if kind == "path"
            else {}
        )
        object_id = next_object_id()
        updated["objects"].append({
            "id": object_id,
            "kind": kind,
            "name": changes["name"],
            "artboard_id": updated["active_artboard_id"],
            "parent_id": parent_id,
            "x": changes["x"], "y": changes["y"],
            "width": changes["width"], "height": changes["height"],
            "rotation": changes["rotation"], "visible": changes["visible"],
            "opacity": changes["opacity"], "z_index": len(updated["objects"]),
            "style": style, "content": content,
        })
        id_map[str(node["id"])] = object_id
        created.append(object_id)
    updated = normalize_ui_document(updated)
    selected = [id_map.get(str(item), str(item)) for item in result.get("selection", [])]
    selected = [item for item in selected if item in {row["id"] for row in updated["objects"]}]
    updated["selection"] = {"object_id": selected[-1] if selected else "", "object_ids": selected}
    validation = validate_ui_document(updated)
    if not validation["ok"]:
        raise ValueError(
            "Figma plugin result produced an invalid Painter document: "
            + "; ".join(validation["errors"][:5])
        )
    return updated, {"ok": True, "created_object_ids": created, "selection": selected, "notices": list(result.get("notices") or [])}


def run_installed_figma_plugin(
    registry,
    plugin_id: str,
    document: Mapping[str, Any],
    *,
    timeout_ms: int = 750,
) -> tuple[dict[str, Any], dict[str, Any]]:
    inspected = registry.inspect(plugin_id)
    validation = dict(inspected["validation"])
    if not validation["ok"]:
        raise ValueError("Invalid Figma plugin package")
    unsupported = list(validation.get("blockers", []))
    if unsupported:
        raise ValueError(
            "Figma plugin is outside the FP2 capability set: " + "; ".join(unsupported)
        )
    main_path = Path(validation["plugin_root"]) / validation["plugin"]["main"]
    runtime = run_figma_plugin_script(
        main_path.read_text(encoding="utf-8"), document, timeout_ms=timeout_ms
    )
    updated, report = apply_figma_plugin_result(document, runtime)
    return updated, {**report, "plugin_id": plugin_id}


__all__ = [
    "RUNTIME_SCHEMA", "apply_figma_plugin_result", "build_figma_plugin_document_payload", "run_figma_plugin_script",
    "run_installed_figma_plugin", "preflight_figma_plugin_source",
]
