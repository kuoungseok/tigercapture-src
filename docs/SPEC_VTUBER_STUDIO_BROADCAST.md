# VTuber Studio / Broadcast Contract

Date: 2026-07-02

This is the canonical product contract for the shared VTuber Studio, Avatar
Target routing, Performance Source handling, Live2D/VRM broadcast output, and
Broadcast Evidence release gate.

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
  - RTMP/Discord registration dialog defaults
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
  - keeps `performance_source_direct_output=false`.
- `app/video_editor_popouts.py`
  - owns `VTuberBroadcastStudioWindow`;
  - owns the Avatar Target selector;
  - owns Live Target controls;
  - owns the Broadcast Evidence card;
  - exposes Refresh Evidence, Register RTMP, and Register Discord controls.
- `app/broadcast_evidence_ui.py`
  - owns product copy/defaults/payload helpers for evidence UI.
- `app/broadcast_platform_e2e.py`
  - checks Local Program Output MP4;
  - checks Live2D Program Output MP4;
  - checks capture/composite output;
  - reserves manual slots for private RTMP ingest and Discord/window-share;
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
- `discord_window_share`

Evidence can be registered from:

- VTuber Studio `Register RTMP`
- VTuber Studio `Register Discord`
- Python Action `broadcast.platform_evidence.register`

Registration must require `confirm_redacted=true`. Notes and paths must reject
token/password/stream-key-like secrets. The UI must not show raw JSON/debug
dumps as the operator-facing evidence screen.

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
- Commercial/sale-ready must remain blocked until redacted private RTMP and
  Discord/window-share evidence are registered.
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
3. Run a real Discord/window-share test.
4. Register redacted Discord evidence.
5. Rerun broadcast release readiness and confirm whether
   `commercial_ready=true`.
