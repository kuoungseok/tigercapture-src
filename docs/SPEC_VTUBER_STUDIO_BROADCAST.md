# VTuber Studio / Broadcast Contract

Date: 2026-07-02

This is the canonical product contract for the shared VTuber Studio, Avatar
Target routing, Performance Source handling, Live2D/VRM broadcast output, and
Broadcast Evidence release gate.

## Agent Read First

As of 2026-07-07, VSeeFace is optional and should be assumed absent unless the
user explicitly asks for sidecar installation, launch, or repair. The shared
VTuber Studio must still produce Program Output through TigerCapture's internal
VRM fallback when VSeeFace is missing, black, degraded, or unregistered.

Stable avatar/source assets belong under `external/assets` or the user's media
folders. `debugCapture` is disposable diagnostics only and must not be required
for normal Studio operation.

Studio/VRM rendering must use the VTuber VRM/MToon renderer boundary:
`app/vtuber/vrm_renderer.py`, renderer family `vtuber_vrm`, render profile
`vrm_mtoon`. `.vrm` Program Output, Avatar Mapping, and internal VRM fallback
must not be routed through AR/PBR preview, Marmoset PBR, or old debug proof
images. The exposed backend is `vrm_mtoon_gpu`; `auto`, `mtoon`,
`vrm_mtoon`, PBR-looking aliases, and legacy `vrm_mtoon_software` requests are
rewritten to `vrm_mtoon_gpu`. The legacy software VRM renderer is disabled for
product/UI/AI-selected routes because it can display dense VRM meshes as broken
point-like contact previews. Renderer contracts expose
`software_renderer_available=false`, `legacy_software_renderer_disabled=true`,
`requested_renderer`, `renderer_rewritten`, and rewrite warnings.

The one-shot `render_internal_vrm_fallback_frame(..., renderer=vrm_mtoon_gpu)`
export helper is not a live-preview renderer. It may be used for QA/export
proof frames, prewarm, or cache generation, but Studio playback and broadcast
operator previews must not call it once per displayed frame. Product preview
must use a persistent VRM/MToon renderer worker or an explicit prerender/runtime
cache while the worker is warming. Any evidence that uses the cache must mark
that state separately from true per-frame live VRM rendering.

As of 2026-07-10, source pitch is converted through
`app.vtuber.vrm_motion_mapping.source_pitch_to_vrm_pitch`: VRM pitch is
`-source_pitch + rest_bias`, with a default rest bias of `-12` degrees. This is
intentional. OpenSeeFace CSV pitch is source-space motion and early neutral
calibration can erase a speaker who already starts slightly looking down. The
VRM/MToon target must therefore use the shared mapping helper for internal
fallback renders and VMC messages; do not apply `FaceMotionFrame.pitch_deg`
directly to VRM head/neck/chest bones.

The current measured live-render diagnostic path is still not real-time, but it
no longer rebuilds the hidden Qt/GL widget every frame. A 2026-07-10
Trump/Milica proof with a conservative preview triangle cap of `12000` measured
about `13.28s` before widget reuse, then about `2.85s` on a cached-widget frame.
The cached timing was about `1.23s` vertex-buffer build and `0.035s` GL widget
grab (`gpu_widget_cache_hit=1`). The remaining renderer fix is to remove the
per-frame CPU vertex-buffer build/service round trip, preferably by persistent
VRM render sessions with VBO updates and then GPU skinning. Lowering the
preview triangle cap too aggressively is invalid because it breaks dense
hair/cloth into dotted artifacts.

Source-person visibility must drive avatar visibility through
`match_source_person_exposure_to_vrm_visibility`: `face_only` -> `bust_up`,
`chest_up` / `bust_up` -> `bust_up` / head-to-mid-chest, `upper_body` ->
at least `half_body`, and `full_body` -> `full_body`.
Product evidence must also trim transparent avatar padding before fitting,
scale the visible avatar large enough to read, and anchor the lower visible
edge to the Program Output bottom safe line. A tiny or floating avatar is
invalid even when the preset label is `bust_up`.
Studio evidence, Program Output, and review automation must read
`source_exposure` plus `visibility_policy` from source-framing plans and reject
face-only/head-only VRM evidence for chest-up, upper-body, or full-body
sources.

## Core Rule

