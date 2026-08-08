import { build } from "esbuild";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const args = Object.fromEntries(process.argv.slice(2).map((value, index, all) => {
  if (!value.startsWith("--")) return ["", ""];
  return [value.slice(2), all[index + 1] || ""];
}).filter(([key]) => key));

const source = path.resolve(args.source || "");
const output = path.resolve(args.output || "");
const width = Math.max(1, Number(args.width || 1920));
const height = Math.max(1, Number(args.height || 1080));
const fps = Math.max(1, Number(args.fps || 30));
const durationFrames = Math.max(1, Number(args.frames || 150));
const runtimeDir = path.dirname(fileURLToPath(import.meta.url));
if (!fs.existsSync(source)) throw new Error(`TSX source not found: ${source}`);
fs.mkdirSync(output, { recursive: true });

const entry = path.join(output, "entry.tsx");
const imported = JSON.stringify(source.replaceAll("\\", "/"));
fs.writeFileSync(entry, `
import React from "react";
import { createRoot } from "react-dom/client";
import ImportedComponent from ${imported};
globalThis.__TIGER_WIDTH__ = ${width};
globalThis.__TIGER_HEIGHT__ = ${height};
globalThis.__TIGER_FPS__ = ${fps};
globalThis.__TIGER_DURATION_FRAMES__ = ${durationFrames};
globalThis.__TIGER_FRAME__ = 0;
const target = document.getElementById("root");
const root = createRoot(target);
const renderFrame = (frame) => {
  globalThis.__TIGER_FRAME__ = Number(frame || 0);
  root.render(React.createElement(ImportedComponent, { key: String(frame) }));
};
globalThis.__tigerSetFrame = (frame) => new Promise((resolve) => {
  renderFrame(frame);
  requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
});
renderFrame(0);
globalThis.__tigerReady = true;
`);

await build({
  entryPoints: [entry],
  outfile: path.join(output, "bundle.js"),
  bundle: true,
  format: "iife",
  platform: "browser",
  jsx: "automatic",
  alias: {
    remotion: path.join(runtimeDir, "shim-remotion.tsx"),
    "next/image": path.join(runtimeDir, "shim-next-image.tsx"),
  },
  nodePaths: [path.join(runtimeDir, "node_modules")],
  logLevel: "warning",
});

fs.writeFileSync(path.join(output, "index.html"), `<!doctype html>
<html><head><meta charset="utf-8"><style>
html,body,#root{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}
*{box-sizing:border-box} body{font-family:Inter,"Segoe UI",Arial,sans-serif}
</style></head><body><div id="root"></div><script src="bundle.js"></script></body></html>`);
console.log(JSON.stringify({ ok: true, source, output, width, height, fps, durationFrames }));
