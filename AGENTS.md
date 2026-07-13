# TigerCapture Agent Rules

These rules are for AI coding agents working in this repository.

## Agent Handoff Entry Point

When a user mentions a previous session, handoff, review automation, UI renewal,
VTuber Studio, VSeeFace, Program Output, or missing context, read
`docs/AGENT_START_HERE.md` before searching randomly through the repository.
That file is the durable index for active handoff docs, current assumptions, and
known traps from recent sessions.

## Git Remote Boundary

This repository uses separate remotes for private source and public
distribution.

- `source` / `kuoungseok/tigercapture-src` is the private source repository.
  Push source branches, feature branches, WIP checkpoints, source tags, and
  source PR work only to `source` unless the user explicitly says otherwise.
- `origin` / `kuoungseok/tigercapture` is the public distribution repository.
  Do not push full source, source checkpoints, feature branches, or source PRs
  to `origin`.
- `origin` should contain only distribution-safe branches, tags, docs, release
  metadata, installers, or packaged artifacts. Use the dedicated `release`
  branch or a sanitized release/export workflow for distribution updates.
- Never make `origin` public, create public release tags, or publish release
  artifacts until verifying that no source commits, source branches, source
  tags, or accidental PR refs would be exposed.
- If source content is accidentally pushed to `origin`, stop and report it
  immediately. Do not continue by changing repository visibility or creating
  more public-facing refs.
- Local Git must use the repository hook path `.githooks` and default pushes
  should go to `source`:

  ```powershell
  git config core.hooksPath .githooks
  git config remote.pushDefault source
  ```

  The tracked `.githooks/pre-push` guard blocks source branches, WIP branches,
  source tags, and source-tree refs from being pushed to `origin`. Do not bypass
  this guard except for an explicitly requested emergency cleanup.

## Debug Capture Boundary

`debugCapture` is disposable scratch space. The user may delete it at any time
when it grows large, so never put important or non-regenerable files there.

Allowed in `debugCapture`:

- temporary logs, probe reports, screenshots, thumbnails, and QA captures
- generated diagnostics that can be recreated from source assets and code
- short-lived intermediate files used by local tests or manual verification

Not allowed in `debugCapture`:

- external tools, SDKs, or installed applications
- source media, purchased/downloaded asset originals, models, avatars, or
  reference assets that are needed later
- project state, manifests, caches, or configuration files that the app must
  rely on after cleanup

Use `external/tools` for external applications and SDKs, `external/assets` for
local third-party assets, and tracked docs/resources for durable project data.
AR/PBR QA and preview tool defaults must use durable samples under
`sample_assets` or `external/assets`, not `debugCapture`.
Default source media, motion CSVs, descriptors, models, avatars, and imported
assets must never point at `debugCapture`; run
`.\.venv\Scripts\python.exe -m pytest tests\test_debug_capture_boundary.py -q`
after changing asset/tool defaults.
If existing code still points at `debugCapture` for important dependencies,
move the dependency to the proper durable location and leave only regenerated
reports or screenshots in `debugCapture`.

## VTuber / VSeeFace Fallback Boundary

Assume VSeeFace is absent unless the user explicitly asks to install, launch, or
repair the external sidecar. VSeeFace is optional; it must not be required for
normal project open, preview, export, or VTuber Studio Program Output.

For VRM/VSeeFace-style workflows, start from this default:

- `Performance Source` is tracking input only.
- `Program Output` is the final broadcast/recorded picture.
- If VSeeFace is missing, black, degraded, or unregistered, use the internal VRM
  fallback path for Program Output.
- Do not spend a session chasing VSeeFace registration, virtual camera setup, or
  remote-window capture unless the user specifically asks for that sidecar
  work.
- Stable avatar assets belong under `external/assets/vtuber`; proof images,
  probe reports, screenshots, and generated motion/debug files may live in
  `debugCapture` only because they can be regenerated.

The current VTuber handoff index is `docs/WORKFLOW_VTUBER_BROADCAST_CONTEXT.md`.
The Trump-source mapping note is
`docs/VTUBER_TRUMP_SOURCE_MAPPING_CONTEXT.md`.

## Main Editor Boundary

`app/video_editor_window.py` is a compatibility facade. Do not add new feature
logic, UI classes, dialogs, long QSS blocks, workflow methods, media handlers,
or timeline behavior there.

Allowed in `app/video_editor_window.py`:

- imports and re-exports that preserve older public import paths
- `__all__`
- tiny compatibility helpers such as `_format_ms`, `_format_speed`, `_format_size`

When adding editor features, choose or create a focused module instead:

- editor startup/state: `app/video_editor_window_initializer.py`,
  `app/video_editor_window_core.py`
- method binding/legacy names: `app/video_editor_window_delegates.py`
- UI layout sections: `app/video_editor_ui_*.py`
- timeline operations/view/drag/layout: `app/video_editor_timeline_*.py`
- media import/proxy/thumbnailing: `app/video_editor_media_*.py`,
  `app/media_pool*.py`
- context menus: `app/video_editor_context_menu_*.py`
- player/preview bridge: `app/video_editor_player_bridge.py`,
  `app/video_editor_preview_*.py`
- export/render queue: `app/video_editor_export_*.py`,
  `app/video_editor_render_queue_bridge.py`
