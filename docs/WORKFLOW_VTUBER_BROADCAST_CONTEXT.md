# VTuber Broadcast Bridge Work Context

This is the active context for the standalone VTuber / VSeeFace-style broadcast
bridge work. It is separate from the Live2D-specific mapping work and separate
from the older AR/PBR road/FBX/Marmoset renderer stream.

The canonical product contract for the shared Studio, Program Output, Live
Target, session-only stream keys, and Broadcast Evidence gate is
`docs/SPEC_VTUBER_STUDIO_BROADCAST.md`. Use this workflow document for
thread-specific context and use the spec file as the stable implementation
contract.

## Read This First

2026-07-07 operating assumption: VSeeFace is absent unless the user explicitly
asks to install, launch, repair, or verify the external sidecar. Do not start a
new session by chasing VSeeFace registration or virtual-camera capture. The
default TigerCapture product path is the shared VTuber Studio using the internal
VRM fallback for Program Output when VSeeFace is missing, black, degraded, or
unregistered.

Durable local inputs belong outside `debugCapture`:

```text
Trump Performance Source:
C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\trump_oval_office_live_GnzWEo_HfE0.mp4

Milica VRM Avatar Target:
external\assets\vtuber\booth_milica\Milica1.3free\Milica_v1.3.vrm

Optional VSeeFace sidecar root:
external\tools\vseeface
```

`debugCapture` paths in this document are historical proof outputs or
regenerable diagnostics. They are not source-of-truth assets and may be missing.
`app/vtuber/internal_vrm_fallback.py` must remain usable after `debugCapture` is
cleaned by importing the durable VRM through the VTuber VRM/MToon renderer
boundary and using internal idle motion. Remaining implementation debt is
first-frame performance, not durable asset discovery.

## Current Boundary

The VTuber broadcast work is a shared bridge/workflow tranche with a thin
editor entry point. The canonical editor entry point is the existing shared
`VTuberBroadcastStudioWindow`; do not add separate VRM Studio or Live2D Studio
windows. Live2D and VRM use the same Studio surface. The selected asset or
`Avatar Target` changes the workflow inside that surface; it does not create a
new window or a different product mode. Standalone proof tools remain the
preferred way to verify bridge, framing, capture diagnostics, and output
contracts before making heavier Preview/Timeline integration changes:

## Current VTuber Studio Scope

Until the user explicitly changes scope, the active work in this thread is the
shared VTuber Studio with the VRM/VSeeFace target selected. VRM completion means
the whole Studio flow: VRM Media Pool import, `VRM / VSeeFace Bridge` target
selection, Performance Source tracking, OpenSeeFace/VMC pose mapping, internal
VRM fallback rendering, Program Output composition, and Live Target output
controls for recording or streaming. Do not treat RTMP/Discord/Live Target as
unrelated when they are part of the Studio's final output stage. Still do not
drift into Live2D-specific renderer tuning, AR/PBR road placement, Marmoset PBR,
or main editor UI renewal from this thread.

Hard renderer boundary: Studio and VRM output must use the VTuber VRM/MToon
renderer family (`vtuber_vrm`, `vrm_mtoon_gpu`). Do not route Avatar Mapping,
`.vrm` Program Output, or internal fallback through AR/PBR, Marmoset PBR, or
debug proof images. Legacy software renderer requests are disabled and
rewritten to `vrm_mtoon_gpu` because the software VRM path can show dense
avatars as broken point-like previews. AR/PBR helpers may only be treated as
hidden mesh parsing utilities behind `app/vtuber/vrm_renderer.py`, never as the
exposed VRM renderer.

Hard visibility boundary: source-person exposure must match VRM visibility via
`match_source_person_exposure_to_vrm_visibility`. `face_only` may use `bust_up`,
`chest_up` / `bust_up` must use `bust_up` / head-to-mid-chest, `upper_body`
must use at least `half_body`, and `full_body` must use `full_body`.
Source framing plans expose `source_exposure` and
`visibility_policy`; review automation should reject head-only/face-only VRM
evidence when the source is chest-up, upper-body, or full-body.

