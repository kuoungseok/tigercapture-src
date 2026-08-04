"""FP3 lifecycle worker for the public Figma Plugin UI messaging contract."""
from __future__ import annotations

import copy
import json
import os
import queue
import re
import shutil
import subprocess
import threading
from typing import Any, Mapping

from app.painter_ui_figma_plugin_runtime import FORBIDDEN_SOURCE


UI_SESSION_SCHEMA = "tigercapture.painter.figma_plugin_ui_session.v1"
MAX_UI_HTML_BYTES = 1024 * 1024
FP3_ALLOWED_FIGMA_ROOTS = frozenset({
    "showUI", "ui", "on", "notify", "closePlugin", "editorType", "currentPage",
    "root", "viewport", "createRectangle", "createEllipse", "createFrame",
    "createText", "createVector", "createNodeFromSvg", "getNodeByIdAsync", "loadFontAsync",
})
SHOW_UI_SOURCE = re.compile(r"\bfigma\s*\.\s*showUI\s*\(")


_UI_NODE_WORKER = r"""
const vm=require('node:vm');
const readline=require('node:readline');
const {stripTypeScriptTypes}=require('node:module');
const rl=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
let context=null,sandbox=null,ui=null,closed=false,vmTimeout=750,outbound=[];
let timerSeq=1;const timerCallbacks=new Map(),hostTimers=new Map();
let all=[],page=null,selection=[],seq=1;
const eventListeners={drop:[]};
function clone(value){
  if(value===undefined)return null;
  return JSON.parse(JSON.stringify(value));
}
function emit(value){process.stdout.write(JSON.stringify(value)+'\n')}
function uiSnapshot(){return {
  visible:!!ui.visible,width:ui.width,height:ui.height,title:ui.title,
  themeColors:!!ui.themeColors,html:ui.html,closed:!!closed
}}
function drainMessages(){const value=outbound;outbound=[];return value}
function nodeSnapshot(){return all.map(n=>({id:n.id,originId:n._originId,type:n.type,name:n.name,x:n.x,y:n.y,
  width:n.width,height:n.height,rotation:n.rotation,visible:n.visible,opacity:n.opacity,
  fills:n.fills,strokes:n.strokes,strokeWeight:n.strokeWeight,strokeAlign:n.strokeAlign,
  vectorPaths:n.vectorPaths,characters:n.characters,fontName:n.fontName,fontSize:n.fontSize,
  fontWeight:n.fontWeight,textAlignHorizontal:n.textAlignHorizontal,lineHeight:n.lineHeight,
  parentId:n.parent&&n.parent!==page?n.parent.id:''}))}
function eventPayload(event){return {ok:true,event,ui:uiSnapshot(),messages:drainMessages(),nodes:nodeSnapshot(),selection:selection.map(n=>n.id)}}
function emitPush(){const messages=drainMessages();emit({...eventPayload('push'),messages})}
function clearTimers(){for(const handle of hostTimers.values())clearTimeout(handle);hostTimers.clear();timerCallbacks.clear()}
function clamp(value,min,max,fallback){const n=Number(value);return Number.isFinite(n)?Math.max(min,Math.min(max,n)):fallback}
function svgAttrs(text){const out={};String(text||'').replace(/([:\w-]+)\s*=\s*["']([^"']*)["']/g,(_,key,value)=>{out[key]=value;return ''});return out}
function svgNumber(value,fallback=0){const n=Number.parseFloat(String(value||''));return Number.isFinite(n)?n:fallback}
function svgPaint(value){
  const text=String(value||'').trim().toLowerCase();if(!text||text==='none')return [];
  let hex=text==='currentcolor'?'#000000':text;if(/^#[0-9a-f]{3}$/.test(hex))hex='#'+[...hex.slice(1)].map(c=>c+c).join('');
  if(!/^#[0-9a-f]{6}$/.test(hex))hex='#000000';
  return [{type:'SOLID',visible:true,opacity:1,color:{r:parseInt(hex.slice(1,3),16)/255,g:parseInt(hex.slice(3,5),16)/255,b:parseInt(hex.slice(5,7),16)/255}}];
}
function svgPathFor(tag,a){
  if(tag==='path')return String(a.d||'');
  if(tag==='polyline'||tag==='polygon'){
    const values=String(a.points||'').trim().split(/[\s,]+/).map(Number).filter(Number.isFinite);if(values.length<4)return '';
    let value=`M ${values[0]} ${values[1]}`;for(let i=2;i+1<values.length;i+=2)value+=` L ${values[i]} ${values[i+1]}`;return value+(tag==='polygon'?' Z':'');
  }
  if(tag==='line')return `M ${svgNumber(a.x1)} ${svgNumber(a.y1)} L ${svgNumber(a.x2)} ${svgNumber(a.y2)}`;
  if(tag==='circle'){
    const cx=svgNumber(a.cx),cy=svgNumber(a.cy),r=Math.max(0,svgNumber(a.r));return `M ${cx-r} ${cy} A ${r} ${r} 0 1 0 ${cx+r} ${cy} A ${r} ${r} 0 1 0 ${cx-r} ${cy} Z`;
  }
  if(tag==='ellipse'){
    const cx=svgNumber(a.cx),cy=svgNumber(a.cy),rx=Math.max(0,svgNumber(a.rx)),ry=Math.max(0,svgNumber(a.ry));return `M ${cx-rx} ${cy} A ${rx} ${ry} 0 1 0 ${cx+rx} ${cy} A ${rx} ${ry} 0 1 0 ${cx-rx} ${cy} Z`;
  }
  if(tag==='rect'){
    const x=svgNumber(a.x),y=svgNumber(a.y),w=Math.max(0,svgNumber(a.width)),h=Math.max(0,svgNumber(a.height));return `M ${x} ${y} H ${x+w} V ${y+h} H ${x} Z`;
  }
  return '';
}
async function start(input){
  vmTimeout=Math.max(50,Math.min(2000,Number(input.vmTimeout)||750));
  all=[];selection=[];seq=1;page={id:'page:current',type:'PAGE',name:'Page',children:[]};
  function title(type){return type[0]+type.slice(1).toLowerCase()}
  function make(type,source={}){
    const node={id:source.id||`plugin:${seq++}`,type,name:source.name||title(type),
      x:+source.x||0,y:+source.y||0,width:Math.max(0,+source.width||100),height:Math.max(0,+source.height||100),
      rotation:+source.rotation||0,visible:source.visible!==false,opacity:source.opacity===undefined?1:+source.opacity,
      fills:Array.isArray(source.fills)?source.fills:(type==='FRAME'?[{type:'SOLID',visible:true,opacity:1,color:{r:1,g:1,b:1}}]:[]),strokes:Array.isArray(source.strokes)?source.strokes:[],
      strokeWeight:Math.max(0,+source.strokeWeight||0),strokeAlign:String(source.strokeAlign||'CENTER'),
      vectorPaths:Array.isArray(source.vectorPaths)?source.vectorPaths:[],characters:String(source.characters||''),
      fontName:source.fontName&&typeof source.fontName==='object'?source.fontName:{family:'Inter',style:'Regular'},
      fontSize:Math.max(1,+source.fontSize||16),fontWeight:Math.max(1,+source.fontWeight||400),
      textAlignHorizontal:String(source.textAlignHorizontal||'LEFT'),
      lineHeight:source.lineHeight&&typeof source.lineHeight==='object'?source.lineHeight:{unit:'AUTO'},
      children:[],parent:null,_originId:source.originId||''};
    node.resize=(w,h)=>{node.width=Math.max(0,+w||0);node.height=Math.max(0,+h||0)};
    node.resizeWithoutConstraints=node.resize;
    if(type==='FRAME')node.appendChild=child=>{if(!child||!all.includes(child))throw Error('Invalid child');
      if(child.parent&&child.parent.children)child.parent.children=child.parent.children.filter(value=>value!==child);
      child.parent=node;node.children.push(child);return child};
    all.push(node);return node;
  }
  const byId={};
  for(const row of input.nodes||[]){const node=make(row.type,row);byId[node.id]=node}
  for(const row of input.nodes||[]){const node=byId[row.id],parent=byId[row.parentId];(parent||page).children.push(node);node.parent=parent||page}
  selection=(input.selection||[]).map(id=>byId[id]).filter(Boolean);
  Object.defineProperty(page,'selection',{get:()=>selection,set:value=>{if(!Array.isArray(value))throw Error('selection must be an array');selection=value}});
  page.appendChild=child=>{if(child.parent&&child.parent.children)child.parent.children=child.parent.children.filter(value=>value!==child);child.parent=page;page.children.push(child);return child};
  const create=type=>{const node=make(type);page.appendChild(node);return node};
  const createNodeFromSvg=value=>{
    const svg=String(value||'');if(!svg.trim()||svg.length>262144)throw Error('SVG source is empty or exceeds 256 KiB');
    const rootMatch=svg.match(/<svg\b([^>]*)>/i);if(!rootMatch)throw Error('Invalid SVG root');
    const root=svgAttrs(rootMatch[1]),viewBox=String(root.viewBox||'').trim().split(/[\s,]+/).map(Number);
    const width=Math.max(1,svgNumber(root.width,viewBox.length===4?viewBox[2]:100));
    const height=Math.max(1,svgNumber(root.height,viewBox.length===4?viewBox[3]:100));
    const frame=create('FRAME');frame.name='SVG';frame.resize(width,height);
    let count=0;const pattern=/<(path|polyline|polygon|line|circle|ellipse|rect)\b([^>]*)\/?\s*>/gi;let match;
    while((match=pattern.exec(svg))){
      if(++count>512)throw Error('SVG element limit exceeded');
      const tag=match[1].toLowerCase(),a=svgAttrs(match[2]),data=svgPathFor(tag,a);if(!data)continue;
      const vector=make('VECTOR');vector.name=`SVG ${tag}`;vector.resize(width,height);vector.vectorPaths=[{windingRule:'NONZERO',data}];
      vector.fills=svgPaint(a.fill===undefined?root.fill:a.fill);vector.strokes=svgPaint(a.stroke===undefined?root.stroke:a.stroke);
      vector.strokeWeight=Math.max(0,svgNumber(a['stroke-width'],svgNumber(root['stroke-width'],0)));frame.appendChild(vector);
    }
    if(!frame.children.length)throw Error('SVG contains no supported path geometry');return frame;
  };
  ui={visible:false,width:300,height:200,title:String(input.pluginName||'Plugin'),themeColors:false,html:'',onmessage:undefined};
  ui.show=()=>{if(!closed)ui.visible=true};
  ui.hide=()=>{if(!closed)ui.visible=false};
  ui.resize=(w,h)=>{ui.width=clamp(w,70,1200,300);ui.height=clamp(h,0,1000,200)};
  ui.close=()=>{closed=true;ui.visible=false;clearTimers()};
  ui.postMessage=value=>{outbound.push(clone(value))};
  const figma={editorType:'figma',ui,currentPage:page,root:{type:'DOCUMENT',children:[page]},
    viewport:{center:{x:+(input.viewport||{}).width/2||0,y:+(input.viewport||{}).height/2||0},scrollAndZoomIntoView(){}},
    createRectangle:()=>create('RECTANGLE'),createEllipse:()=>create('ELLIPSE'),
    createFrame:()=>create('FRAME'),createText:()=>create('TEXT'),createVector:()=>create('VECTOR'),
    createNodeFromSvg,
    on:(type,callback)=>{if(type!=='drop'||typeof callback!=='function')throw Error(`Unsupported FP3 event: ${String(type)}`);eventListeners.drop.push(callback)},
    getNodeByIdAsync:async id=>byId[id]||all.find(node=>node.id===id)||null,
    loadFontAsync:async()=>{},
    showUI:(html,options={})=>{
      ui.html=String(html||'');ui.visible=options.visible!==false;
      ui.width=clamp(options.width,70,1200,300);ui.height=clamp(options.height,0,1000,200);
      ui.title=String(options.title||input.pluginName||'Plugin').slice(0,120);
      ui.themeColors=options.themeColors===true;closed=false;
    },
    notify:value=>{outbound.push({type:'notification',message:String(value)});return {cancel(){}}},
    closePlugin:value=>{if(value)outbound.push({type:'notification',message:String(value)});ui.close()}
  };
  sandbox=Object.create(null);sandbox.figma=figma;
  sandbox.__html__=String(input.html||'');sandbox.__uiFiles__=clone(input.uiFiles||{});
  sandbox.console=Object.freeze({log(){},warn(){},error(){}});
  sandbox.__runTimer=(id)=>{const callback=timerCallbacks.get(id);if(!callback)return;timerCallbacks.delete(id);hostTimers.delete(id);callback()};
  sandbox.__dispatchDrop=async event=>{let handled=false;for(const callback of eventListeners.drop){if((await callback(event))===false)handled=true}await Promise.resolve();await Promise.resolve();return handled};
  sandbox.setTimeout=(callback,delay=0)=>{
    if(typeof callback!=='function')throw Error('setTimeout callback must be a function');
    if(timerCallbacks.size>=32)throw Error('FP3 timer limit exceeded');
    const id=timerSeq++;timerCallbacks.set(id,callback);
    const wait=clamp(delay,0,5000,0);
    hostTimers.set(id,setTimeout(()=>{
      try{vm.runInContext(`globalThis.__runTimer(${id})`,context,{timeout:vmTimeout});emitPush()}
      catch(error){emit({ok:false,event:'error',error:String(error&&error.message||error)});ui.close()}
    },wait));return id;
  };
  sandbox.clearTimeout=(id)=>{const handle=hostTimers.get(Number(id));if(handle)clearTimeout(handle);hostTimers.delete(Number(id));timerCallbacks.delete(Number(id))};
  context=vm.createContext(sandbox,{codeGeneration:{strings:false,wasm:false}});
  const code=stripTypeScriptTypes(String(input.code||''),{mode:'strip'});
  const promise=vm.runInContext(`(async()=>{${code}\n})()`,context,{timeout:vmTimeout});
  await promise;
  emit({...eventPayload('ready'),schema:input.schema});
}
async function command(input){
  if(input.type==='ui_message'){
    if(closed)throw Error('Plugin UI session is closed');
    sandbox.__incoming=clone(input.pluginMessage);
    if(typeof ui.onmessage==='function'){
      const result=vm.runInContext(
        `figma.ui.onmessage(globalThis.__incoming,{origin:'null'})`,context,{timeout:vmTimeout}
      );
      if(result&&typeof result.then==='function')await result;
    }
    emit(eventPayload('state'));
    return;
  }
  if(input.type==='plugin_drop'){
    if(closed)throw Error('Plugin UI session is closed');
    const value=input.pluginDrop||{},absoluteX=clamp(value.absoluteX,0,100000,clamp(value.clientX,0,100000,0)),absoluteY=clamp(value.absoluteY,0,100000,clamp(value.clientY,0,100000,0));
    const strategy=String((value.dropMetadata||{}).parentingStrategy||'page');
    const target=strategy==='immediate'&&selection.length&&selection[0].children?selection[0]:page;
    const files=(value.files||[]).map(file=>({name:String(file.name||''),type:String(file.type||''),getTextAsync:async()=>String(file.text||''),getBytesAsync:async()=>new Uint8Array([...String(file.text||'')].map(c=>c.charCodeAt(0)&255))}));
    const items=(value.items||[]).map(item=>({type:String(item.type||''),data:String(item.data||'')}));
    const event={node:target,x:absoluteX-(target===page?0:target.x),y:absoluteY-(target===page?0:target.y),absoluteX,absoluteY,items,files,dropMetadata:clone(value.dropMetadata||{})};
    sandbox.__incomingDrop=event;
    const result=vm.runInContext(`globalThis.__dispatchDrop(globalThis.__incomingDrop)`,context,{timeout:vmTimeout});if(result&&typeof result.then==='function')await result;
    emit(eventPayload('state'));return;
  }
  if(input.type==='close'){
    ui.close();emit(eventPayload('closed'));
    rl.close();return;
  }
  throw Error(`Unsupported FP3 worker command: ${String(input.type)}`);
}
let chain=Promise.resolve();let started=false;
rl.on('line',line=>{
  chain=chain.then(async()=>{
    const input=JSON.parse(line);
    if(!started){if(input.type!=='start')throw Error('FP3 worker requires start');started=true;await start(input)}
    else await command(input);
  }).catch(error=>emit({ok:false,event:'error',error:String(error&&error.message||error)}));
});
"""


