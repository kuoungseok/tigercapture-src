# Broadcast Scene Core

TigerCapture should not embed OBS just to host a VSeeFace sidecar. The app needs
the small subset of OBS concepts that make a live avatar source usable:

- a canvas profile;
- ordered sources;
- source transform, visibility, opacity, and fit mode;
- alpha and chroma-key compositing;
- audio channel state;
- diagnostics for missing live source frames.

The UI-neutral contract lives in:

```python
from app.broadcast_scene import (
    BroadcastScene,
    composite_broadcast_frame,
    create_vseeface_bridge_scene,
)
from app.broadcast_output import broadcast_output_preflight
```

## Scene Payload

```json
{
  "id": "vseeface_bridge_scene",
  "name": "VSeeFace Bridge",
  "canvas": {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "background": [0, 0, 0, 255]
  },
  "sources": [
    {
      "id": "background",
      "type": "color",
      "z_index": 0,
      "settings": {"color": [0, 0, 0, 255]}
    },
    {
      "id": "vseeface",
      "type": "vseeface",
      "z_index": 10,
      "transform": {
        "x": 0,
        "y": 0,
        "width": 1920,
        "height": 1080,
        "fit": "contain",
        "opacity": 1.0,
        "visible": true
      },
      "chroma_key": {"enabled": false},
      "settings": {"suppress_black_frame": true}
    }
  ],
  "audio": [
    {"id": "mic", "name": "Mic/Aux", "volume": 1.0, "muted": false},
    {"id": "desktop", "name": "Desktop Audio", "volume": 1.0, "muted": false}
  ]
}
```

## Current Scope

Implemented:

- RGB/RGBA source frames;
- color sources;
- VSeeFace/window/display/camera/image source placeholders;
- UI-neutral capture-source resolution through
  `app.broadcast_capture_backend`: external frame-map sources, image files,
  OpenCV camera frames, and explicit screen/window regions can be resolved into
  the frame map consumed by `composite_broadcast_frame(...)`. This path is
  OBS-free; title-based window lookup remains a platform/UI layer.
- stretch/contain/cover/original fit modes;
- opacity and alpha blending;
- chroma key through `app.chroma_key.ChromaKeyParams`;
- optional all-black frame suppression via source setting
  `suppress_black_frame=true`;
- missing-source diagnostics plus degraded-source diagnostics;
- default VSeeFace bridge scene;
- FFmpeg command preflight for raw RGB scene output to MP4 recording or RTMP.
- Live Target presets and preflight for `Local MP4`, `YouTube Live`,
  `Twitch`, `Custom RTMP / RTMPS`, `Discord / Video Call Output`, and
  experimental `TikTok Live`, `Instagram Live`, and `X Live` targets.
- `BroadcastOutputSession`, which starts/stops an FFmpeg stdin process for
  recording/RTMP targets and writes already-composited Program Output RGB
  frames.
- Live output recovery diagnostics: RTMP sessions can auto-reconnect when the
  FFmpeg process exits or a frame write fails, and status payloads expose
  `health`, `retry_count`, `max_retries`, `last_exit_code`, `last_write_ms`,
  `max_write_ms`, `backpressure_count`, `recovery_action`, redacted
  `stderr_tail`, `platform_error_kind`, and `platform_error_message`.
- Operator reconnect policy: RTMP Live Target settings expose a retry count.
  `max_retries=0` disables auto reconnect; the default RTMP policy is 3.
- Platform-aware troubleshooting guidance through
  `app.broadcast_troubleshooting.build_live_target_troubleshooting(...)` and
  the `broadcast.live_target.troubleshoot` Python Action. This expands
  classified live-output failures into concise operator checks for YouTube,
  Twitch, Custom RTMP/RTMPS, TikTok, Instagram, X, and Discord/video-call output.
- Troubleshooting panel payloads with check item completion state and clickable
  actions. The legacy `checks` string list stays for compatibility, while
  `check_items` and `panel.items` expose `status`, `completed`, action kind,
  optional dashboard URL, or registered Python Action id.
- Broadcast commercial-readiness diagnostics through
  `app.broadcast_release_readiness.build_broadcast_release_readiness_report`,
  `tools/qa_broadcast_release_readiness.py`, and the
  `broadcast.release_readiness` Python Action. The gate separates
  `alpha_ready` from `commercial_ready`; missing real platform/device evidence
  blocks sale-ready claims without blocking local alpha use.