The operator flow is always:

```text
open shared VTuber Studio
-> choose an Avatar Target or asset
-> run the target-specific mapping workflow
-> inspect Program Output / Source Tracking / Avatar Mapping
-> choose a Live Target for record, RTMP/RTMPS, or video-call output
```

Target-specific branches:

- `.vrm` Media Pool item: selects `VRM / VSeeFace Bridge`, uses VSeeFace
  sidecar or internal VRM fallback, and streams a pose route.
- Live2D actor clip: uses the same Studio monitors, but the mapping path is
  Live2D-specific key/parameter application. Once the Live2D actor is visible
  in Program Output, Local MP4/RTMP/window-share Live Targets consume that same
  composited Program Output frame stream.
- Future avatar asset: adds another Avatar Target branch inside the same
  Studio.

- VSeeFace remains an external sidecar.
- Performance Source stays input-only tracking media.
- Program Output is produced by the broadcast scene/studio contract, not by
  showing the tracking source video directly.
- Live Targets are Program Output destinations. YouTube/Twitch/Custom RTMP use
  RTMP/RTMPS; Discord/video-call apps use Program Output window share or a
  future virtual-camera backend; TikTok/Instagram/X are experimental RTMP
  targets that require platform-issued server URL and stream key.
- Standalone tools such as `tools/render_vtuber_broadcast_studio_ui.py` remain
  the regression visual verification surface.
- The current editor integration is intentionally thin: open the shared VTuber
  Studio, select an `Avatar Target`, and inspect Program Output / Source
  Tracking / Avatar Mapping / Live Target state without duplicating windows.

## Optional VSeeFace Dependency UI

TigerCapture does not require VSeeFace for Program Output. VSeeFace is only an
external sidecar option. The bridge UI therefore needs a visible
dependency/setup card before VSeeFace-specific capture work:

1. Detect whether a configured `VSeeFace.exe` exists.
2. If a default sidecar install exists, ask the user to select/connect it.
3. If only a local `VSeeFace*.zip` exists, offer an explicit install action.
4. If nothing is available, offer download/install guidance and a script action
   that can download only from a user-approved URL or extract a user-provided
   zip.
5. After install, continue to VRM0 selection, tracking input, sidecar settings,
   capture backend probing, and Program Output connection.

The setup UI contract is exposed through `view.dependency` and the first
`setup_flow` step from `app.vtuber.vseeface_bridge.build_vseeface_bridge_status`.
The installer tool is `tools/install_vseeface_sidecar.py`; it does not run
automatically.

## Terms

- `Program Output`: the final frame that would be recorded or streamed.
- `Performance Source`: camera/video tracking input used to drive an avatar.
- `Avatar Target`: the selected avatar target inside the shared VTuber Studio,
  such as `VRM / VSeeFace Bridge`, a Live2D actor clip, or a future avatar.
- `Source Tracking`: monitor view where the Performance Source can be shown.
- `Avatar Mapping`: monitor view showing solved avatar framing and pose.
- `VTuber Studio`: the shared operator workspace around those views and
  controls. Live2D and VRM share this same UI. Avoid product names such as
  `VRM Studio` or `Live2D Studio` for this surface.
- `Live Target`: the selected Program Output destination, such as Local MP4,
  YouTube Live, Twitch, Custom RTMP, Discord/video-call output, or
  experimental TikTok/Instagram/X.

Use `program_output` in code/schema. In localized Korean UI, prefer the
equivalent of `Broadcast Output` over a literal debug-style schema label.

## Current Visual Verification

The current screenshot surface is:

```text
tools/render_vtuber_broadcast_studio_ui.py
```

That tool reads the standalone broadcast layout contract and local tracking/VRM
mapping artifacts, then renders a PNG. This is not the final editor integration.

