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
- Review automation and presentation evidence:
  `docs/review_automation/AGENT_START_HERE.md`.
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
  `upper_body` maps to at least `half_body`, and `full_body` maps to
  `full_body`. Source framing plans expose `source_exposure` and
  `visibility_policy` for AI/review automation; do not show a head-only or
  face-only VRM thumbnail when the source person is upper-body or full-body.
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

## Evidence Discipline

Review/catalog/PPT evidence must use real TigerCapture UI screenshots and real
rendered proof outputs. Generated monitor frames, mockups, and debug captures
can be used only when clearly labeled as design/reference or regenerated proof,
not as fake editor evidence.
