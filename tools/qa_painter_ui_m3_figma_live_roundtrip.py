from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _live_snapshot_tail() -> str:
    return r"""
  function cleanPaint(p) {
    const row={type:p.type,visible:p.visible!==false,opacity:p.opacity??1};
    if(p.type==='SOLID') row.color=p.color;
    if(p.gradientStops) row.gradientStops=p.gradientStops;
    if(p.gradientTransform) row.gradientHandlePositions=[
      {x:p.gradientTransform[0][2],y:p.gradientTransform[1][2]},
      {x:p.gradientTransform[0][0]+p.gradientTransform[0][2],y:p.gradientTransform[1][0]+p.gradientTransform[1][2]},
      {x:p.gradientTransform[0][1]+p.gradientTransform[0][2],y:p.gradientTransform[1][1]+p.gradientTransform[1][2]}
    ];
    return row;
  }
  function snap(node) {
    const box=node.absoluteBoundingBox;
    const row={id:node.id,name:node.name,type:node.type,visible:node.visible!==false,
      opacity:node.opacity??1,rotation:node.rotation||0};
    if(box) row.absoluteBoundingBox={x:box.x,y:box.y,width:box.width,height:box.height};
    if('fills' in node && Array.isArray(node.fills)) row.fills=node.fills.map(cleanPaint);
    if('strokes' in node && Array.isArray(node.strokes)) row.strokes=node.strokes.map(cleanPaint);
    if('strokeWeight' in node) row.strokeWeight=node.strokeWeight;
    if('cornerRadius' in node && typeof node.cornerRadius==='number') row.cornerRadius=node.cornerRadius;
    if('characters' in node) row.characters=node.characters;
    if('layoutMode' in node) row.layoutMode=node.layoutMode;
    for(const key of ['itemSpacing','paddingLeft','paddingTop','paddingRight','paddingBottom'])
      if(key in node) row[key]=node[key];
    if('componentPropertyDefinitions' in node) row.componentPropertyDefinitions=node.componentPropertyDefinitions;
    if('componentProperties' in node) row.componentProperties=node.componentProperties;
    const shared={};
    for(const key of ['stable_id','component_id','component_source_object_id','component_family_id']) {
      const value=node.getSharedPluginData('tigerstudio',key);
      if(value) shared[key]=value;
    }
    if(Object.keys(shared).length) row.sharedPluginData={tigerstudio:shared};
    if(node.type==='INSTANCE' && node.mainComponent) row.componentId=node.mainComponent.id;
    if('reactions' in node) row.reactions=node.reactions;
    if('children' in node) row.children=node.children.map(snap);
    return row;
  }
  const payload=JSON.stringify({name:'Tiger Studio M3 live roundtrip',
    document:{id:'0:0',name:'Document',type:'DOCUMENT',children:[snap(figma.currentPage)]}});
  const html=`<textarea id="t"></textarea><script>
    onmessage=async(e)=>{const m=e.data.pluginMessage;if(!m||m.type!=='copy')return;
      const t=document.getElementById('t');t.value=m.payload;t.select();
      let ok=false;try{ok=document.execCommand('copy')}catch(_){}
      if(!ok)try{await navigator.clipboard.writeText(m.payload);ok=true}catch(_){}
      parent.postMessage({pluginMessage:{type:ok?'copied':'copy_failed'}},'*');};
  <\/script>`;
  figma.showUI(html,{visible:false,width:1,height:1});
  figma.ui.onmessage=msg=>figma.closePlugin(msg.type==='copied'
    ?'Tiger Studio live roundtrip JSON copied'
    :'Tiger Studio live roundtrip clipboard failed');
  figma.ui.postMessage({type:'copy',payload});
"""