The VSeeFace bridge status summary can be rendered from the actual post-install
probe report with:

```text
tools/render_vseeface_broadcast_scene_summary.py --capture-report debugCapture\vseeface_post_install_with_video_report.json --out debugCapture\vseeface_broadcast_scene_summary_black_probe_report.png
```

The 2026-07-01 local run starts the VSeeFace sidecar and generates face tracking
rows from a Trump source video, but VSeeFace's client area and
`VSeeFaceCamera` output are still black in this remote/GPU environment. The
bridge should treat that as `degraded`, suppress the black source from Program
Output, and prefer `Use internal VRM fallback` for Program Output. VSeeFace
repair/registration remains available as a secondary action because VSeeFace is
an optional sidecar, not the required output engine.

2026-07-10 broadcast QA update: the durable Trump source can drive the bundled
OpenSeeFace `facetracker.exe` reliably when the tracker input is cropped to the
speaker region (`0.26,0.02,0.44,0.68`) with try-hard detection and a lower
detection threshold. The full frame may produce a CSV containing only the header
and blank rows; blank CSV rows are not tracking data and must not make the
video-source report look successful. The default OpenSeeFace-to-VRM motion
tuning now lightly amplifies pitch/yaw/roll while preserving sign so subtle
human head turns remain readable on stylized VRM broadcast framing.
The OpenSeeFace motion frames also expose `chin_offset_x_norm`, computed from
Landmark[8] against the tracked landmark bounding-box center. Negative values
mean the chin is left of the face/head center in screen space. The Trump crop
shows this consistently (about `-0.23` face-width near 4.87s), so QA can detect
the original off-center jaw/face angle instead of relying only on Euler values.

2026-07-10 private YouTube Live QA status: a generated moving-square smoke test
successfully reached YouTube Studio, then a VRM Program Output smoke test showed
the Milica avatar in Studio briefly. The ingest-side status stayed healthy
enough to write frames, but the YouTube Studio preview still buffered/stalled
intermittently. Treat this as a real product bug, not a pass: RTMP ingest
connected and viewer playback visible are two separate evidence states. The
current `tools/stream_vrm_youtube_smoke.py` tool is a safe QA helper that reads
the stream key only from an environment variable and redacts reports, but its
Trump mapping path is a fast cached-sprite motion proxy. It is useful for
proving output plumbing and rough motion, not for claiming full per-frame
VRM/MToon avatar rendering.

Current stabilization blockers from the same run:

- YouTube may auto-start a private stream when ingest begins. The Studio UI must
  warn clearly about private/unlisted test mode, Stop ingest vs End stream, and
  stream key regeneration after any key exposure.
- First VRM fallback render can take tens of seconds, so Program Output needs a
  persistent descriptor/runtime cache or prewarm path before live use.
- YouTube Studio buffering must be captured as platform playback evidence, not
  hidden behind green FFmpeg status.
- Platform screenshots must come from the real editor/YouTube surface or be
  explicitly labeled diagnostics. Do not synthesize evidence frames.

2026-07-10 local editor proof update: `tools/run_vtuber_studio_trump_live.py`
now has a `--frame-source cached-bustup` mode that opens the real
`VTuberBroadcastStudioWindow`, fills Source Tracking with a Trump bust-up crop
derived from OpenSeeFace face boxes, and fills Program Output with actual
prerendered `vrm_mtoon_gpu` transparent bust-up frames. The status contract
records `source_tracking_fit=openseeface_face_box_to_bust_up_cover_16x9`,
`program_output_fit=broadcast_16x9_cover_background_plus_bust_up_vrm`, and a
Program avatar height ratio of about `0.96`. This fixes the local framing/UI
proof failure, but it is intentionally not a live renderer-performance pass:
the same Trump/Milica frames measured about 48-56 seconds per frame through
`render_internal_vrm_fallback_frame(..., renderer=vrm_mtoon_gpu)`. Product live
preview needs a persistent renderer worker plus descriptor/runtime/prerender
cache before any real-time claim.