- color tools: `app/video_editor_color_*.py`, `app/color_*.py`
- audio tools: `app/video_editor_audio_*.py`, `app/audio_*.py`
- actor/Live2D/Spine/MMD/AR-PBR workflows:
  `app/video_editor_actor_*.py`, `app/video_editor_live2d_workflow.py`,
  `app/video_editor_mmd_workflow.py`, `app/ar_pbr/*`, `app/mmd/*`
- reusable action/MCP surfaces: `app/actions/*`, `app/automation_*.py`

If no suitable module exists, create a new focused module named after the
feature area. Wire it into the editor through `video_editor_window_delegates.py`,
the relevant controller/workflow module, or the initializer. Keep the facade
small.

## Editor Capture Means MCP/AI Capture

When the user says "캡쳐기능 봐줘", "에디터 안 캡쳐", "editor capture",
or similar without explicitly asking for launcher UI, assume they mean the
UI-less MCP/AI capture action surface, not the visible Capture app or editor
toolbar buttons.

Start from these files:

- `app/actions/evidence_namespace.py` for `capture.*` action registration.
- `app/actions/editor_adapter_editing_review.py` for screenshot/GIF/window
  capture action implementations.
- `app/actions/editor_adapter_core_helpers.py` for semantic capture targets
  such as `editor`, `viewer`, `timeline`, `media_pool`, `workbench`, `audio`,
  `color`, and diagnostic `screen`.
- `app/actions/ui_namespace.py` and `app/actions/editor_adapter_ui.py` for
  `ui.popout.capture`.
- `app/automation_bridge.py` and `app/automation_mcp.py` for MCP/AI exposure.
- `app/window_capture.py` for ownerless external Windows app screenshot/video
  capture.

For external tools such as Unreal Editor where another AI/agent controls when
the operation finishes, use `capture.window.video.start`, optionally poll
`capture.window.video.status`, and call `capture.window.video.stop` when the
external task completes. Always pass `max_duration_ms` as a hard safety cap.
If that external agent asks "until when?", answer: until it sends stop after
the task completes, or until `max_duration_ms` expires. The Unreal-side control
procedure is `docs/SPEC_UNREAL_MCP_CAPTURE_CONTROL.md`. For Unreal windows,
`backend=auto` should be used; it prefers `wgc_window` so overlapped Unreal
Editor windows can be captured as a window target, with visible-crop fallback.
Do not route Unreal evidence capture through OBS unless the user explicitly
asks for OBS output; if OBS records black, switch to direct Unreal `hwnd`
capture instead of retrying OBS.

Only inspect launcher capture UI (`app/controller.py`, `app/recorder.py`,
`app/capture.py`, recording bars/overlays) when the user explicitly asks about
the standalone Capture app, visible recording UI, region selection, or
capture-to-Studio handoff.

## AR/PBR Depth Preview Rules

Many agents only read this file or `SPEC.md`, so keep the core AR/PBR depth
contract here instead of relying only on `docs/SPEC_AR_PBR_COMPOSITOR.md`.

- The main viewer `Depth` toggle is diagnostic and user-controlled. It must stay
  off by default.
- Normal video playback must not estimate depth unless an active AR/PBR track
  explicitly needs depth for occlusion, scene/plane anchoring, or the user has
  enabled the Depth viewer toggle.
- Live depth estimation without a cache is allowed only as an intentional
  diagnostic/placement cost. Do not make it part of the baseline playback path.
- Depth-map-only viewing must not change export/composite output.
- Use `ProjectPlayer.set_ar_pbr_depth_view_mode(...)` or Python Actions
  `ar_pbr.preview.depth_view.get/set` for the viewer mode. Do not create
  parallel private toggles.
- Video-depth occlusion must use the shared normalization/effect-mask helpers in
  `app.ar_pbr.depth_occlusion` and viewer conversion in
  `app.ar_pbr.depth_view`.

## VTuber Source Visibility Rules

When mapping a source person capture/video to a VRM avatar, match the visible
person scope instead of showing an arbitrary VRM thumbnail:

- `face_only` / `face_closeup` source: VRM may use `bust_up`, but must still
  show head, neck, and shoulders; never use a face-only meta thumbnail as
  Program Output evidence.
- `chest_up` / `bust_up` / head-and-shoulders source: VRM must use `bust_up`
  / head-to-mid-chest framing. Do not widen this to `half_body` for normal
  talking-head or seated desk footage where the source is visible only to the
  chest.
  Product evidence must trim transparent avatar padding before fitting, keep
  the visible avatar large enough to read, and anchor the lower visible edge to
  the Program Output bottom safe line. Tiny or floating avatars are invalid
  even when the metadata says `bust_up`.
- `upper_body` source: VRM must use at least `half_body` / head-to-waist
  framing. If a caller asks for `bust_up`, upgrade it unless the user explicitly
  overrides with an allow-narrower flag.
- `full_body` source: VRM must use `full_body` / head-to-toe framing.
- The machine-readable rule is
  `match_source_person_exposure_to_vrm_visibility` from
  `app/vtuber/source_framing.py`. Source framing plans must expose
  `source_exposure` and `visibility_policy` so review automation and local AI
  can explain the chosen VRM framing.

## Refactor Guard

Run the architecture guard after editor-facing changes:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_editor_architecture_rules.py -q
```

Run the debug-capture boundary guard after changing tool or asset defaults:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_debug_capture_boundary.py -q
```

If the guard fails because a real feature was added to `video_editor_window.py`,
move that feature into a focused module instead of raising the limit.