- Broadcast E2E evidence artifacts through
  `app.broadcast_platform_e2e.build_broadcast_platform_e2e_report` and
  `tools/qa_broadcast_platform_e2e.py`. The tool can generate local
  Record-to-file FFmpeg evidence, Live2D Program Output Record-to-file
  evidence, and capture/composite evidence automatically, while RTMP ingest and
  Discord/video-call checks remain explicit manual platform evidence slots.
  Redacted manual evidence can be registered with
  `tools/register_broadcast_platform_evidence.py --check-id private_rtmp_ingest`
  or `--check-id discord_window_share --confirm-redacted`.
- Operator-facing broadcast evidence checklist through
  `app.broadcast_platform_e2e.build_broadcast_platform_evidence_checklist`,
  the `broadcast.platform_evidence_checklist` Python Action, and the shared
  `VTuberBroadcastStudioWindow` Broadcast Evidence card. The Studio UI is
  implemented in `app/video_editor_popouts.py` after the first editor split;
  future popout/VTuber Studio UI changes should stay there instead of returning
  to `app/video_editor_window.py`. The Studio card shows concise status and the
  next human check; detailed registration commands stay in the action/checklist
  payload instead of being shown as debug JSON. UI-neutral status text,
  registration defaults, and form payload normalization live in
  `app.broadcast_evidence_ui`.
- Redacted evidence registration through
  `broadcast.platform_evidence.register`, which wraps
  `register_manual_platform_evidence` and requires `confirm_redacted=true`.
  The action rejects secret-like notes/paths and should only be used after a
  real private RTMP or Discord/window-share check has been completed. The
  shared `VTuberBroadcastStudioWindow` exposes this as Register RTMP/Register
  Discord buttons that open a redaction-confirming form instead of showing raw
  JSON or asking users to run a command manually.
- VTuber Studio `Live Target` controls that can start/stop the session and feed
  `ProjectPlayer.gpu_frame_ready` RGB frames into the output session.
- Live audio input routing for FFmpeg sessions:
  - generated silent stereo audio;
  - Windows DirectShow audio device name;
  - looped audio file input;
  - TigerCapture project audio bus, materialized asynchronously to a temporary
    WAV before starting the live FFmpeg session.
- Vertical canvas recommendation for TikTok/Instagram-style targets.
- Virtual-camera planning for Discord/video-call output with Program Output
  window sharing as the OBS-free default and installed OBS/Spout2/NDI backend
  contracts as opt-in choices when available.
- OBS Virtual Camera bridge planning through
  `app.broadcast_virtual_camera.obs_virtual_camera_bridge_plan(...)` and the
  `broadcast.virtual_camera.plan` /
  `broadcast.virtual_camera.obs_bridge_plan` Python Actions. The bridge contract
  uses OBS Window Capture of Tiger Studio Program Output, never sends a
  Performance Source directly to the call, and exposes optional OBS WebSocket
  readiness without requiring it.
- Confirmed OBS WebSocket setup gates through
  `obs_virtual_camera_bridge_execution_gate(...)`,
  `obs_virtual_camera_bridge_executor_dry_run(...)`, and
  `execute_obs_virtual_camera_bridge(...)`, exposed as
  `broadcast.virtual_camera.obs_bridge_gate`,
  `broadcast.virtual_camera.obs_bridge_dry_run`, and
  `broadcast.virtual_camera.obs_bridge_execute`. Execution requires explicit
  confirmation, an installed OBS backend, WebSocket enabled, and the optional
  `obsws-python` dependency.
- Optional OS credential-store helper for stream keys through a lazy `keyring`
  backend; projects still never store raw stream keys.

Not implemented yet:

- title-based native window lookup and full display picker UX. Explicit
  screen/window region capture and OpenCV camera capture contracts exist, but
  the polished platform picker still needs UI integration.
- Spout2/NDI/virtual-camera input;
- GPU compositor;
- source rotation in the CPU compositor;
- detailed per-filter audio mixdown failure UX. The current worker reads FFmpeg
  progress and supports Stop-driven cancellation, but audio-specific errors are
  still summarized from FFmpeg stderr tails.
- bundled virtual-camera driver installation. TigerCapture plans OBS/Spout2/NDI
  output when those backends are already installed, and otherwise uses Program
  Output window sharing.
