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
`app/vtuber/internal_vrm_fallback.py` can reuse generated descriptor/motion
artifacts when present, but its default path must remain usable after
`debugCapture` is cleaned by importing the durable VRM and using internal idle
motion. Remaining implementation debt is first-frame performance, not durable
asset discovery.

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

The internal fallback frame path is `app/vtuber/internal_vrm_fallback.py`. It
must render a transparent avatar frame without VSeeFace, OBS, virtual camera, or
Qt. If temporary descriptor or motion artifacts are needed, they must be
generated from durable inputs instead of assumed to exist in `debugCapture`. The
standalone Program Output proof tool is:

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
device name, or a looped audio file. TigerCapture's full internal project-audio
bus is not mixed into live output yet.

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