Tiger Studio has one shared VTuber Studio surface. Do not create separate
`VRM Studio` or `Live2D Studio` windows. The existing
`VTuberBroadcastStudioWindow` stays the common operator workspace, and the
selected `Avatar Target` changes only the workflow inside that window.

`Performance Source` is tracking input only. It can appear in Source Tracking
or Avatar Mapping monitors, but it must never be rendered directly into
`Program Output`.

Only `Program Output` is sent to:

- Local MP4
- RTMP/RTMPS
- Discord or video-call window share
- virtual-camera backends

Stream keys are session-only. They must not be written to project settings or
project files.

## Module Ownership

- Popout, detached dock, and VTuber Studio UI live in
  `app/video_editor_popouts.py`.
  - This file owns `VTuberBroadcastStudioWindow`.
  - This file owns `_BroadcastProjectAudioBusMixdownThread`.
  - Future VTuber Studio, popout, and detached dock UI work must stay here
    instead of returning to `app/video_editor_window.py`.
- Broadcast Evidence UI-neutral copy and payload helpers live in
  `app/broadcast_evidence_ui.py`.
  - status-line text
- RTMP/YouTube viewer registration dialog defaults
  - registration payload normalization
- Screen Studio Auto Polish dialog code lives in
  `app/video_editor_screenstudio_dialogs.py`.
- Python Action and MCP surfaces must remain registered-action based. Do not
  expose private editor methods directly, and do not churn action IDs unless a
  product contract changes.

## Terms

- `Avatar Target`: selected VRM/VSeeFace target, Live2D actor clip, or future
  avatar target.
- `Performance Source`: camera or video tracking input only.
- `Program Output`: final broadcast/recorded picture. Never direct
  Performance Source video.
- `Live Target`: Program Output destination, such as Local MP4, RTMP/RTMPS,
  Discord/window-share, or virtual camera.
- `VRM / VSeeFace Bridge`: VRM target path using bridge/pose stream data.

The UI must not use the old term `Avatar Source` or `아바타소스`. Use
`Performance Source` / `퍼포먼스 소스`.

## Avatar Target Flows

VRM / VSeeFace Bridge:

```text
Performance Source
-> OpenSeeFace / VMC / pose stream
-> VRM / VSeeFace Bridge
-> Program Output
-> Live Target
```

VSeeFace is an optional sidecar. If it is unavailable, black, or degraded, the
Studio can use the internal VRM fallback path for Program Output.

Live2D actor clip:

```text
Performance Source
-> Live2D key/parameter mapping
-> Live2D actor Program Output composition
-> Live Target
```

Live2D direct key baking is Live2D-target specific. VRM/VSeeFace targets do not
use `actor.live2d.apply_performance_source`.

Both targets share the same VTuber Studio UI and the same Program Output /
Live Target output path.

## Current Implementation Contracts

- `app/vtuber/broadcast_studio_layout.py`
  - exposes the `avatar_target` contract;
  - marks VRM and Live2D targets as `program_output=true`;
  - marks VRM and Live2D targets as `live_target_output=true`;
  - exposes VRM targets with `renderer_family=vtuber_vrm`,
    `render_profile=vrm_mtoon`, and `pbr_renderer=false`;
  - keeps `performance_source_direct_output=false`.
- `app/video_editor_popouts.py`
  - owns `VTuberBroadcastStudioWindow`;
  - owns the Avatar Target selector;
  - uses explicit preview fit modes for Program Output, Source Tracking, and
    Avatar Mapping so source frames do not overflow, mapping views do not shrink
    into a monitor-inside-monitor, and Program Output remains an operator
    monitor rather than a text card;
  - accepts real VRM Avatar Mapping preview pixmaps from the editor/proof path
    before falling back to the schematic mapping monitor; old arbitrary
    renderer/debug proof output must still be rejected by the evidence layer;
  - owns Live Target controls;
  - owns the Broadcast Evidence card;
  - exposes Refresh Evidence, Register RTMP, and Register YouTube View controls.
- `app/broadcast_evidence_ui.py`
  - owns product copy/defaults/payload helpers for evidence UI.