def prepare(output: Path, *, plugin_id: str = "") -> dict:
    from app.painter_ui_components import insert_ui_object_into_component_slot
    from app.painter_ui_figma import export_figma_plugin_package
    from tools.qa_painter_ui_m3_slot_capture import _build_slot_document

    document, outsider, slot = _build_slot_document()
    document, _ = insert_ui_object_into_component_slot(
        document,
        instance_root_id=slot["instance_root_id"],
        property_name="Actions",
        object_id=outsider["id"],
    )
    package = export_figma_plugin_package(document, output)
    target = Path(package["output_dir"])
    code_path = target / "code.js"
    code = code_path.read_text(encoding="utf-8")
    marker = "  figma.closePlugin(`Imported ${doc.artboards.length} artboards and ${doc.objects.length} objects from Tiger Studio`);"
    if marker not in code:
        raise RuntimeError("Figma live-roundtrip injection marker is missing")
    code_path.write_text(code.replace(marker, _live_snapshot_tail()), encoding="utf-8")
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["name"] = "Tiger Studio M3 Live Roundtrip"
    assigned_plugin_id = str(plugin_id or "").strip()
    manifest["id"] = assigned_plugin_id or "tigerstudio-painter-ui-m3-live-roundtrip"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    report = {"schema":"tigerstudio.painter.ui.m3_figma_live_roundtrip.v1",
              "phase":"prepared","manifest_path":str(manifest_path),
              "exchange_path":package["exchange_path"],
              "source_document_id":document["document_id"],
              "source_object_count":len(document["objects"]),
              "slot_object_id":slot["slot_object_id"],
              "plugin_id":manifest["id"],
              "figma_assigned_plugin_id":bool(assigned_plugin_id),
              "live_execution_ready":bool(assigned_plugin_id)}
    (output / "prepare_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


def consume(output: Path, snapshot: Path) -> dict:
    from app.painter_ui_figma import import_figma_json
    imported, import_report = import_figma_json(snapshot)
    slot_rows=[row for row in imported["objects"] if row.get("component_slot_property")]
    prepared_path = output / "prepare_report.json"
    prepared = (
        json.loads(prepared_path.read_text(encoding="utf-8"))
        if prepared_path.exists()
        else {}
    )
    source_ids = {
        str(row.get("id") or "")
        for row in json.loads(
            Path(prepared.get("exchange_path", "")).read_text(encoding="utf-8")
        ).get("document", {}).get("objects", [])
    } if prepared.get("exchange_path") and Path(prepared["exchange_path"]).exists() else set()
    imported_ids = {str(row.get("id") or "") for row in imported["objects"]}
    stable_ids_preserved = sorted(source_ids & imported_ids)
    report={"schema":"tigerstudio.painter.ui.m3_figma_live_roundtrip.v1",
            "phase":"consumed","snapshot_path":str(snapshot.resolve()),
            "imported_object_count":len(imported["objects"]),
            "imported_component_count":len(imported["components"]),
            "slot_count":len(slot_rows),"import_ok":bool(import_report.get("ok",True)),
            "source_stable_id_count":len(source_ids),
            "preserved_stable_id_count":len(stable_ids_preserved),
            "stable_ids_preserved":stable_ids_preserved,
            "import_report":import_report}
    report["passed"]=bool(
        report["imported_object_count"]
        and report["imported_component_count"]
        and report["slot_count"]
        and (not source_ids or source_ids == imported_ids)
    )
    (output / "roundtrip_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (output / "roundtrip_document.json").write_text(json.dumps(imported,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--snapshot",default="")
    parser.add_argument("--stdin",action="store_true")
    parser.add_argument(
        "--plugin-id",
        default="",
        help="Figma-assigned development plugin id used for a real live run",
    )
    args=parser.parse_args(); output=Path(args.output).resolve(); output.mkdir(parents=True,exist_ok=True)
    if args.stdin:
        snapshot=output / "figma_live_snapshot.json"
        payload=sys.stdin.read()
        json.loads(payload)
        snapshot.write_text(payload,encoding="utf-8")
        report=consume(output,snapshot)
    else:
        report=(
            consume(output,Path(args.snapshot))
            if args.snapshot
            else prepare(output, plugin_id=args.plugin_id)
        )
    print(json.dumps(report,ensure_ascii=False)); return 0 if report.get("passed",True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
