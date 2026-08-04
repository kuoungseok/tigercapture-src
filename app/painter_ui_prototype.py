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
    from app.painter_ui_prototype_authoring import (
        normalize_ui_prototype_contract,
    )

    prototype = normalize_ui_prototype_contract(
        document["linked_targets"].get("prototype")
    )
    active_flow = next(
        (
            row
            for row in prototype["flows"]
            if row["id"] == prototype["active_flow_id"]
        ),
        None,
    )
    return {
        "schema": PROTOTYPE_SCHEMA,
        "document_id": document["document_id"],
        "artboard_id": (
            active_flow["artboard_id"]
            if active_flow is not None and active_flow["artboard_id"]
            else document["active_artboard_id"]
        ),
        "history": [],
        "overlay_artboard_ids": [],
        "object_states": {},
        "component_variants": {},
        "component_family_variants": {},
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
    interaction_id: str = "",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    runtime = dict(state or prototype_initial_state(document))
    runtime["history"] = list(runtime.get("history") or [])
    runtime["overlay_artboard_ids"] = list(
        runtime.get("overlay_artboard_ids") or []
    )
    runtime["object_states"] = dict(runtime.get("object_states") or {})
    runtime["component_variants"] = dict(
        runtime.get("component_variants") or {}
    )
    runtime["component_family_variants"] = dict(
        runtime.get("component_family_variants") or {}
    )
    runtime["object_visibility"] = dict(runtime.get("object_visibility") or {})
    runtime["object_opacity"] = dict(runtime.get("object_opacity") or {})
    runtime["material_scalars"] = dict(runtime.get("material_scalars") or {})
    runtime["variables"] = dict(runtime.get("variables") or {})
    runtime["variable_modes"] = dict(runtime.get("variable_modes") or {})
    runtime["events"] = list(runtime.get("events") or [])
    objects = {row["id"]: row for row in document["objects"]}
    source_object = objects.get(str(source_object_id))
    source_candidates = {str(source_object_id)}
    if source_object is not None:
        source_definition_id = str(
            source_object.get("component_source_object_id") or ""
        )
        if source_definition_id:
            source_candidates.add(source_definition_id)
        if str(source_object.get("component_role") or "") == "instance":
            components = {row["id"]: row for row in document["components"]}
            authored_component = components.get(
                str(source_object.get("component_id") or "")
            )
            family_id = str(
                (authored_component or {}).get("base_component_id")
                or (authored_component or {}).get("id")
                or ""
            )
            runtime_component_id = str(
                runtime["component_variants"].get(str(source_object_id))
                or runtime["component_family_variants"].get(family_id)
                or ""
            )
            runtime_component = components.get(runtime_component_id)
            if runtime_component is not None:
                source_candidates.add(str(runtime_component["root_object_id"]))
    requested_trigger = str(trigger).strip().casefold()
    direct_instance_override = bool(
        source_object is not None
        and source_object.get("component_role") == "instance"
        and any(
            interaction["enabled"]
            and interaction["source_object_id"] == str(source_object_id)
            and interaction["trigger"] == requested_trigger
            for interaction in document["interactions"]
        )
    )
    matched = []
    for interaction in document["interactions"]:
        if not interaction["enabled"]:
            continue
        if interaction_id and interaction["id"] != str(interaction_id):
            continue
        if interaction["source_object_id"] not in source_candidates:
            continue
        if interaction["trigger"] != str(trigger).strip().casefold():
            continue
        if (
            direct_instance_override
            and interaction["source_object_id"] != str(source_object_id)
            and interaction["action"] == "change_variant"
        ):
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
        elif action == "change_variant" and interaction.get("component_id"):
            target_component_id = str(interaction["component_id"])
            runtime["component_variants"][str(source_object_id)] = (
                target_component_id
            )
            components = {
                row["id"]: row for row in document["components"]
            }
            current_component = components.get(
                str((source_object or {}).get("component_id") or "")
            )
            family_id = str(
                (current_component or {}).get("base_component_id")
                or (current_component or {}).get("id")
                or ""
            )
            if family_id and not bool(
                parameters.get("reset_component_state", False)
            ):
                runtime["component_family_variants"][family_id] = (
                    target_component_id
                )
            runtime["object_states"][str(source_object_id)] = str(
                parameters.get("variant")
                or parameters.get("variant_key")
                or target_component_id
            )
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
        if bool(parameters.get("reset_component_state", False)):
            runtime["component_variants"] = {}
            runtime["component_family_variants"] = {}
            runtime["object_states"] = {}
        matched.append(interaction["id"])
    runtime["matched_interaction_ids"] = matched
    return runtime


def resolve_ui_component_prototype_document(
    value: Mapping[str, Any],
    state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Render runtime Change-to choices without mutating the authoring document."""

    from app.painter_ui_components import switch_ui_component_instance_variant

    document = normalize_ui_document(value)
    runtime = dict(state or {})
    components = {row["id"]: row for row in document["components"]}
    targets: dict[str, str] = {}
    for family_id, component_id in dict(
        runtime.get("component_family_variants") or {}
    ).items():
        for row in document["objects"]:
            if row.get("component_role") != "instance":
                continue
            component = components.get(str(row.get("component_id") or ""))
            if component is None:
                continue
            component_family_id = str(
                component.get("base_component_id") or component["id"]
            )
            if (
                component_family_id == str(family_id)
                and str(row.get("component_source_object_id") or "")
                == str(component.get("root_object_id") or "")
            ):
                targets[str(row["id"])] = str(component_id)
    targets.update(
        {
            str(instance_root_id): str(component_id)
            for instance_root_id, component_id in dict(
                runtime.get("component_variants") or {}
            ).items()
        }
    )
    for instance_root_id, component_id in targets.items():
        objects = {row["id"]: row for row in document["objects"]}
        root = objects.get(str(instance_root_id))
        if root is None or root.get("component_role") != "instance":
            continue
        if str(root.get("component_id") or "") == str(component_id):
            continue
        try:
            document, _result = switch_ui_component_instance_variant(
                document,
                instance_root_id=str(instance_root_id),
                target_component_id=str(component_id),
            )
        except ValueError:
            continue
    return document


def prototype_delay_schedule(
    value: Mapping[str, Any],
    state: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    document = normalize_ui_document(value)
    runtime = dict(state or prototype_initial_state(document))
    visible_artboards = {
        str(runtime.get("artboard_id") or ""),
        *(str(row) for row in runtime.get("overlay_artboard_ids") or []),
    }
    visible_artboards.discard("")
    object_artboards = {
        str(row["id"]): str(row["artboard_id"])
        for row in document["objects"]
    }
    visibility = dict(runtime.get("object_visibility") or {})
    rows = []
    for interaction in document["interactions"]:
        source_id = str(interaction["source_object_id"])
        if (
            not interaction["enabled"]
            or interaction["trigger"] != "delay"
            or object_artboards.get(source_id) not in visible_artboards
            or not bool(visibility.get(source_id, True))
        ):
            continue
        parameters = dict(interaction.get("parameters") or {})
        rows.append(
            {
                "interaction_id": str(interaction["id"]),
                "source_object_id": source_id,
                "delay_ms": max(
                    0,
                    min(600000, int(parameters.get("delay_ms") or 0)),
                ),
            }
        )
    return rows


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


def _object_html(
    row: Mapping[str, Any],
    *,
    children_html: str = "",
) -> str:
    from app.painter_ui_scroll import normalize_ui_scroll

    style = dict(row.get("style") or {})
    content = dict(row.get("content") or {})
    scroll = normalize_ui_scroll(row.get("scroll"))
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
    overflow = {
        "none": "hidden" if bool(row.get("clip_content", False)) else "visible",
        "horizontal": "auto hidden",
        "vertical": "hidden auto",
        "both": "auto",
    }[scroll["overflow"]]
    position = "sticky" if scroll["position"] == "sticky" else "absolute"
    classes = "ui-object kind-%s scroll-%s" % (
        html.escape(str(row["kind"])),
        html.escape(scroll["position"]),
    )
    own_text = text if row["kind"] in {"text", "button"} else ""
    return (
        '<div class="%s" id="%s" role="%s" aria-label="%s" '
        'data-scroll-position="%s" '
        'tabindex="0" style="left:%spx;top:%spx;width:%spx;height:%spx;'
        'opacity:%s;display:%s;background:%s;border:%spx solid %s;'
        'border-radius:%spx;position:%s;overflow:%s;'
        '--object-rotation:%sdeg;transform:translate(var(--scroll-x,0px),'
        'var(--scroll-y,0px)) rotate(var(--object-rotation))">%s%s</div>'
        % (
            classes,
            html.escape(str(row["id"])),
            role,
            label,
            html.escape(scroll["position"]),
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
            position,
            overflow,
            float(row["rotation"]),
            own_text,
            children_html,
        )
    )


def export_ui_prototype(
    value: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    inspection = inspect_ui_prototype(document)
    from app.painter_ui_prototype_authoring import inspect_ui_smart_animate

    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    data_json = json.dumps(
        {
            "document": document,
            "initial_state": prototype_initial_state(document),
            "smart_animate": {
                row["id"]: inspect_ui_smart_animate(document, row)
                for row in document["interactions"]
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_motion_bridge import resolved_ui_geometry

    geometry = resolve_ui_constraints(
        document,
        resolved_ui_geometry(
            document,
            normalize=False,
            resolve_responsive=False,
        ),
    )
    rows_by_id: dict[str, dict[str, Any]] = {}
    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    for source_row in document["objects"]:
        row = dict(source_row)
        row.update(geometry.get(str(row["id"]), {}))
        rows_by_id[str(row["id"])] = row
        children_by_parent.setdefault(str(row.get("parent_id") or ""), []).append(row)

    def render_object(row: Mapping[str, Any]) -> str:
        nested = sorted(
            children_by_parent.get(str(row["id"]), []),
            key=lambda item: (item["z_index"], item["id"]),
        )
        local_row = dict(row)
        parent_id = str(row.get("parent_id") or "")
        parent = rows_by_id.get(parent_id)
        if parent is not None:
            local_row["x"] = float(row["x"]) - float(parent["x"])
            local_row["y"] = float(row["y"]) - float(parent["y"])
        return _object_html(
            local_row,
            children_html="".join(render_object(child) for child in nested),
        )

    artboards = []
    for artboard in document["artboards"]:
        children = "".join(
            render_object(row)
            for row in sorted(
                (
                    row
                    for row in rows_by_id.values()
                    if row["artboard_id"] == artboard["id"]
                    and not str(row.get("parent_id") or "")
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
.ui-object{position:absolute;display:block}.ui-object.kind-text,.ui-object.kind-button{display:grid;place-items:center}
.ui-object:focus{outline:3px solid #4da3ff;outline-offset:2px}
</style></head><body><main id="stage">%s</main>
<script id="tiger-data" type="application/json">%s</script>
<script>
const data=JSON.parse(document.getElementById("tiger-data").textContent);
let state=data.initial_state;
const rows=data.document.interactions.filter(x=>x.enabled);
const byId=id=>document.getElementById(id);
const objectRows=Object.fromEntries(data.document.objects.map(x=>[x.id,x]));
const componentRows=Object.fromEntries(data.document.components.map(x=>[x.id,x]));
document.querySelectorAll('.ui-object').forEach(container=>{
 if(!['auto','scroll'].includes(getComputedStyle(container).overflowY)&&
    !['auto','scroll'].includes(getComputedStyle(container).overflowX))return;
 container.addEventListener('scroll',()=>{
  container.querySelectorAll(':scope > .scroll-fixed').forEach(el=>{
   el.style.setProperty('--scroll-x',`${container.scrollLeft}px`);
   el.style.setProperty('--scroll-y',`${container.scrollTop}px`);
  });
 });
});
function transitionFor(row){
 const t=(row.parameters||{}).transition||{};
 const easing={linear:"linear",ease_in:"ease-in",ease_out:"ease-out",
  ease_in_out:"ease-in-out",spring:"cubic-bezier(.2,.9,.25,1.15)"};
 return {kind:t.kind||"instant",duration:Number(t.duration_ms||0),
  easing:easing[t.easing]||"ease"};
}
function animateTarget(id,transition){
 const el=byId("artboard-"+id);if(!el||transition.kind==="instant"||transition.duration<=0)return;
 let start={opacity:0},end={opacity:1};
 if(["move_in","slide","smart_animate"].includes(transition.kind))start={opacity:.2,transform:"translateX(28px)"};
 else if(["move_out","push"].includes(transition.kind))start={opacity:.2,transform:"translateX(-28px)"};
 el.animate([start,end],{duration:transition.duration,easing:transition.easing,fill:"both"});
}
function captureSmart(row){
 const report=(data.smart_animate||{})[row.id]||{};
 return (report.matched_pairs||[]).map(pair=>{
  const source=byId(pair.source_object_id);if(!source)return null;
  const rect=source.getBoundingClientRect(),style=getComputedStyle(source);
  return {pair,rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},
   style:{opacity:style.opacity,backgroundColor:style.backgroundColor,
    borderColor:style.borderColor,borderWidth:style.borderWidth,
    borderRadius:style.borderRadius}};
 }).filter(Boolean);
}
function animateSmart(row,captured,transition){
 captured.forEach(item=>{
  const target=byId(item.pair.target_object_id);if(!target)return;
  const rect=target.getBoundingClientRect(),targetRow=objectRows[item.pair.target_object_id]||{};
  const sourceRow=objectRows[item.pair.source_object_id]||{};
  const sx=rect.width?item.rect.width/rect.width:1,sy=rect.height?item.rect.height/rect.height:1;
  const dx=item.rect.x-rect.x,dy=item.rect.y-rect.y;
  const rotation=Number(sourceRow.rotation||0)-Number(targetRow.rotation||0);
  const properties=item.pair.properties||[];
  const start={transformOrigin:"top left",
   transform:`translate(${dx}px,${dy}px) scale(${sx},${sy}) rotate(${rotation}deg)`};
  const end={transformOrigin:"top left",transform:"translate(0,0) scale(1,1) rotate(0deg)"};
  if(properties.includes("opacity")){start.opacity=item.style.opacity;end.opacity=getComputedStyle(target).opacity}
  if(properties.includes("fill")){start.backgroundColor=item.style.backgroundColor;end.backgroundColor=getComputedStyle(target).backgroundColor}
  if(properties.includes("stroke")){start.borderColor=item.style.borderColor;start.borderWidth=item.style.borderWidth;end.borderColor=getComputedStyle(target).borderColor;end.borderWidth=getComputedStyle(target).borderWidth}
  if(properties.includes("corner_radius")){start.borderRadius=item.style.borderRadius;end.borderRadius=getComputedStyle(target).borderRadius}
  target.animate([start,end],{duration:transition.duration,easing:transition.easing});
 });
}
function componentFamilyId(component){return component?(component.base_component_id||component.id):""}
function currentComponentId(instanceRow){
 const authored=componentRows[instanceRow.component_id];
 const family=componentFamilyId(authored);
 return state.component_variants[instanceRow.id]||state.component_family_variants[family]||instanceRow.component_id;
}
function instanceSubtree(rootId){
 return data.document.objects.filter(row=>{
  let cursor=row;while(cursor&&cursor.parent_id){if(cursor.parent_id===rootId)return true;cursor=objectRows[cursor.parent_id]}
  return row.id===rootId;
 });
}
function variantTargetRow(component,canonicalId){
 const map=((component||{}).metadata||{}).variant_source_map||{};
 return objectRows[map[canonicalId]||canonicalId]||null;
}
function applyInstanceVariant(instanceRow,componentId){
 const component=componentRows[componentId],targetRoot=component&&objectRows[component.root_object_id];
 if(!component||!targetRoot)return;
 instanceSubtree(instanceRow.id).forEach(row=>{
  const target=variantTargetRow(component,row.component_source_object_id||"");
  const el=byId(row.id);if(!target||!el)return;
  const style=target.style||{},overrides=row.instance_overrides||{};
  if(row.id!==instanceRow.id){el.style.left=`${Number(target.x)-Number(targetRoot.x)}px`;el.style.top=`${Number(target.y)-Number(targetRoot.y)}px`}
  el.style.width=`${Number(target.width)}px`;el.style.height=`${Number(target.height)}px`;
  if(overrides["style.fill"]===undefined)el.style.background=style.fill||"transparent";
  if(overrides["style.stroke"]===undefined)el.style.borderColor=style.stroke||"transparent";
  if(overrides["style.stroke_width"]===undefined)el.style.borderWidth=`${Number(style.stroke_width||0)}px`;
  if(overrides["style.radius"]===undefined)el.style.borderRadius=`${Number(style.radius||0)}px`;
  if(overrides.opacity===undefined)el.style.opacity=Number(target.opacity??1);
  if(["text","button"].includes(row.kind)&&overrides["content.text"]===undefined)el.textContent=String((target.content||{}).text||target.name||"");
  el.dataset.componentId=componentId;
 });
}
function render(){
 document.querySelectorAll(".artboard").forEach(el=>{
  const id=el.id.replace("artboard-","");
  el.classList.toggle("active",id===state.artboard_id);
  el.classList.toggle("overlay",state.overlay_artboard_ids.includes(id));
 });
 data.document.objects.filter(row=>row.component_role==="instance"&&
  (componentRows[row.component_id]||{}).root_object_id===row.component_source_object_id
 ).forEach(row=>applyInstanceVariant(row,currentComponentId(row)));
 Object.entries(state.object_visibility).forEach(([id,v])=>{
  const el=document.getElementById(id);if(el)el.style.display=v?"grid":"none";
 });
 Object.entries(state.object_opacity).forEach(([id,v])=>{
  const el=document.getElementById(id);if(el)el.style.opacity=v;
 });
 Object.entries(state.object_states).forEach(([id,v])=>{
  const el=byId(id);if(el)el.dataset.componentState=v;
 });
}
function interactionCandidates(id){
 const object=objectRows[id],result=new Set([id]);if(!object)return result;
 if(object.component_source_object_id)result.add(object.component_source_object_id);
 if(object.component_role==="instance"){
  const component=componentRows[currentComponentId(object)];if(component)result.add(component.root_object_id);
 }
 return result;
}
function fire(id,trigger,key=""){
 const candidates=interactionCandidates(id);
 const direct=rows.some(x=>x.source_object_id===id&&x.trigger===trigger);
 rows.filter(x=>candidates.has(x.source_object_id)&&x.trigger===trigger&&!(direct&&x.source_object_id!==id&&x.action==="change_variant")).forEach(x=>{
 const p=x.parameters||{};if(p.key&&p.key.toLowerCase()!==key.toLowerCase())return;
  const transition=transitionFor(x);
  const smart=transition.kind==="smart_animate"?captureSmart(x):[];
  if(x.action==="navigate"&&x.target_artboard_id){state.history.push(state.artboard_id);state.artboard_id=x.target_artboard_id}
  else if(x.action==="back"&&state.history.length)state.artboard_id=state.history.pop();
  else if(x.action==="open_overlay"&&x.target_artboard_id&&!state.overlay_artboard_ids.includes(x.target_artboard_id))state.overlay_artboard_ids.push(x.target_artboard_id);
  else if(x.action==="close_overlay")state.overlay_artboard_ids.pop();
  else if(x.action==="swap_overlay"&&x.target_artboard_id){if(state.overlay_artboard_ids.length)state.overlay_artboard_ids[state.overlay_artboard_ids.length-1]=x.target_artboard_id;else state.overlay_artboard_ids.push(x.target_artboard_id)}
  else if(x.action==="change_variant"&&x.component_id){
   state.component_variants[id]=String(x.component_id);
   const authored=componentRows[(objectRows[id]||{}).component_id],family=componentFamilyId(authored);
   if(family&&!p.reset_component_state)state.component_family_variants[family]=String(x.component_id);
   state.object_states[id]=String(p.variant||p.variant_key||x.component_id);
  }
  else if(["change_state","change_variant"].includes(x.action)&&x.target_object_id)state.object_states[x.target_object_id]=String(p.state||p.variant||x.name||"");
  else if(x.action==="set_visibility"&&x.target_object_id)state.object_visibility[x.target_object_id]=p.visible!==false;
  else if(x.action==="set_opacity"&&x.target_object_id)state.object_opacity[x.target_object_id]=Number(p.opacity??1);
  else if(x.action==="set_material_scalar"&&x.target_object_id){state.material_scalars[x.target_object_id]??={};state.material_scalars[x.target_object_id][p.name||"value"]=Number(p.value||0)}
  else if(x.action==="set_variable"&&p.variable_id)state.variables[p.variable_id]=p.value;
  else if(x.action==="set_variable_mode"&&p.collection_id)state.variable_modes[p.collection_id]=String(p.mode_id||"");
  else if(x.action==="scroll_to"&&x.target_object_id){const el=byId(x.target_object_id);if(el)el.scrollIntoView({behavior:"smooth",block:"center"})}
  else if(x.action==="play_sound"&&p.uri)new Audio(p.uri).play();
  else if(x.action==="play_animation"&&x.target_object_id){const el=document.getElementById(x.target_object_id);if(el)el.animate([{opacity:.4,transform:"scale(.98)"},{opacity:1,transform:"scale(1)"}],{duration:Number(p.duration_ms||250)})}
  if(p.reset_component_state){state.component_variants={};state.component_family_variants={};state.object_states={}}
  render();
  if(transition.kind==="smart_animate"&&smart.length)animateSmart(x,smart,transition);
  else if(x.target_artboard_id)animateTarget(x.target_artboard_id,transition);
 });
}
document.querySelectorAll(".ui-object").forEach(el=>{
 el.onclick=()=>fire(el.id,"click");el.ondblclick=()=>fire(el.id,"double_click");
 el.onmouseenter=()=>{fire(el.id,"hover");fire(el.id,"mouse_enter")};
 el.onmouseleave=()=>fire(el.id,"mouse_leave");
 el.onpointerdown=()=>fire(el.id,"press");
 el.ondragend=()=>fire(el.id,"drag");
 el.onfocus=()=>fire(el.id,"focus");el.onkeydown=e=>fire(el.id,"keyboard",e.key);
 rows.filter(x=>x.source_object_id===el.id&&x.trigger==="delay").forEach(x=>setTimeout(()=>fire(el.id,"delay"),Number((x.parameters||{}).delay_ms||0)));
});window.addEventListener("gamepadconnected",()=>rows.filter(x=>x.trigger==="gamepad").forEach(x=>fire(x.source_object_id,"gamepad")));render();
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
    "resolve_ui_component_prototype_document",
    "export_ui_prototype",
    "inspect_ui_prototype",
    "prototype_delay_schedule",
    "prototype_initial_state",
]