- `app/broadcast_platform_e2e.py`
  - checks Local Program Output MP4;
  - checks Live2D Program Output MP4;
  - checks capture/composite output;
  - reserves required manual slots for private RTMP ingest and YouTube
    private/unlisted viewer playback, with Discord/window-share as optional
    evidence;
  - exposes `build_broadcast_platform_evidence_checklist()`.
- `app/broadcast_release_readiness.py`
  - separates alpha-ready from commercial/sale-ready;
  - keeps `commercial_ready=false` until real platform evidence exists.

Registered public action surface:

```text
vtuber.studio.open
vtuber.avatar_target.summary
vtuber.avatar_target.select
vtuber.vrm.bridge_status
vtuber.vrm.pose_stream_preview
broadcast.live_target.summary
broadcast.live_target.select
broadcast.platform_evidence_checklist
broadcast.evidence_readiness.refresh
broadcast.platform_evidence.preflight
broadcast.platform_evidence.register
broadcast.release_readiness
actor.live2d.apply_performance_source
```

## Broadcast Evidence Gate

Automated local evidence can pass without external services:

- `record_file_local`
- `live2d_record_file_local`
- `capture_composite_local`

Commercial/sale readiness still requires two real redacted platform evidence
items:

- `private_rtmp_ingest`
- `youtube_unlisted_viewer_playback`

Current Broadcast commercial evidence status, as of 2026-07-10:

- `broadcast_commercial_evidence`: `missing`
- `private_rtmp_ingest`: not accepted as commercial evidence until a redacted
  evidence row is registered. A private YouTube ingest smoke can prove the
  encoder path, but it is still only partial until recorded in the evidence
  artifact.
- `youtube_unlisted_viewer_playback`: missing. A YouTube Studio preview that
  buffers or shows the avatar only briefly is not enough.
- `commercial_ready`: false.

Ingest health and viewer playback are separate evidence states. A green
TigerCapture/FFmpeg session must not satisfy the YouTube viewer playback row.

Optional claim-specific evidence:

- `discord_window_share`

Evidence can be registered from:

- VTuber Studio `Register RTMP`
- VTuber Studio `Register YouTube View`
- Python Action `broadcast.platform_evidence.register`

Registration must require `confirm_redacted=true`. Notes and paths must reject
token/password/stream-key-like secrets and direct YouTube watch/preview URLs
such as `youtube.com/watch`, `youtu.be`, `youtube.com/live`, and YouTube Studio
live/preview URLs. The UI must not show raw JSON/debug dumps as the
operator-facing evidence screen.

After registration, the evidence artifact is:

```text
debugCapture/broadcast_platform_e2e_qa.json
```

Readiness can be rechecked with:

```text
tools/qa_broadcast_release_readiness.py --allow-not-ready
```

or Python Action:

```text
broadcast.release_readiness
```

## Release Claim Meaning

- Alpha/local functionality can be ready when automated local Program Output
  checks pass.
- Commercial/sale-ready must remain blocked until redacted private RTMP ingest
  and YouTube private/unlisted viewer playback evidence are registered.
  Discord/window-share evidence is optional unless that specific claim is being
  marketed.
- Do not claim `commercial_ready=true` based only on local MP4 smoke tests.

Known current artifacts:

```text
debugCapture/broadcast_record_smoke.mp4
debugCapture/broadcast_live2d_record_smoke.mp4
debugCapture/broadcast_platform_e2e_qa.json
debugCapture/broadcast_release_readiness_qa.json
```

## Guardrails

- Do not add VTuber Studio, popout, or detached dock UI directly to
  `app/video_editor_window.py`.
- Keep Broadcast Evidence copy/defaults/payload logic in
  `app/broadcast_evidence_ui.py`.
- Keep Screen Studio Auto Polish dialog code in
  `app/video_editor_screenstudio_dialogs.py`.
- Never render Performance Source directly into Program Output.
- Never persist stream keys in project settings.
- Do not mix main UI renewal work with VTuber/Broadcast Evidence work unless a
  specific integration point requires it.
- Keep Live2D renderer quality and Performance Source action/control contracts
  separate.

## Remaining Real Work

1. Run a real private RTMP ingest test.
2. Register redacted RTMP evidence.
3. Open the real private/unlisted YouTube viewer or preview page.
4. Register redacted YouTube viewer evidence.
5. Rerun broadcast release readiness and confirm whether
   `commercial_ready=true`.
