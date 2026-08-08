"""Executable responsive Web package delivery for Painter UI documents."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_advanced_delivery import inspect_advanced_ui_delivery
from app.painter_ui_document import normalize_ui_document
from app.painter_ui_prototype import (
    export_ui_prototype,
    inspect_ui_prototype,
)
from app.painter_ui_themes import resolve_ui_theme_document


WEB_PREFLIGHT_SCHEMA = "tigerstudio.painter.ui.web_preflight.v1"
WEB_PACKAGE_SCHEMA = "tigerstudio.painter.ui.web_package.v1"
_RENDERER = {
    "Native": "dom_css",
    "Vector": "svg",
    "Platform Effect": "css_effect",
    "Material": "css_effect",
    "Baked": "raster_asset",
    "Actor Only": "canvas_actor",
    "Blocked": "blocked",
}

_WEB_CSS = """/* Tiger Studio Painter responsive Web adapter */
:root{color-scheme:dark}
html,body{width:100%;min-height:100%;overflow:auto}
#stage{width:100%;min-height:100vh;padding:16px;align-content:start}
.artboard.active,.artboard.overlay{
  scale:var(--tiger-web-scale,1);
  transform-origin:top center;
}
@media (max-width:600px){
  #stage{padding:8px}
  .artboard{box-shadow:0 8px 30px #0009}
}
"""

_WEB_RUNTIME = """(() => {
  const stage = document.getElementById("stage");
  let responsiveAuto = true;
  function chooseResponsiveArtboard() {
    if (!responsiveAuto || typeof data === "undefined" || typeof state === "undefined") return;
    const rows = data.document.artboards || [];
    if (rows.length < 2 || (state.history || []).length) return;
    const wanted = window.innerWidth <= 600 ? "mobile"
      : window.innerWidth <= 1024 ? "tablet" : "desktop";
    const exact = rows.find((row) => String(row.breakpoint || "").toLowerCase() === wanted);
    const fallback = [...rows].sort((a,b) =>
      Math.abs(Number(a.width || 1) - window.innerWidth)
      - Math.abs(Number(b.width || 1) - window.innerWidth))[0];
    const selected = exact || fallback;
    if (selected && state.artboard_id !== selected.id) {
      state.artboard_id = selected.id;
      render();
    }
  }
  function fitActiveArtboard() {
    chooseResponsiveArtboard();
    const rows = [...document.querySelectorAll(".artboard.active,.artboard.overlay")];
    let requiredHeight = 0;
    rows.forEach((row) => {
      const width = Number.parseFloat(row.style.width) || row.offsetWidth || 1;
      const height = Number.parseFloat(row.style.height) || row.offsetHeight || 1;
      const availableWidth = Math.max(1, window.innerWidth - (window.innerWidth <= 600 ? 16 : 32));
      const availableHeight = Math.max(1, window.innerHeight - 32);
      const scale = Math.min(1, availableWidth / width, availableHeight / height);
      row.style.setProperty("--tiger-web-scale", String(scale));
      requiredHeight = Math.max(requiredHeight, height * scale);
    });
    if (stage) stage.style.minHeight = `${Math.max(window.innerHeight, requiredHeight + 32)}px`;
  }
  const observer = new MutationObserver(fitActiveArtboard);
  observer.observe(document.body, {attributes:true,subtree:true,attributeFilter:["class"]});
  document.addEventListener("click", () => { responsiveAuto = false; }, {once:true});
  window.addEventListener("resize", fitActiveArtboard, {passive:true});
  window.addEventListener("load", fitActiveArtboard, {once:true});
  requestAnimationFrame(fitActiveArtboard);
})();
"""


def _css_string(value: Any) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def _resolved_web_css(document: Mapping[str, Any]) -> str:
    rows = [_WEB_CSS]
    for artboard in document["artboards"]:
        rows.append(
            '[id="artboard-%s"]{background:%s}'
            % (
                _css_string(artboard["id"]),
                str(artboard.get("background") or "#FFFFFF"),
            )
        )
    for item in document["objects"]:
        style = dict(item.get("style") or {})
        declarations = [
            f"color:{style.get('text_color') or '#111111'}",
            f"font-size:{float(style.get('font_size') or 14.0):g}px",
        ]
        font_weight = style.get("font_weight")
        if font_weight:
            declarations.append(f"font-weight:{font_weight}")
        text_align = str(style.get("text_align") or "").strip()
        if text_align:
            declarations.append(f"text-align:{text_align}")
        line_height = style.get("line_height")
        if line_height:
            declarations.append(f"line-height:{float(line_height):g}px")
        rows.append(
            '[id="%s"]{%s}'
            % (_css_string(item["id"]), ";".join(declarations))
        )
    return "\n".join(rows) + "\n"


def preflight_ui_web(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    delivery = inspect_advanced_ui_delivery(document)
    prototype = inspect_ui_prototype(document)
    web = dict(delivery["targets"]["web"])
    features = []
    renderer_counts: dict[str, int] = {}
    for row in web["features"]:
        renderer = _RENDERER[str(row["resolved"])]
        renderer_counts[renderer] = renderer_counts.get(renderer, 0) + 1
        features.append({**row, "renderer": renderer})
    blockers = list(web["blockers"])
    blockers.extend(prototype["validation_errors"])
    blockers.extend(
        f"unsupported_interaction:{row}"
        for row in prototype["unsupported_interaction_ids"]
    )
    return {
        "schema": WEB_PREFLIGHT_SCHEMA,
        "ok": not blockers,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "counts": web["counts"],
        "renderer_counts": renderer_counts,
        "features": features,
        "prototype": prototype,
        "blockers": sorted(set(blockers)),
        "warnings": list(delivery["warnings"]),
        "responsive_policy": {
            "viewport_meta": True,
            "fit_active_artboard": True,
            "max_upscale": 1.0,
            "mobile_breakpoint_px": 600,
        },
        "claim_scope": "executable_local_web_package",
    }


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _artifact(path: Path, root: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def package_ui_web(
    value: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    preflight = preflight_ui_web(document)
    if not preflight["ok"]:
        return {
            "schema": WEB_PACKAGE_SCHEMA,
            "ok": False,
            "preflight": preflight,
            "artifacts": [],
        }
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    resolved_document = resolve_ui_theme_document(document)
    prototype_report = export_ui_prototype(resolved_document, root)
    index = Path(prototype_report["entrypoint"])
    html_text = index.read_text(encoding="utf-8")
    html_text = html_text.replace(
        "</head>",
        '<link rel="stylesheet" href="web.css"></head>',
        1,
    )
    html_text = html_text.replace(
        "</body>",
        '<script src="web-runtime.js"></script></body>',
        1,
    )
    _write_text(index, html_text)
    css_path = root / "web.css"
    runtime_path = root / "web-runtime.js"
    preflight_path = root / "web_preflight.json"
    _write_text(css_path, _resolved_web_css(resolved_document))
    _write_text(runtime_path, _WEB_RUNTIME)
    _write_text(
        preflight_path,
        json.dumps(preflight, ensure_ascii=False, indent=2) + "\n",
    )
    artifact_paths = (
        index,
        root / "design_document.json",
        css_path,
        runtime_path,
        preflight_path,
    )
    artifacts = [_artifact(path, root) for path in artifact_paths]
    manifest = {
        "schema": WEB_PACKAGE_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "entrypoint": "index.html",
        "artifacts": artifacts,
        "preflight": preflight,
        "prototype_inspection": prototype_report["inspection"],
        "hosting": "not_included",
    }
    manifest_path = root / "manifest.json"
    _write_text(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    return {
        "schema": WEB_PACKAGE_SCHEMA,
        "ok": True,
        "output_dir": str(root),
        "entrypoint": str(index),
        "manifest_path": str(manifest_path),
        "artifacts": artifacts,
        "preflight": preflight,
    }


__all__ = [
    "WEB_PACKAGE_SCHEMA",
    "WEB_PREFLIGHT_SCHEMA",
    "package_ui_web",
    "preflight_ui_web",
]
