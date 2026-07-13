# Agent Start Here

This is the first durable handoff index for Codex/AI agents continuing work in
TigerCapture. Use it when the user says a previous session did work, when the
current task sounds like review automation or UI renewal, or when VTuber /
VSeeFace context is involved.

## Read Order

Always start with:

1. `AGENTS.md`
2. this file
3. the focused handoff/spec listed below for the active area

Focused entry points:

- UI renewal: `docs/UI_RENEWAL_THREAD_HANDOFF.md`,
  `docs/SPEC_UI_RENEWAL.md`, then `TODO.md`.
- MCP/AI editor capture, including user requests like "캡쳐기능 봐줘" or
  "에디터 안 캡쳐": `docs/SPEC_PYTHON_ACTION_SYSTEM.md`, then
  `docs/SPEC_UNREAL_MCP_CAPTURE_CONTROL.md` for Unreal/external-window
  capture control, then `app/actions/evidence_namespace.py` and
  `app/actions/editor_adapter_editing_review.py`. Treat this as action-only
  capture unless the user explicitly asks for visible Capture app UI.
- Review automation and presentation evidence:
  `docs/review_automation/AGENT_START_HERE.md`.
- Music Lab / AI Composer / generated audio playback artifacts:
  `docs/SPEC_AI_COMPOSER_MUSIC_LAB.md`, then the Music Lab section in
  `SPEC.md`.
- VTuber Studio, Program Output, VSeeFace, VRM, Trump source mapping:
  `docs/WORKFLOW_VTUBER_BROADCAST_CONTEXT.md`,
  `docs/VTUBER_TRUMP_SOURCE_MAPPING_CONTEXT.md`,
  `docs/SPEC_VTUBER_STUDIO_BROADCAST.md`,
  `docs/SPEC_VSEEFACE_BRIDGE.md`.
- MMD player: `docs/mmd_player_handoff.md`.

If two areas overlap, keep the product boundary from the focused docs. Do not
merge UI renewal, review automation, and VTuber sidecar setup into one unbounded
task unless the user explicitly asks for that.

## Current Hard Rules

- `debugCapture` is disposable scratch space. The user may delete it when it
  grows large. Do not store important source assets, SDKs, installed apps,
  manifests, project state, or non-regenerable files there.
- External apps and SDKs belong under `external/tools`.
- Third-party/local durable assets belong under `external/assets`.
- `app/video_editor_window.py` is a compatibility facade. Add editor features in
  focused modules and wire them through delegates, controllers, or popouts.
- Tiger Studio and the lightweight capture launcher are separated product
  surfaces. The capture program may be bundled with Studio, but capture-to-Studio
  handoff is blocked by default through
  `app.launcher_studio_policy.capture_to_studio_enabled()`. Only explicit
  bundle/QA opt-in such as `TIGERCAPTURE_CAPTURE_TO_STUDIO=1` should expose
  Studio buttons or construct `VideoEditorWindow` from the capture app.
  `main.py` is the capture-app entry point; `studio_main.py`, `TigerCapture.exe
  --studio`, packaged `TigerStudio.exe`, and source-built `TigerStudio.exe` are
  the Studio entry paths.
- In editor context, "capture" without explicit launcher/recording UI wording
  means MCP/AI action capture: `capture.targets`, `capture.screenshot`,
  `capture.gif`, `capture.windows.list`, `capture.window.screenshot`,
  `capture.window.video`, and `ui.popout.capture`. Do not start by changing
  toolbar buttons or the standalone capture launcher for that request.
  For external tasks with unknown duration, such as Unreal terrain generation,
  use `capture.window.video.start/status/stop` with `max_duration_ms` as the
  hard timeout instead of guessing one fixed `duration_ms`. Use `backend=auto`
  for Unreal so TigerCapture tries `wgc_window` before visible-crop fallback.
  Do not route Unreal evidence capture through OBS by default; OBS black output
  should be treated as an OBS/source failure and replaced with direct Unreal
  `hwnd` capture.
- Music Lab playback-safe files are for human listening only and must be made
  from the measured WAV by 48 kHz conversion plus peak normalization only. Do
  not add warm-up beds, pre-roll, noise floors, synthetic silence padding, or
  other "player stability" audio; a previous attempt introduced a false audible
  cut that was not present in the measured render. If the original probe report
  is clean but a playback-safe copy cuts, audit the companion-file generator
  before changing the composer or mix code.
- Music Lab's basic/default renderer is sample/SoundFont-based
  `backend=sample_production` with `sample_library_policy=auto`. AI/production
  audio is the advanced path and must be selected explicitly with
  `backend=production` or a concrete `ai_provider`; `auto` must not silently
  switch to AI just because a provider is configured.