- reconnect/retry/backpressure UI for failed or slow live targets.

## Output Preflight

The current output layer builds commands only; it does not start a stream.

```python
diag = broadcast_output_preflight(
    {"kind": "rtmp", "target": "rtmp://server/app/key"},
    {"width": 1920, "height": 1080, "fps": 30},
)
```

The command expects `rgb24` frames on stdin. This matches
`composite_broadcast_frame(..., output_alpha=False)`.

`BroadcastOutputSession` is the runtime layer:

```python
from app.broadcast_output_session import BroadcastOutputSession

session = BroadcastOutputSession(
    {"target_id": "youtube_live", "stream_key": "..."},
    {"width": 1920, "height": 1080, "fps": 30},
)
session.start()
session.write_frame(program_rgb)
session.stop()
```

The session accepts `numpy` RGB/RGBA frames, PIL images, or raw RGB24 bytes. It
resizes frames to the selected canvas when needed, redacts stream keys from
status payloads, and never stores stream keys in project settings. RTMP sessions
default to `auto_reconnect=true` with `max_retries=3`; recording targets do not
auto-restart because doing so can overwrite or split local files. FFmpeg stderr
is drained on a background reader so the pipe cannot block the process; status
payloads keep only a short redacted tail and classify common live failures such
as stream-key/auth rejection, bad server URL, network timeout, connection reset,
and FFmpeg configuration errors. `status["troubleshooting"]` contains the
platform-specific checklist and primary action for the current failure.

Live audio is intentionally explicit. `include_audio=true` requires one of:

```json
{"audio_source_kind": "silence"}
{"audio_source_kind": "project_audio_bus"}
{"audio_source_kind": "dshow_device", "audio_device_name": "Microphone"}
{"audio_source_kind": "file", "audio_file": "music.wav"}
```

`project_audio_bus` reuses the same `app.audio_tracks.build_audio_filter` path
as export. Timeline trim, cuts, fades, gain, pan, automation, and clip effects
are rendered to a temporary WAV, then attached to the live FFmpeg session as a
looped file input. The live Studio starts the mixdown in a worker thread,
displays FFmpeg `-progress pipe:1` completion percentage, and cancels the FFmpeg
process if the operator stops the Live Target during preparation.

## Live Target Presets

The Live Target layer is a user-facing wrapper around `BroadcastOutputProfile`.
It chooses the output kind and validates the platform-specific inputs without
starting an external process:

```python
from app.broadcast_output import live_target_preflight

diag = live_target_preflight(
    {"target_id": "youtube_live", "stream_key": "..."},
    {"width": 1920, "height": 1080, "fps": 30},
)
```

Core targets:

- `record_file`: `Local MP4` recording target. `local_mp4` is accepted as a
  UI/action alias but persists as `record_file` for project compatibility.
- `youtube_live`: RTMPS preset plus session-only stream key.
- `twitch`: RTMP ingest preset plus session-only stream key.
- `custom_rtmp`: user-provided RTMP/RTMPS URL.
- `discord_video_call`: Program Output window/virtual-camera style target, not
  RTMP.

Experimental targets:

- `tiktok_live`
- `instagram_live`
- `x_live`

Experimental targets require platform-issued RTMP/RTMPS server URL and stream
key. TikTok/Instagram default to a vertical Program Output canvas preset. The
project file must not store raw stream keys; the UI keeps keys session-only and
stores only non-secret target settings.

For Discord/video-call apps, `virtual_camera_output_plan(...)` chooses an
OBS-free path by default: share the Tiger Studio Program Output window directly.
This works without OBS, a driver install, or a VSeeFace/OBS dependency. OBS uses
a Window Capture of the Tiger Studio Program Output window and exposes OBS
Virtual Camera to Discord only when the user explicitly selects that backend or
the caller opts into installed-backend auto-selection. Spout2 and NDI are also
represented as explicit sender contracts. Installation remains user-approved
only.

When a virtual-camera device backend is already installed, the plan can select
`pyvirtualcam_device`. `BroadcastVirtualCameraDeviceSession` then writes
already-composited Program Output RGB frames into the installed backend. This is
still user-approved-only integration: TigerCapture does not install a camera
driver, and if no backend is available the default remains Program Output window
sharing.

OBS setup is represented by a separate bridge plan:

```python
from app.broadcast_virtual_camera import obs_virtual_camera_bridge_plan

plan = obs_virtual_camera_bridge_plan(
    {
        "program_window_title": "Tiger Studio Program Output",
        "scene_name": "Tiger Studio Program Output",
        "source_name": "Tiger Studio Program Output",
    },
    installed_backends={"obs_virtual_camera": {"available": True}},
)
```

The plan may launch/configure OBS only after user confirmation. Automatic scene
configuration is allowed only when OBS WebSocket is explicitly enabled and the
optional `obsws-python` dependency is available. Without that, the UI should
show the operator steps: open OBS, add Program Output as Window Capture, start
OBS Virtual Camera, then select it in Discord or the video-call app.

The execution path is intentionally gated:

```python
from app.broadcast_virtual_camera import (
    obs_virtual_camera_bridge_execution_gate,
    obs_virtual_camera_bridge_executor_dry_run,
)

gate = obs_virtual_camera_bridge_execution_gate(
    {
        "confirm": True,
        "websocket_enabled": True,
        "obsws_available": True,
    },
    installed_backends={"obs_virtual_camera": {"available": True}},
)
dry_run = obs_virtual_camera_bridge_executor_dry_run(...)
```

Only `execute_obs_virtual_camera_bridge(...)` connects to OBS. It uses
obsws-python lazily, does not install drivers, and returns operation statuses
for connect, scene creation, Window Capture source creation/update, and starting
OBS Virtual Camera.

## Program Output vs Performance Source

VTuber performance-source media is tracking input, not a broadcast background.
For example, a Trump speech video may drive face/mouth/head motion, but that
video must only appear in the Source Tracking monitor. It must not leak into
Program Output.

The UI-neutral contract lives in `app.vtuber.performance_source`:

```python
from app.vtuber.performance_source import (
    choose_program_background_at,
    active_performance_source_at,
    program_output_contract,
)
```

Program Output background selection is:

1. If a capture item is active at the current timeline time, use that capture.
2. Otherwise use the active normal video/image timeline clip.
3. Otherwise use a green chroma fallback.
4. Never use a `vtuber_performance_source` / `performance_source_track` clip as
   Program Output background.

Media Pool and timeline UI labels should use "Performance Source" / "퍼포먼스
소스" with a compact `PERF` badge. The older "Avatar Source" / "아바타소스"
wording is reserved for legacy/internal compatibility only.
Canonical Korean UI wording is `퍼포먼스 소스`; older mojibake text in this
section must not be copied into UI or new specs.

Python Action / MCP automation must use the registered action surface instead
of calling editor private methods directly:

- `vtuber.performance_source.summary`
- `vtuber.performance_source.mark_media`
- `vtuber.performance_source.add_clip`
- `vtuber.program_output_contract`
- `actor.live2d.apply_performance_source`

These actions mark Media Pool items, place input-only Performance Source clips
on a dedicated timeline track, and verify that Program Output still uses only
capture, normal media, or green chroma fallback as its background.
`actor.live2d.apply_performance_source` uses the active Performance Source at
the requested timeline time as Live2D tracking input. It can apply mocap
parameter keyframes and VTuber source-framing camera guidance to the Live2D
actor clip, but it never promotes the Performance Source video into Program
Output.

## VSeeFace Bridge Direction

The VSeeFace integration is a permanent external-sidecar bridge, not an
embedded editor module. The formal sidecar contract is documented in
`docs/SPEC_VSEEFACE_BRIDGE.md` and implemented under `app/vtuber/`.

The bridge should fill the scene frame map with a source id of `vseeface`.
If VSeeFace capture is explicitly unready, for example
`capture_ready=false` with `capture_status=virtual_camera_black_frame`, scene
diagnostics report the source under `degraded_frame_sources` instead of failing
the whole scene under `missing_frame_sources`.
Capture options can be added in this order:

1. transparent or chroma-keyed window capture;
2. Spout2 capture when available;
3. virtual camera fallback;
4. VMC/OSC control and tracking data sync.

The first shippable path can be:

```text
VSeeFace companion process
-> live frame capture as "vseeface"
-> BroadcastScene compositor
-> TigerCapture preview/record/export or future live output
```

OBS can remain optional. The broadcast scene core is the internal scene mixer the
app needs whether final output goes through OBS, TigerCapture recording, or a
future RTMP encoder.