def preflight_figma_plugin_ui_source(source: str, html: str) -> dict[str, Any]:
    code = str(source or "")
    markup = str(html or "")
    errors: list[str] = []
    match = FORBIDDEN_SOURCE.search(code)
    if match:
        errors.append(f"Blocked JavaScript capability: {match.group(0)}")
    if not SHOW_UI_SOURCE.search(code):
        errors.append("FP3 Plugin UI source must call figma.showUI")
    if len(markup.encode("utf-8")) > MAX_UI_HTML_BYTES:
        errors.append("Figma Plugin UI HTML exceeds the 1 MiB FP3 limit")
    referenced_roots = set(re.findall(r"\bfigma\s*\.\s*([A-Za-z_$][\w$]*)", code))
    unsupported = sorted(referenced_roots - FP3_ALLOWED_FIGMA_ROOTS)
    if unsupported:
        errors.append(f"Unsupported FP3 Figma API: figma.{unsupported[0]}")
    return {
        "ok": not errors,
        "schema": UI_SESSION_SCHEMA,
        "runtime_policy": "isolated_message_bridge_fp3",
        "html_bytes": len(markup.encode("utf-8")),
        "errors": errors,
    }


class PainterFigmaPluginUISession:
    """One plugin main/UI lifecycle in a restricted Node subprocess."""

    def __init__(
        self,
        source: str,
        html: str,
        *,
        plugin_name: str = "Plugin",
        ui_files: Mapping[str, str] | None = None,
        document: Mapping[str, Any] | None = None,
        timeout_ms: int = 750,
    ) -> None:
        preflight = preflight_figma_plugin_ui_source(source, html)
        if not preflight["ok"]:
            raise ValueError(preflight["errors"][0])
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node.js is required for the FP3 Plugin UI session")
        self._timeout = max(0.2, min(int(timeout_ms), 2_000) / 1000 + 0.5)
        from app.painter_ui_document import create_ui_document
        from app.painter_ui_figma_plugin_runtime import build_figma_plugin_document_payload

        self._source_document = copy.deepcopy(document or create_ui_document(390, 844))
        document_payload = build_figma_plugin_document_payload(self._source_document)
        self._plugin_id_map = {
            str(row["id"]): str(row.get("originId") or row["id"])
            for row in document_payload["nodes"]
        }
        self._events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._process = subprocess.Popen(
            [node, "--permission", "--disable-proto=throw", "-e", _UI_NODE_WORKER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env={
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
                "WINDIR": os.environ.get("WINDIR", "C:\\Windows"),
            },
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        self._send({
            "type": "start",
            "schema": UI_SESSION_SCHEMA,
            "code": str(source),
            "html": str(html),
            "uiFiles": dict(ui_files or {}),
            "pluginName": str(plugin_name),
            "vmTimeout": max(50, min(int(timeout_ms), 2_000)),
            **document_payload,
        })
        self.ready = self._receive("ready")

    def _read_stdout(self) -> None:
        assert self._process.stdout is not None
        for line in self._process.stdout:
            try:
                self._events.put(json.loads(line))
            except Exception:
                self._events.put({"ok": False, "event": "error", "error": "Invalid FP3 worker output"})

    def _send(self, value: Mapping[str, Any]) -> None:
        if self._process.poll() is not None or self._process.stdin is None:
            raise RuntimeError("Figma Plugin UI worker is not running")
        self._process.stdin.write(json.dumps(dict(value), ensure_ascii=False) + "\n")
        self._process.stdin.flush()

    def _receive(self, expected: str) -> dict[str, Any]:
        try:
            event = self._events.get(timeout=self._timeout)
        except queue.Empty as exc:
            self.terminate()
            raise TimeoutError("Figma Plugin UI worker timed out") from exc
        if not event.get("ok"):
            self.terminate()
            raise RuntimeError(str(event.get("error") or "Figma Plugin UI worker failed"))
        if event.get("event") != expected:
            self.terminate()
            raise RuntimeError(f"Unexpected Figma Plugin UI event: {event.get('event')}")
        return event

    def post_ui_message(self, plugin_message: Any) -> dict[str, Any]:
        self._send({"type": "ui_message", "pluginMessage": plugin_message})
        return self._receive("state")

    def post_plugin_drop(self, plugin_drop: Mapping[str, Any]) -> dict[str, Any]:
        payload = copy.deepcopy(dict(plugin_drop))
        files = payload.get("files") or []
        if not isinstance(files, list) or len(files) > 16:
            raise ValueError("Plugin drop files must be an array of at most 16 entries")
        total = 0
        for file in files:
            if not isinstance(file, Mapping):
                raise ValueError("Plugin drop file entry must be an object")
            total += len(str(file.get("text") or "").encode("utf-8"))
        if total > MAX_UI_HTML_BYTES:
            raise ValueError("Plugin drop files exceed the 1 MiB session limit")
        self._send({"type": "plugin_drop", "pluginDrop": payload})
        return self._receive("state")

    def poll_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            if not event.get("ok"):
                self.terminate()
                raise RuntimeError(str(event.get("error") or "Figma Plugin UI worker failed"))
            events.append(event)
        return events

    def apply_event(
        self,
        document: Mapping[str, Any],
        event: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Atomically apply one full FP3 node snapshot with stable created IDs."""
        from app.painter_ui_figma_plugin_runtime import apply_figma_plugin_result

        result = copy.deepcopy(dict(event))
        new_plugin_ids: list[str] = []
        for node in result.get("nodes", []):
            plugin_id = str(node.get("id") or "")
            mapped = self._plugin_id_map.get(plugin_id, "")
            if mapped:
                node["originId"] = mapped
            elif not node.get("originId"):
                new_plugin_ids.append(plugin_id)
        updated, report = apply_figma_plugin_result(document, result)
        for plugin_id, object_id in zip(new_plugin_ids, report["created_object_ids"]):
            self._plugin_id_map[plugin_id] = object_id
        return updated, report

    def close(self) -> dict[str, Any]:
        if self._process.poll() is not None:
            return {"ok": True, "event": "closed", "already_closed": True}
        self._send({"type": "close"})
        event = self._receive("closed")
        try:
            self._process.wait(timeout=self._timeout)
        except subprocess.TimeoutExpired:
            self.terminate()
        return event

    def terminate(self) -> None:
        if self._process.poll() is None:
            self._process.kill()
            try:
                self._process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass

    def __enter__(self) -> "PainterFigmaPluginUISession":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()


__all__ = [
    "MAX_UI_HTML_BYTES",
    "PainterFigmaPluginUISession",
    "UI_SESSION_SCHEMA",
    "preflight_figma_plugin_ui_source",
]