- One-click Music Lab requests such as "make BGM/music" must render through the
  default sample-production studio master profile
  `one_click_sample_production_studio_v1`: bus tone shaping, rumble/mud
  control, presence/air enhancement, room ambience, mid-side width, parallel
  glue compression, dropout/surge repair, sample-jump smoothing, and soft
  preview limiting. The same route also applies
  `sample_production_articulation_expression_v1`, which classifies notes by
  role/length, shapes short-note gates, writes CC1/CC11 expression automation
  for SoundFont renders, and shapes internal fallback envelopes. Do not return
  raw SoundFont/internal-synth audio for that path unless the user explicitly
  chooses a diagnostic comparison.
- After editor-facing changes, run
  `.\.venv\Scripts\python.exe -m pytest tests\test_editor_architecture_rules.py -q`.

## VTuber Default Assumption

As of 2026-07-07, assume VSeeFace is absent unless the user explicitly asks to
work on the VSeeFace sidecar. TigerCapture must still provide a usable VTuber
Studio path through its own internal VRM fallback.

Default behavior for VRM/VSeeFace-style work:

- `Performance Source` is face/body tracking input only.
- `Program Output` is the final recorded or streamed picture.
- The raw Trump/person source video must not be used as Program Output.
- Studio and VRM rendering must use the VTuber VRM/MToon renderer boundary
  (`app/vtuber/vrm_renderer.py`, renderer family `vtuber_vrm`). Do not route
  `.vrm`, Avatar Mapping, or internal VRM Program Output through AR/PBR,
  Marmoset PBR, generic AR/PBR `full-gpu` debug proof images, or old debug proof
  images. Product-catalog VTuber evidence must request and prove the exposed
  VTuber backend `vrm_mtoon_gpu`. Legacy `vrm_mtoon_software` /
  `software-zbuffer` output is diagnostic only and must be rejected for product
  screenshots because it can produce point-like broken avatar output.
- Source-person visibility must drive VRM visibility. The code rule is
  `match_source_person_exposure_to_vrm_visibility` in
  `app/vtuber/source_framing.py`: `face_only` maps to `bust_up`,
  `chest_up` / `bust_up` maps to `bust_up` / head-to-mid-chest, `upper_body`
  maps to at least `half_body`, and `full_body` maps to `full_body`.
  Product evidence must also trim transparent avatar padding before fitting,
  scale the visible avatar large enough to read, and anchor its lower visible
  edge to the Program Output bottom safe line. Tiny/floating avatars are not
  valid product evidence.
  Source framing plans expose `source_exposure` and
  `visibility_policy` for AI/review automation; do not show a head-only or
  face-only VRM thumbnail when the source person is chest-up, upper-body, or
  full-body.
- VSeeFace missing, black, degraded, unregistered, or not installed is a
  degraded sidecar state, not a blocker for Program Output when internal VRM
  fallback assets are available.
- Do not chase VSeeFace virtual-camera registration or window-capture debugging
  unless the user explicitly asks for sidecar repair.

Current stable local references:

```text
Trump source video:
C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\trump_oval_office_live_GnzWEo_HfE0.mp4

Milica VRM:
external\assets\vtuber\booth_milica\Milica1.3free\Milica_v1.3.vrm

Optional VSeeFace sidecar install root:
external\tools\vseeface
```

Current fallback note: `app/vtuber/internal_vrm_fallback.py` no longer requires
generated `debugCapture` descriptor or motion files for its default path. It
loads the durable `.vrm` through the VTuber VRM/MToon renderer boundary and uses
internal idle motion when `debugCapture` has been cleaned. Remaining debt is
first-frame performance: runtime VRM descriptor generation/rendering can be slow
and needs a dedicated optimization pass before making strong preview-performance
claims.
2026-07-10 update: Trump-to-VRM pitch now goes through
`app.vtuber.vrm_motion_mapping.source_pitch_to_vrm_pitch`
(`vrm_pitch = -source_pitch - 12deg`) for internal VRM pose curves and VMC
messages. The latest real Studio proof uses `vrm_mtoon_gpu` and records
`mapped_vrm_motion.pitch_deg=-12.97`. Live-render diagnostics are faster after
the helper keeps the hidden Qt/GL widget alive: cached frames measured about
`2.852s/frame` with `gpu_widget_cache_hit=1`, `build_vertex_buffer_s ~= 1.23`,
and `gpu_widget_grab_s ~= 0.035`. This is still not real-time; the next
bottleneck is per-frame CPU vertex-buffer build plus helper-service round trip.
Do not lower triangle caps aggressively because dense hair/cloth becomes
visibly dotted.

## Evidence Discipline

Review/catalog/PPT evidence must use real TigerCapture UI screenshots and real
rendered proof outputs. Generated monitor frames, mockups, and debug captures
can be used only when clearly labeled as design/reference or regenerated proof,
not as fake editor evidence.
