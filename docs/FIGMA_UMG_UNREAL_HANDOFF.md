# Handoff — Figma → UMG, getting the Start button into Unreal

Branch `codex/worktree-cleanup-20260708`, all work pushed to `source`.
HEAD == remote at `e7797fea`.

## The one thing left

Generation into UE 5.8 fails on a single layer:

```
figma-node-363-1582: baked_static_vector_source_hash_mismatch
```

Measured cause:

```
layer Size            16.0 x 12.0
bake plan logical     12.0 x  8.0
```

Exactly +4 on each axis = `STATIC_VECTOR_BAKE_PADDING` (2) doubled.
`expand_umg_layer_for_static_bake(layer, plan)` grows the layer by the bake
padding, and the plugin then recomputes the source hash from the grown layer and
compares it with the plan's `source_hash`, which was captured before the growth.

This is latent fallout from `ae95e767` ("Materialize static bakes that live
inside components"). Before that commit, component-owned bakes were never
materialized at all, so this path had never run. Screen-layer bakes agree; the
component path is where it shows.

Start here:
- `app/painter_ui_umg_adapter.py` `_materialize_static_bakes` — the loop now
  walks `document["Components"][*]["Layers"]` as well; `expand_umg_layer_for_static_bake`
  is called per baked layer.
- `app/unreal_umg_static_vector_bake.py` — `expand_umg_layer_for_static_bake`,
  `STATIC_VECTOR_BAKE_PADDING`.
- Plugin side: search `baked_static_vector_source_hash_mismatch` in
  `resources/unreal_plugins/UMG/TigerStudioUMG/Source/TigerStudioUMGEditor/Private/TigerStudioUMGImportSubsystem.cpp`
  to see exactly what it hashes.

Once this passes, the button should render: the document already reaches
`packaged ok=True`, `Blocked 0`, with `Start` among the surviving labels.

## Reproduce in one command

```
.venv/Scripts/python.exe tmp/generate_auto_layout_unreal.py
```

Imports `~/Downloads/Figma auto layout playground (Community).fig`, drops the
still-blocked vector art, packages, and generates into
`debugCapture/component_schema18_buildcheck/HostProject`.
Delete `debugCapture/umg_auto_layout_native_package` first if bake hashes look stale.

## Build the plugin (do NOT use tools/build_unreal_umg_plugin.py)

```
.venv/Scripts/python.exe tmp/build_plugin_editor_only.py     # ~25 s, deterministic
```

`tools/build_unreal_umg_plugin.py` runs RunUAT BuildPlugin, which builds the
editor target and then a game target in the same run. The editor target always
succeeds; the second invocation intermittently dies with
`Result: Failed (ConflictingInstance)` because UBT's own mutex is still held by
the invocation that just finished. It also needs
`%LOCALAPPDATA%\UnrealBuildTool\Trace.uba` to exist or UBT crashes in
`Log.BackupLogFile`. The editor DLLs are the only ones generation loads.

Close every `UnrealEditor.exe` / `UnrealEditor-Cmd.exe` before building —
a running editor holds the plugin DLLs and `install_project_plugin` fails with
`PermissionError`.

## Verifying what Unreal actually rendered

`WidgetTree` is not reachable from the UE Python API on the blueprint, its
generated class, or the CDO. Render instead and count pixels:

```
.venv/Scripts/python.exe tmp/render_umg_widget.py    # writes debugCapture/umg_auto_layout_render.png
```

Editor logs go to `HostProject/Saved/Logs/HostProject.log`, not stdout.

To open the editor on an asset, use `tmp/open_unreal_editor.py` with
`MSYS_NO_PATHCONV=1`. Notes that cost time:
- `Asset.Open` is not a real console command.
- Git Bash rewrites `/Game/...` into `C:/Program Files/Git/Game/...`.
- `-ExecutePythonScript` runs the script and then calls `CloseEditor()`, so the
  window flashes and quits. Use `-ExecCmds=py <file>` instead.

## What landed (newest first)

| commit | what |
| --- | --- |
| `e7797fea` | painted rounded container → synthetic leaf background + content panel; plugin schema ceiling 20 |
| `9d780a87` | main-axis alignment carried as schema-20 `MainAlignment`, realized with Fill spacers |
| `f90ed34f` | bind the authored font on screen layers too (there are two text construction paths) |
| `e8879bc2` | ship the font face as a resource, wrap `UFontFace` in a runtime `UFont` |
| `ae95e767` | materialize static bakes that live inside components |
| `6919ac8e` | hidden layers export `HitTestInvisible` so they stop swallowing clicks |
| `8b320207` | derive instance overrides so UMG shows `Start`, not the component default |
| `4904d69c` | draw blocked layers as a marked, locked reference in the UMG view |

## Measurements worth keeping

- Description paragraph in Unreal: 2 lines → **3 lines** after the font fix
  (dark-ink row bands `y 334-356, 364-386, 394-416`).
- Button label: `Get started` → **`Start`**.
- UMG view missing content: 53.95% → 7.87% with the reference layer on.
- Frame gates: `Blocked 229 → 222`, `content-button` 2 reasons → 0.

## Still open, not started

- Vector shape gate — the five-reason cluster that still blocks ~200 objects on
  this frame. Needs stroke and open-subpath support in
  `app/unreal_umg_static_vector_bake.py`, which bumps `RENDERER`
  (`qt_svg_fill_geometry_v3`) and invalidates every existing bake hash.
  Lifting any single gate of that cluster frees nothing; they must go together.
- `Collapsed` visibility (schema + C++) if a document ever hides a child inside
  an auto-layout frame. In the measured file: 92 hidden objects, 0 inside an
  auto-layout parent, so `HitTestInvisible` was enough.
