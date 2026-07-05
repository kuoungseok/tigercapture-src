# VTuber / Live2D Work Context

This note only records why Live2D became a side branch of the VTuber work. The
current non-Live2D VTuber broadcast bridge context lives in
`docs/WORKFLOW_VTUBER_BROADCAST_CONTEXT.md`.

## Why Live2D Work Started

The Live2D work did not start from the AR/PBR road/FBX/Marmoset renderer task.
It started from the VTuber broadcast pipeline discussion:

1. The user wanted a VSeeFace-like broadcast workflow:
   - import/use a VRM or avatar model
   - drive it from camera or face video tracking
   - compose the animated avatar into a broadcast/program output
2. VSeeFace itself should remain external or bridged, not embedded as a merged
   internal renderer.
3. Before building the VSeeFace bridge, the project needed OBS-like internal
   scene concepts:
   - Program Output
   - Source Tracking
   - Avatar Mapping
   - Broadcast Studio layout
4. The user clarified that a face/person video such as the Trump test clip must
   not appear directly in Program Output. It is tracking input only.
5. The term `Avatar Source` was rejected and replaced with `Performance Source`.
6. Performance Source then became the shared tracking input concept for:
   - VRM / VSeeFace-style avatars
   - Live2D actors
   - later Live2D or other avatar systems

So the direct reason for the Live2D work is:

> Apply the same input-only Performance Source tracking contract to Live2D, so
> Live2D actors can be driven by camera/video face tracking without leaking that
> source video into Program Output.

## Current Live2D Scope

Implemented direction:

- Performance Source is input-only tracking media.
- Program Output must use capture/media/chroma background rules, not the
  Performance Source clip itself.
- Live2D can consume the active Performance Source at the current timeline time.
- Subject framing is normalized as:
  - `face_only`
  - `upper_body`
  - `full_body`
  - `unknown`
- Face-only tracking should limit body translation/scale.
- Upper-body tracking should damp body movement.
- Full-body tracking may allow wider movement.
- Live2D editor and actor-lane context menu expose `Performance Source Mapping`.
- Main preview and Preview Popout should both show the mapped Live2D result.

## Return Path After Live2D

When this Live2D tranche is done, return to the VTuber broadcast pipeline, not
the AR/PBR renderer.

Next VTuber work should be:

1. Live2D production tuning:
   - parameter ranges
   - smoothing
   - blink/eye/mouth aliases
   - model-specific fallback behavior
2. Real camera/capture input UX:
   - camera registration
   - media-pool or timeline video as a camera substitute
   - reconnect/black-frame diagnostics
3. Broadcast Studio output flow:
   - Program Output
   - Source Tracking monitor
   - Avatar Mapping monitor
   - controls for avatar framing
4. VSeeFace bridge work:
   - launch/config status
   - capture source verification
   - bridge diagnostics
   - keep VSeeFace external, not merged into the app
5. Recording/stream output controls once the scene pipeline is stable.

## Do Not Mix With AR/PBR

AR/PBR is a separate prior work stream:

- FBX/GLB/VRM import
- PBR/HDR IBL rendering
- depth map and road-plane placement
- camera solve
- shadow/reflection catchers
- Marmoset-like renderer quality

Do not assume the next task after Live2D is AR/PBR unless the user explicitly
returns to the 3D road-compositing renderer.
