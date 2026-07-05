# VTuber Trump Source Mapping Context

This note is a compact handoff for the review automation and multi-monitor
capture work. It records the intended VTuber Studio story in a form that future
threads can read without reconstructing the older discussion.

## User Intent

- AR/PBR review evidence should use a bicycle model.
- VTuber Studio review evidence should show a Trump face video driving an avatar
  mapping workflow.
- The user said `VML`; the current codebase and docs use `VMC/OSC`, `VRM`, and
  `VSeeFace`. Treat the intended meaning as:

```text
Trump video Performance Source
-> OpenSeeFace tracking rows
-> VMC/OSC pose/morph stream
-> Milica VRM / VSeeFace Bridge Avatar Target
-> VTuber Studio Program Output
```

If the user later confirms a different `VML` meaning, update this document
before implementation.

## Existing History

The main historical documents are:

- `docs/WORKFLOW_VTUBER_LIVE2D_CONTEXT.md`
  - records why the Trump/source-mapping conversation created the shared
    `Performance Source` concept;
  - states that a Trump/person video is tracking input only;
  - records that `Avatar Source` was rejected in favor of `Performance Source`.
- `docs/WORKFLOW_VTUBER_BROADCAST_CONTEXT.md`
  - current VTuber broadcast bridge context;
  - says the shared `VTuberBroadcastStudioWindow` is the canonical surface;
  - says not to create separate `VRM Studio` or `Live2D Studio` windows;
  - records the 2026-07-01 VSeeFace black-frame/degraded capture result and the
    internal VRM fallback path.
- `docs/SPEC_VTUBER_STUDIO_BROADCAST.md`
  - stable product contract for Program Output, Source Tracking, Avatar Mapping,
    Avatar Target, Performance Source, and Live Target.
- `docs/SPEC_VSEEFACE_BRIDGE.md`
  - formal bridge contract;
  - VSeeFace is external sidecar, not embedded;
  - includes the Trump source-framing proof commands and Milica VRM examples.
- `docs/SPEC_BROADCAST_SCENE.md`
  - states that Performance Source must not leak into Program Output.

## Existing Assets And Proof Files

Found local evidence paths:

```text
debugCapture/trump_face_source.mp4
debugCapture/openseeface_trump_to_vseeface_39540_data.csv
debugCapture/milica_vrm_trump_actual_mapping_preview.png
debugCapture/milica_vrm_trump_actual_mapping_preview.json
debugCapture/milica_vrm_source_framing_bust_up_head_desk_occluded.png
debugCapture/milica_vrm_source_framing_bust_up_head_desk_occluded.json
debugCapture/internal_vrm_fallback_program_output.png
debugCapture/vtuber_broadcast_studio_ui_trump.png
debugCapture/vtuber_assets/booth_milica/Milica1.3free/Milica_v1.3.vrm
```

The current search did not find a bicycle model asset. Existing AR/PBR debug
evidence includes motorcycle outputs, but the review scenario should not
silently substitute motorcycle for bicycle. If a bicycle model is missing, mark
the AR/PBR review slot as asset-blocked or import a real bicycle asset first.

## Correct VTuber Studio Story

The VTuber Studio page should not show the Trump video as the final output.
It should show four distinct concepts:

```text
Performance Source / Source Tracking
  Trump face video frame with face box, subject box, confidence, and frame time.

Avatar Target
  Milica VRM selected as `VRM / VSeeFace Bridge`.

Avatar Mapping
  Pose, mouth, blink, head rotation, bust-up framing, desk/occlusion line, and
  user offset controls derived from the Trump Performance Source.

Program Output
  The actual composited broadcast output. It may use internal VRM fallback if
  VSeeFace capture is black or unavailable, but it must not use the raw Trump
  source frame as the background.
```

This makes the review visually honest: the source video is visible where it is
supposed to be visible, and the final output shows the avatar result.

## Recommended Multi-Monitor Placement

Do not cram VTuber Studio into the same small cell as Live2D, MMD, and AR/PBR
if the goal is to explain the mapping. Use a dedicated VTuber mapping variant.

### Variant A: General Actor/3D Production

```text
left monitor:
  Live2D editor / actor view
  AR/PBR bicycle model preview
  MMD actor editor
  Actor Library or asset support strip

center monitor:
  main Viewer
  full-width Timeline
  AI command dock

right monitor:
  Node Graph
  Sound Editor
  Mixer / scopes
```

### Variant B: VTuber Broadcast Mapping

```text
left monitor:
  VTuber Studio, large
    Program Output
    Source Tracking with Trump frame
    Avatar Mapping with Milica VRM
    Studio Controls

center monitor:
  main editor Viewer
  Timeline with Performance Source track and avatar/output lane
  AI command dock

right monitor:
  Node Graph or Workbench automation view
  Sound Editor / levels for broadcast audio
  VSeeFace bridge diagnostics or Live Target status
```

Use Variant B when the page title or scenario is about VTuber Studio, VSeeFace,
VRM, VMC, Trump source mapping, Program Output, or Live Target.

## Implementation Notes

- `VTuberBroadcastStudioWindow` lives in `app/video_editor_popouts.py`.
- Do not add a separate `VRM Studio` window.
- Do not add a separate `Live2D Studio` window.
- Use registered actions where possible:

```text
vtuber.studio.open
vtuber.avatar_target.summary
vtuber.avatar_target.select
vtuber.performance_source.summary
vtuber.performance_source.mark_media
vtuber.performance_source.add_clip
vtuber.program_output_contract
vtuber.vrm.bridge_status
vtuber.vrm.pose_stream_preview
broadcast.live_target.summary
broadcast.live_target.select
```

- Review-only window capture actions may open/stage the VTuber Studio, but this
  should stay separate from the main Python Action registry unless the action is
  a real user-facing editor command.
- GPU/video/VRM surfaces should be shown before capture. Do not rely on hidden
  widget grabs for these surfaces.

## Useful Proof Commands

Plan-only source framing:

```powershell
.\.venv\Scripts\python.exe tools\vtuber_source_framing_plan.py --video debugCapture\trump_face_source.mp4 --preset bust_up --slots neutral,head,mouth --out debugCapture\vtuber_source_framing_plan_trump.json
```

Milica VRM with Trump OpenSeeFace motion:

```powershell
.\.venv\Scripts\python.exe tools\render_milica_vrm_trump_mapping.py --out debugCapture\milica_vrm_trump_actual_mapping_preview.png --json-out debugCapture\milica_vrm_trump_actual_mapping_preview.json
```

VTuber Studio UI proof:

```powershell
.\.venv\Scripts\python.exe tools\render_vtuber_broadcast_studio_ui.py --out debugCapture\vtuber_broadcast_studio_ui_trump.png
```

Internal VRM fallback Program Output proof:

```powershell
.\.venv\Scripts\python.exe tools\render_internal_vrm_fallback_program_output.py --capture-report debugCapture\vseeface_post_install_with_video_report.json --out debugCapture\internal_vrm_fallback_program_output.png
```

## Guardrails

- Do not show fake VTuber UI evidence in catalog/review pages.
- Do not use an AI-generated avatar mapping image as if it came from the editor.
- Do not show the Trump Performance Source as Program Output.
- Do not claim VSeeFace capture is working if the actual capture backend is
  black/degraded; show internal VRM fallback honestly.
- Do not substitute motorcycle for the requested AR/PBR bicycle model.