2026-07-10 follow-up proof after agent review: the same tool now records
measured preview contracts and separate proof PNGs:

```text
debugCapture\vtuber_studio_trump_live_window_after_fit_fix.png
debugCapture\vtuber_studio_trump_live_window_after_fit_fix_program_output.png
debugCapture\vtuber_studio_trump_live_window_after_fit_fix_source_tracking.png
debugCapture\vtuber_studio_trump_live_window_after_fit_fix_avatar_mapping.png
debugCapture\vtuber_studio_trump_live_status_after_fit_fix.json
```

The fixed local status records `source_tracking_crop.crop_aspect=1.7796`,
`single_crop_then_resize=true`, `face_fully_visible=true`,
`program_avatar_height_ratio=0.9597`, `program_avatar_bottom_gap_ratio=0.0`,
and `program_avatar_grounded=true`. `app/video_editor_popouts.py` now accepts
real VRM mapping pixmaps for VRM targets instead of ignoring
`avatar_preview_image` and falling back to a small schematic. This is a local
Studio UI/framing pass; `live_renderer_currently_too_slow=true` remains until a
persistent VRM/MToon renderer worker replaces the one-shot export helper.

2026-07-10 live-render diagnostic follow-up: the Trump/Milica path now uses
`app.vtuber.vrm_motion_mapping.source_pitch_to_vrm_pitch` for both internal
VRM pose curves and VMC messages. The mapping is `vrm_pitch = -source_pitch -
12deg`, so a source that visually starts slightly looking down is no longer
neutralized into a backward-leaning VRM pose. Latest proof:

```text
debugCapture\vtuber_studio_trump_live_actual_render_widget_cache.png
debugCapture\vtuber_studio_trump_live_actual_render_widget_cache_program_output.png
debugCapture\vtuber_studio_trump_live_actual_render_widget_cache_source_tracking.png
debugCapture\vtuber_studio_trump_live_actual_render_widget_cache_avatar_mapping.png
debugCapture\vtuber_studio_trump_live_actual_render_widget_cache.json
```

That status records `renderer=vrm_mtoon_gpu`, `render_ok=true`,
`mapped_vrm_motion.pitch_deg=-12.97`, `program_avatar_height_ratio=0.8472`,
`program_avatar_grounded=true`, `live_preview_triangle_cap=12000`, and
`gpu_widget_cache_hit=1`. Renderer performance is improved but still not
acceptable for live playback: cached frames measured `actual_renderer_elapsed_s
=2.852`, with render timings approximately `build_vertex_buffer_s=1.2303`,
`hdri_load_s=0.1108`, and `gpu_widget_grab_s=0.0353`. A temporary `2400`
triangle cap reduced time but visibly broke the avatar into dotted hair/body
artifacts, so do not use low triangle caps as the renderer fix. The correct
next step is to remove the per-frame CPU vertex-buffer build and helper-service
round trip, then move animated skinning to GPU/VBO updates.

The internal fallback frame path is `app/vtuber/internal_vrm_fallback.py`. It
must render a transparent avatar frame without VSeeFace, OBS, virtual camera, or
Qt. It must not rely on temporary AR/PBR descriptor cache files or old
`debugCapture` proof PNGs. The standalone Program Output proof tool is:

```text
tools/render_internal_vrm_fallback_program_output.py --capture-report debugCapture\vseeface_post_install_with_video_report.json --out debugCapture\internal_vrm_fallback_program_output.png
```

That proof intentionally feeds a black VSeeFace frame into the BroadcastScene
compositor and verifies that Program Output suppresses it while rendering
`internal_vrm_fallback`.

