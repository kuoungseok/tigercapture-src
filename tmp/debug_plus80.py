import json
from pathlib import Path

doc = json.loads(Path("debugCapture/umg_auto_layout_native_package/tiger_umg_document.json").read_text(encoding="utf-8"))

target_ids = {
    "figma-node-2411-13256": "text-eyebrow",
    "figma-node-2411-13257": "text-title",
    "figma-node-2411-13258": "description",
    "figma-node-2411-13259": "content-button",
}

for comp in doc.get("Components", []):
    if comp.get("Id") != "figma-component-2411-13255":
        continue
    layers = {l["Id"]: l for l in comp.get("Layers", [])}
    root = layers.get("figma-node-2411-13255") or comp.get("Layers", [None])[0]
    print("ROOT keys sample:", {k: root.get(k) for k in ("Id", "PanelKind", "Position", "Size", "SpacingStrategy")})
    for lid, name in target_ids.items():
        layer = layers.get(lid)
        if not layer:
            print(name, lid, "MISSING")
            continue
        payload = {}
        try:
            payload = json.loads(layer.get("PayloadJson") or "{}")
        except Exception:
            pass
        print("---", name, lid, "---")
        for key in ("Position", "Size", "CanvasSlot", "PanelKind", "FlowSlot", "MainAlignment"):
            print(" ", key, "=", layer.get(key))
        print("  pivot(from constraints in payload?) :", payload.get("constraints"))