VTuber Studio is a shared operator surface, not a Live2D-only window and not a
separate VRM-only window. The editor entry point remains the existing
`VTuberBroadcastStudioWindow`; its implementation lives in
`app/video_editor_popouts.py` after the first editor UI split. Future popout,
detached dock, and VTuber Studio UI changes must go there, not directly into
`app/video_editor_window.py`. It now exposes an `Avatar Target` selector for
configured `VRM / VSeeFace Bridge` targets and Live2D actor clips. VRM targets
show bridge state, capture state, current Performance Source, and pose-stream
readiness. Live2D direct key baking remains Live2D-only.

VRM avatar selection is productized through Media Pool import. `.vrm` files are
classified as `VRM Avatar` / `Avatar Target` assets with a `VRM` badge. A
double-click selects the shared `VRM / VSeeFace Bridge` target and opens
`VTuberBroadcastStudioWindow`; right-click exposes the same target/studio
actions explicitly. Selection persists `vseeface_bridge.avatar_vrm` and
`vtuber_studio.avatar_target_id = "vrm:vseeface_bridge"`. The VRM file itself
is never a Program Output background.

Registered action ids for this shared surface:

```text
vtuber.studio.open
vtuber.avatar_target.summary
vtuber.avatar_target.select
broadcast.live_target.summary
broadcast.live_target.select
broadcast.platform_evidence_checklist
broadcast.platform_evidence.preflight
broadcast.platform_evidence.register
vtuber.vrm.bridge_status
vtuber.vrm.pose_stream_preview
```

Live Target stream keys are session-only. Project settings store platform,
server URL, bitrate, and local MP4 recording path, but must not store raw stream
keys. The local file target is shown as `Local MP4`; the persisted compatible
id remains `record_file`.

The runtime output path is now:

```text
ProjectPlayer.gpu_frame_ready RGB frame
-> VTuber Studio Live Target start/stop state
-> BroadcastOutputSession.write_frame(...)
-> FFmpeg stdin rgb24
-> MP4 recording or RTMP/RTMPS target
```

Live audio can currently be attached as generated silence, a Windows DirectShow
device name, a looped audio file, or the TigerCapture project audio bus
materialized to a temporary WAV before FFmpeg starts.

TikTok/Instagram-style targets request a vertical 1080x1920 output canvas.
Discord/video-call output remains manual Program Output window sharing until a
real virtual-camera backend is implemented; `broadcast_virtual_camera` records
that plan and keeps driver installation user-approved.

Stream-key storage has two layers:

- session-only key entry in VTuber Studio;
- optional OS credential-store helper via `broadcast_secrets` when a keyring
  backend is available.

Raw stream keys must still not be written to `.tgp` project settings.

## Active Implementation Area

- `app/vtuber/broadcast_studio_layout.py`
- `app/vtuber/internal_vrm_fallback.py`
- `app/vtuber/performance_source.py`
- `app/vtuber/vseeface_bridge.py`
- `app/actions/editor_adapter.py`
- `app/actions/registry.py`
- `app/vtuber/openseeface_video_source.py`
- `app/vtuber/openseeface_motion.py`
- `tools/install_vseeface_sidecar.py`
- `tools/render_vtuber_broadcast_studio_ui.py`
- `tools/render_internal_vrm_fallback_program_output.py`
- `docs/SPEC_VSEEFACE_BRIDGE.md`
- `docs/SPEC_BROADCAST_SCENE.md`

## Next Work

1. Harden the standalone bridge/status/capture diagnostics.
2. Keep Performance Source out of Program Output in every preview/export path.
3. Improve avatar framing controls for broadcast use.
4. Verify camera/video input health and black-frame fallback behavior.
5. Expand the thin editor integration only through the shared VTuber Studio
   entry point and registered actions.

## Do Not Mix With Live2D

Live2D can consume the same Performance Source concept, but Live2D renderer
quality, Cubism parameter aliases, and Live2D editor UX are a separate tranche.
Do not file generic VTuber broadcast bridge decisions under the Live2D context
unless the change is specifically about Live2D.
