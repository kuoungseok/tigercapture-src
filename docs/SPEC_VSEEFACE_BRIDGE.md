# VSeeFace Bridge Contract

VSeeFace is not a TigerCapture module and should not be merged into the editor.
It remains an external sidecar application. TigerCapture only owns a bridge
contract for process planning, source capture metadata, VRM compatibility
preflight, and BroadcastScene integration.

## Agent Read First

2026-07-07 default: assume VSeeFace is not installed or not usable unless the
user explicitly asks to work on the external sidecar. The VSeeFace bridge is an
optional integration path, not the required VTuber Program Output engine.

When VSeeFace is missing, black, degraded, unregistered, or not launched,
TigerCapture must continue through the internal VRM fallback path whenever a
durable VRM avatar is available. Do not block normal project open, preview,
export, or VTuber Studio Program Output on VSeeFace.

Durable locations:

```text
external/tools/vseeface
external/assets/vtuber
```

`debugCapture` is disposable scratch space for generated reports, screenshots,
probe outputs, and temporary proof artifacts. Any command in this spec that
writes to `debugCapture` must be understood as regenerable diagnostics, not as a
durable dependency.

## Non-Goals

- Do not embed VSeeFace into TigerCapture.
- Do not link against or modify VSeeFace internals.
- Do not require VSeeFace for normal project open, preview, or export.
- Do not store VSeeFace runtime state as mandatory project data.
- Do not treat this bridge as a Blender/Marmoset-style renderer.

## Code Interface

The UI-neutral bridge contract lives in:

```python
from app.vtuber.vseeface_bridge import (
    VSeeFaceBridgeConfig,
    build_vseeface_broadcast_scene,
    build_vseeface_broadcast_source,
    build_vseeface_bridge_status,
    build_vseeface_launch_plan,
    default_vseeface_bridge_config,
    vseeface_bridge_contract,
    vseeface_bridge_preflight,
)
from app.vtuber.vrm_profile import inspect_vrm_profile
from app.vtuber.openseeface_motion import load_openseeface_motion_csv
from app.vtuber.vrm_pose_driver import build_vrm_pose_frames
```

The bridge schema is:

```text
tigerstudio.vtuber.vseeface_bridge.v1
```

The integration mode is always:

```text
external_sidecar
```

## Bridge Config

```json
{
  "schema": "tigerstudio.vtuber.vseeface_bridge.v1",
  "integration_mode": "external_sidecar",
  "vseeface_exe": "E:/ClaudeCodeApp/GifCam/external/tools/vseeface/VSeeFace/VSeeFace.exe",
  "avatar_vrm": "E:/ClaudeCodeApp/GifCam/external/assets/vtuber/booth_milica/Milica1.3free/Milica_v1.3.vrm",
  "auto_launch": true,
  "arguments": [],
  "capture": {
    "method": "window_capture",
    "source_id": "vseeface",
    "window_title_hint": "VSeeFace",
    "virtual_camera_name": "VSeeFaceCamera",
    "spout_sender_name": "VSeeFace",
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "framing_preset": "bust_up",
    "camera": {
      "preset": "bust_up",
      "target": "head_and_shoulders",
      "composition": "head_to_mid_chest",
      "fov_deg": 20,
      "camera_distance_m": 1.45,
      "camera_height_m": 1.45,
      "pitch_deg": -6,
      "eye_line_y": 0.36,
      "headroom": 0.06,
      "lower_frame": "mid_chest",
      "broadcast_zoom": 1.65,
      "broadcast_offset_y": -0.18
    },
    "chroma_key": {"enabled": false}
  },
  "tracking": {
    "enabled": false,
    "protocol": "vmc_osc",
    "target_host": "127.0.0.1",
    "receive_port": 39539,
    "send_port": 39540
  },
  "input": {
    "mode": "webcam",
    "source_kind": "camera_device",
    "source_id": "camera:default",
    "camera_device_id": "",
    "camera_device_name": "Default camera",
    "camera_index": null,
    "video_path": "",
    "media_pool_id": "",
    "track_id": null,
    "clip_id": null,
    "source_in_ms": 0,
    "source_out_ms": 0,
    "timeline_in_ms": 0,
    "timeline_out_ms": 0,
    "openseeface_host": "127.0.0.1",
    "openseeface_port": 39540,
    "width": 640,
    "height": 360,
    "fps": 24,
    "model": 3,
    "detection_threshold": 0.35,
    "try_hard": false,
    "crop": null,
    "realtime": true
  }
}
```

## Dependency Install / Connect UI

VSeeFace is an external dependency. The bridge UI must show a dependency/setup
card before capture probing:

- `view.dependency`: compact UI state for installed/missing/zip-available
  VSeeFace.
- `setup_flow.steps[0].id == "vseeface_install"`: first wizard row.
- `connect_installed_vseeface_sidecar`: use an already installed/default
  sidecar `VSeeFace.exe`.
- `install_vseeface_sidecar`: explicit install path from a local `VSeeFace*.zip`
  or user-approved download URL.

The default sidecar install root is `external/tools/vseeface`. Default local
avatar samples live under `external/assets/vtuber`. `debugCapture` is reserved
for reports, screenshots, probes, and other generated diagnostics.

Registered actions:

```text
vtuber.vseeface_install_plan
vtuber.vseeface_install_execution_gate
vtuber.vseeface_install_executor_dry_run
vtuber.vseeface_install_execute
vtuber.vseeface_connect_installed_sidecar
```

The installer tool is:

```text
tools/install_vseeface_sidecar.py
```

It never runs automatically. The UI must ask for user confirmation before
calling `vtuber.vseeface_install_execute`. After install, call
`vtuber.vseeface_connect_installed_sidecar` so project settings store the
resolved `vseeface_exe` path.

## Start And Probe Workflow

Once VSeeFace is installed, connected, and a VRM0 avatar is configured, the UI
can expose a launch/probe action set:

```text
vtuber.vseeface_start_probe_plan
vtuber.vseeface_start_probe_execution_gate
vtuber.vseeface_start_probe_executor_dry_run
vtuber.vseeface_start_probe_execute
```

The plan is based on the `start_vseeface_and_probe` bridge action. It launches
the external sidecar only through `tools/verify_vseeface_post_install.py
--launch-vseeface`, then runs `tools/vseeface_live_check.py` and capture backend
preflight. It must not run on project open or status refresh. The UI must pass
`confirm=true` to `vtuber.vseeface_start_probe_execute` before any subprocess is
started.

## Tracking Input Sources

VSeeFaceCamera registration is the capture-output setup step. It should not be
confused with the face-tracking input. The tracking input can be:

- `camera_device`: a real webcam/capture device.
- `video_file`: an explicit video file.
- `media_pool_video`: a video item from the Media Pool.
- `timeline_video_clip`: a video clip already placed on a timeline track.

UI integration should use:

```python
from app.vtuber.vseeface_bridge import build_vseeface_input_source_options

input_sources = build_vseeface_input_source_options(
    project_snapshot=editor_snapshot,
    camera_devices=[{"id": "webcam0", "name": "USB Camera", "index": 0}],
    selected=config.input_source,
)
```

The returned payload is UI-ready:

```json
{
  "schema": "tigerstudio.vtuber.vseeface_bridge.input_sources.v1",
  "action": "select_tracking_input_source",
  "selected_id": "timeline:2:5",
  "selected": {
    "id": "timeline:2:5",
    "kind": "timeline_video_clip",
    "mode": "openseeface_video",
    "label": "V1 Clip 1 - face.mov",
    "input": {
      "mode": "openseeface_video",
      "source_kind": "timeline_video_clip",
      "source_id": "timeline:2:5",
      "video_path": "C:/media/face.mov",
      "track_id": 2,
      "clip_id": 5,
      "timeline_in_ms": 0
    },
    "status": "ready",
    "tone": "ok",
    "actions": [],
    "diagnostics": {
      "status": "ready",
      "ready": true,
      "errors": [],
      "warnings": [],
      "recommendations": []
    }
  },
  "options": [],
  "diagnostics": {
    "selected_status": "ready",
    "selected_tone": "ok",
    "ready_count": 1,
    "needs_probe_count": 0,
    "unavailable_count": 0,
    "has_reconnectable_camera": false
  }
}
```

When the user selects an option, save the option's `input` object back into the
bridge config. The bridge will then feed that video path to OpenSeeFace instead
of using a live webcam. The selection action is declarative and must not launch
VSeeFace, FFmpeg, or registration tools by itself.

Status reports also include the choices:

```python
status = build_vseeface_bridge_status(
    config,
    capture_diagnostics=probe_report,
    project_snapshot=editor_snapshot,
    camera_devices=camera_devices,
)
```

Normal UI should read `status["input_sources"]` for the picker and
`status["view"]["input_source"]` for the compact card. Use card `id` values
instead of fixed card indexes.

Tracking input health is separate from VSeeFace output-capture health. Pass
camera or clip probe results through `input_diagnostics`, not
`capture_diagnostics`:

```python
status = build_vseeface_bridge_status(
    config,
    input_diagnostics={
        "inputs": {
            "camera:webcam0": {
                "status": "disconnected",
                "errors": ["camera_unavailable"],
                "recommendations": ["reconnect_usb_camera"]
            }
        }
    },
)
```

Each option should expose a compact `status`, `tone`, `actions`, and
`diagnostics` object. Supported input statuses are `ready`, `not_probed`,
`unavailable`, `black_frame`, and `missing`. A failed camera option should offer
`reconnect_tracking_input_source`; a missing media/timeline video should offer
`select_tracking_input_source`. This lets the main UI show a normal picker and
status badge without exposing raw debug JSON.

Main-editor action integration:

```python
registry.execute(
    "vtuber.vseeface_bridge_status",
    {
        "camera_devices": [{"id": "webcam0", "name": "USB Camera", "index": 0}],
        "capture_diagnostics": probe_report,
        "width": 1920,
        "height": 1080,
        "fps": 30
    },
)
```

This is the preferred UI entry point. It returns:

- `status`: the full bridge report.
- `view`: the compact no-debug ViewModel for cards/buttons.
- `input_sources`: the picker payload for real cameras, Media Pool videos, and
  timeline video clips.
- `setup_flow`: ordered setup steps for a wizard-style UI.

`status["setup_flow"]` is ordered and machine-readable:

```json
{
  "schema": "tigerstudio.vtuber.vseeface_bridge.setup_flow.v1",
  "state": "needs_probe",
  "ready": false,
  "current_step_id": "capture_backend",
  "completed_steps": 3,
  "total_steps": 5,
  "progress": 0.6,
  "requires_admin": false,
  "steps": [
    {"id": "vseeface_exe", "title": "VSeeFace executable", "state": "done"},
    {"id": "vrm0_avatar", "title": "VRM0 avatar", "state": "done"},
    {"id": "tracking_input", "title": "Tracking input", "state": "done"},
    {"id": "capture_backend", "title": "Capture backend", "state": "current"},
    {"id": "broadcast_scene", "title": "Broadcast scene", "state": "pending"}
  ]
}
```

`view["setup_flow"]` is the no-debug display version with the same step ids,
current title/text, progress, and display actions. The intended order is:

1. VSeeFace executable
2. VRM0 avatar
3. Tracking input
4. Capture backend
5. Broadcast scene

To fetch only the input picker:

```python
registry.execute(
    "vtuber.vseeface_input_sources",
    {"camera_devices": [{"id": "webcam0", "name": "USB Camera", "index": 0}]},
)
```

This returns the same `input_sources` picker payload using the current project
snapshot, including Media Pool videos and timeline video clips.

To persist the sidecar setup:

```python
registry.execute("vtuber.vseeface_select_exe", {"path": "E:/VSeeFace/VSeeFace.exe"})
registry.execute("vtuber.vseeface_select_vrm0_avatar", {"path": "E:/Avatars/Milica.vrm"})
registry.execute(
    "vtuber.vseeface_select_capture_backend",
    {"method": "virtual_camera", "virtual_camera_name": "VSeeFaceCamera"},
)
registry.execute("vtuber.vseeface_select_framing", {"framing_preset": "bust_up"})
```

These actions write only `project_settings["vseeface_bridge"]["vseeface_exe"]`
`project_settings["vseeface_bridge"]["avatar_vrm"]`, and
`project_settings["vseeface_bridge"]["capture"]`. The framing action updates the
capture `framing_preset` and the derived camera guidance. The VRM action validates that
the file is VSeeFace-compatible VRM0 before saving. None of these actions launch
VSeeFace.

To persist a selected source:

```python
registry.execute(
    "vtuber.vseeface_select_input_source",
    {"source_id": "timeline:2:5"},
)
```

The action writes only:

```json
{
  "project_settings": {
    "vseeface_bridge": {
      "input": {
        "mode": "openseeface_video",
        "source_kind": "timeline_video_clip",
        "source_id": "timeline:2:5",
        "video_path": "C:/media/face.mov",
        "track_id": 2,
        "clip_id": 5
      }
    }
  }
}
```

Dry-run is supported and reports the normalized input that would be saved. The
action does not launch VSeeFace, start OpenSeeFace, touch registration, or run
FFmpeg.

Display actions in `view["primary_action"]`, `view["secondary_actions"]`, and
`view["setup_flow"]["steps"][].action` may include `registry_action`, for
example:

```json
{
  "id": "select_vseeface_exe",
  "label": "Select VSeeFace.exe",
  "registry_action": "vtuber.vseeface_select_exe",
  "form": {
    "submit_action": "vtuber.vseeface_select_exe",
    "params": [
      {
        "name": "path",
        "label": "VSeeFace.exe",
        "kind": "file",
        "required": true,
        "must_exist": true,
        "file_filter": "VSeeFace.exe (VSeeFace.exe);;Windows executable (*.exe)"
      }
    ]
  }
}
```

The UI should call the registry action after collecting the required file path
or source id from the user.

Known form controls:

- `file_picker`: use the first `form.params[]` item with `kind=file`.
- `capture_backend_picker`: submit `method` as one of `window_capture`,
  `virtual_camera`, `spout2`, or `none`; optional text fields configure backend
  labels such as `virtual_camera_name`.
- `framing_picker`: submit `framing_preset` as one of `bust_up`, `half_body`, or
  `full_body`.
- `camera_or_project_clip_picker`: render `status.input_sources.options` and
  submit the selected option id as `source_id`.

To preview the current bridge action without executing external tools:

```python
registry.execute(
    "vtuber.vseeface_action_preview",
    {"action_id": "register_vseeface_camera", "allow_admin": false},
)
```

This wraps the same declarative action plan used by the CLI and keeps admin
steps blocked unless the UI explicitly passes `allow_admin=true` for preview.

To preview the sidecar settings that would be applied to VSeeFace:

```python
registry.execute(
    "vtuber.vseeface_sidecar_settings_preview",
    {"settings_path": "E:/VSeeFace/VSeeFace_Data/StreamingAssets/settings.ini"},
)
```

This action is read-only. It does not create or edit `settings.ini`, launch
VSeeFace, run OpenSeeFace, register a virtual camera, or touch FFmpeg. It only
returns the normalized values TigerCapture would use for the external sidecar,
including the VRM0 avatar path, OpenSeeFace host/port, and whether the
VSeeFace virtual camera should remain enabled for the selected capture backend.

The returned payload includes:

```json
{
  "schema": "tigerstudio.actions.vseeface_sidecar_settings_preview.v1",
  "changed": false,
  "preview": {
    "schema": "tigerstudio.vtuber.vseeface_bridge.sidecar_settings_preview.v1",
    "read_only": true,
    "would_write": false,
    "settings_path": "E:/VSeeFace/VSeeFace_Data/StreamingAssets/settings.ini",
    "section": "OpenSeeDemo",
    "values": {
      "AvatarFile": "E:/Avatars/Milica.vrm",
      "Host": "127.0.0.1",
      "Port": "39540",
      "KeepVirtualCamEnabled": "1"
    }
  }
}
```

Normal UI should show `status["view"]["sidecar_settings"]` instead of raw JSON.
It exposes compact fields such as `avatar_file`, `openseeface_endpoint`,
`virtual_camera_kept_enabled`, and `tone`. If `ok=false`, keep the bridge in a
setup state and ask the user to choose a valid VRM0 avatar first.
The compact card list also includes a final `sidecar` card with a short label
such as `OpenSeeFace 127.0.0.1:39540`; render that card like the other setup,
capture, scene, and input cards.
When the preview is valid, `status["view"]["secondary_actions"]` includes
`apply_sidecar_settings`. Its `registry_action` is
`vtuber.vseeface_sidecar_apply_plan`, so the UI can show one Apply Settings
button without exposing raw JSON or shell commands.

To prepare the explicit settings write step without running it:

```python
registry.execute(
    "vtuber.vseeface_sidecar_apply_plan",
    {
        "settings_path": "E:/VSeeFace/VSeeFace_Data/StreamingAssets/settings.ini",
        "out_path": "debugCapture/vseeface_sidecar_config_report.json"
    },
)
```

This returns a non-auto-run plan:

```json
{
  "schema": "tigerstudio.actions.vseeface_sidecar_apply_plan.v1",
  "changed": false,
  "plan": {
    "schema": "tigerstudio.vtuber.vseeface_bridge.sidecar_apply_plan.v1",
    "auto_run": false,
    "requires_user_initiation": true,
    "requires_admin": false,
    "preview_only": true,
    "would_write_when_executed": true,
    "steps": [
      {
        "id": "write_sidecar_settings",
        "kind": "tool",
        "program": ".\\.venv\\Scripts\\python.exe",
        "args": ["tools\\configure_vseeface_sidecar.py", "..."],
        "auto_run": false
      }
    ]
  }
}
```

The UI may present this as an Apply Settings button, but the action itself must
not execute the tool step. For non-virtual-camera capture backends, the plan
passes `--disable-virtual-camera` so `KeepVirtualCamEnabled` does not drift from
the preview. Action preview should surface
`file_write_requires_user_confirmation` for this plan because it writes the
external VSeeFace `settings.ini` only after explicit execution.

Before handing that plan to any executor, call the read-only gate:

```python
registry.execute(
    "vtuber.vseeface_sidecar_execution_gate",
    {"settings_path": "E:/VSeeFace/settings.ini", "confirm": false},
)
```

With `confirm=false`, the gate returns `execute_allowed=false` and marks the
tool step as `requires_user_confirmation`. With `confirm=true`, it may return
`execute_allowed=true`, but it still does not execute the tool or write files.
It only verifies that the plan uses the local venv Python and one of the
whitelisted VSeeFace bridge tools.

The same check is available as a CLI for diagnostics:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_execution_gate.py --plan debugCapture\vseeface_sidecar_plan.json --out debugCapture\vseeface_execution_gate.json
```

Adding `--confirm` changes only the gate result; the tool still does not execute
subprocesses or write VSeeFace settings.

The actual executor wrapper is a separate tool and defaults to dry-run:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_plan_executor.py --plan debugCapture\vseeface_sidecar_plan.json --confirm --out debugCapture\vseeface_executor_dry_run.json
```

The executor runs no subprocesses unless both `--execute` and `--confirm` are
present and the execution gate allows every tool step. UI code should never call
subprocesses directly; it should call the gate first, then hand the same plan to
this executor only after explicit user approval.

For in-app UI, prefer the read-only dry-run registry action:

```python
registry.execute(
    "vtuber.vseeface_sidecar_executor_dry_run",
    {"settings_path": "E:/VSeeFace/settings.ini", "confirm": true},
)
```

This action has no `execute` parameter and always calls the executor with
`execute=false`, so it can be used to populate confirmation dialogs safely.

For the full sidecar settings UI, prefer the bundled workflow action:

```python
registry.execute(
    "vtuber.vseeface_sidecar_workflow",
    {"settings_path": "E:/VSeeFace/settings.ini", "confirm": false},
)
```

It returns `settings_preview`, `apply_plan`, `execution_gate`,
`executor_dry_run`, and a compact `view` object. With `confirm=false`, the view
state is `confirmation_required`. With `confirm=true`, it may become
`ready_to_execute`, but it still does not write files or run tools. The UI
should render `workflow.view` and use its action list instead of assembling the
individual calls manually.

`workflow.view` includes:

- `progress`: 0.0 to 1.0 for a compact progress bar.
- `steps`: fixed UI steps for settings preview, apply plan, execution gate, and
  executor dry run.
- `next_action`: the recommended registry action for the current state.
- `actions`: all read-only support actions for an advanced/details popover.

The same workflow can be written from the command line:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_sidecar_workflow.py --config debugCapture\vseeface_bridge_config.json --settings E:\VSeeFace\settings.ini --out debugCapture\vseeface_sidecar_workflow.json
```

`--confirm` changes the workflow state only; this report tool is read-only and
never writes VSeeFace settings.

When `vseeface_bridge.input.mode` is `openseeface_video`, probe/verification
plans must pass the selected project video into the verification tool:

```json
{
  "id": "post_install_verify",
  "kind": "tool",
  "program": ".\\.venv\\Scripts\\python.exe",
  "args": [
    "tools\\verify_vseeface_post_install.py",
    "--video",
    "C:/media/face.mov",
    "--port",
    "39540",
    "--fps",
    "24.0",
    "--crop",
    "0.32,0.05,0.36,0.75",
    "--out",
    "debugCapture\\vseeface_post_install_report.json"
  ],
  "auto_run": false
}
```

If the selected input is a live camera, the same verify step keeps
`--skip-video-send`. This preserves webcam workflows while allowing Media Pool
and timeline clips to drive OpenSeeFace during bridge verification.

## Capture Methods

Supported bridge method names:

- `window_capture`: capture the VSeeFace window, with chroma key if needed.
- `spout2`: future direct frame transport when available.
- `virtual_camera`: optional VSeeFaceCamera capture backend. If it is black,
  missing, or unregistered, Program Output should use `internal_vrm_fallback`
  instead of blocking the broadcast.
- `none`: configuration/preflight only.

The first implementation should use `window_capture`. Spout2 and virtual camera
remain optional backends behind the same source contract.

## Window Capture Diagnostics

The bridge must treat VSeeFace window capture as a probeable backend, not as a
guaranteed dependency. VSeeFace remains an external Unity/D3D application, and
some remote Windows sessions can show a black client area to Win32 capture APIs
even while the process is alive.

Diagnostic module:

```python
from app.vtuber.vseeface_capture_diagnostics import analyze_graphics_probe_report
```

Probe tool:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_graphics_probe.py --wait-seconds 8 --include-glcore
```

Local 2026-06-29 result on this workstation:

- Direct3D 11 variants launched and stayed alive, but `PrintWindow`/`mss`
  captured a black client area.
- Vulkan and GLCore produced a visible Unity error dialog, but the log reported
  `InitializeEngineGraphics failed`, so those are not usable capture backends.
- Temporarily disabling `GPUManagementPlugin.dll` did not fix the D3D11 black
  capture result.

Required behavior:

- If `analyze_graphics_probe_report()` returns `ok=false`, the broadcast bridge
  must not block project open/preview/export.
- The UI should mark `window_capture` unavailable for that sidecar session and
  suggest `spout2` or `virtual_camera`.
- Preview should retain a no-op/fallback source instead of replacing the scene
  with a black frame.

Backend preflight:

```python
from app.vtuber.vseeface_capture_diagnostics import inspect_capture_backends
```

CLI:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_capture_backend_preflight.py
```

Current local 2026-06-29 backend result:

```json
{
  "preferred_backend": "virtual_camera",
  "status": "needs_install",
  "reason": "vseeface_camera_bundle_present_but_not_registered",
  "next_action": "run_vseeface_camera_install_bat_as_admin"
}
```

Details:

- VSeeFace includes `NativeSpoutPlugin.dll`, so Spout2 sender support is present.
- No OBS Spout receiver plugin was found locally.
- VSeeFace includes `VSeeFaceCamera32bit.dll` and `VSeeFaceCamera64bit.dll`.
- Registry inspection did not find a registered `VSeeFaceCamera`/`Unity Capture`
  DirectShow device.
- Silent `regsvr32` registration did not complete in this remote session, so
  virtual-camera registration should be treated as an interactive/admin setup
  step, not an automated bridge startup step.

Virtual camera admin setup helper:

```powershell
.\.venv\Scripts\python.exe tools\register_vseeface_camera.py
```

This writes:

```text
debugCapture\register_vseeface_camera_admin.bat
```

The batch registers `VSeeFaceCamera32bit.dll` and `VSeeFaceCamera64bit.dll`
with `UnityCaptureName=VSeeFaceCamera`. Running it requires administrator/UAC
approval. The bridge must not run this silently on startup; it can offer it as
an explicit setup action and rerun `vseeface_capture_backend_preflight.py` after
the user approves installation.

After registration, verify capture with:

```powershell
.\.venv\Scripts\python.exe tools\probe_vseeface_virtual_camera.py
```

This scans local OpenCV/DirectShow camera indexes and writes a sample PNG for
the first non-black frame. Before `VSeeFaceCamera` is registered, this probe is
expected to report `no_nonblack_virtual_camera_frame`.

Full post-install verification:

```powershell
.\.venv\Scripts\python.exe tools\verify_vseeface_post_install.py --launch-vseeface
```

This is the intended one-command check after administrator registration. It
reruns capture backend preflight, rewrites the sidecar settings, optionally
launches VSeeFace, sends the sample face video through the bundled OpenSeeFace
facetracker, probes virtual camera frames, and writes one JSON report. If
`VSeeFaceCamera` is still not registered, it exits with
`blocked_registration_required` and does not launch VSeeFace.

## Broadcast Framing

The default camera framing is `bust_up`, because typical VTuber streams do not
show the full body during normal talking segments.

Supported framing presets:

- `bust_up`: head and shoulders, framed to mid-chest. This is the default.
- `half_body`: head to waist for reaction/gameplay scenes.
- `full_body`: head to toe, used for model checks or dancing, not normal talk.

Source-person visibility contract for AI/review automation:

- Rule id: `match_source_person_exposure_to_vrm_visibility`.
- `face_only` / `face_closeup` source may use `bust_up`, but evidence still
  must show head, neck, and shoulders; do not use a face-only VRM meta thumbnail
  as Program Output or Avatar Mapping proof.
- `upper_body` source must use at least `half_body` / head-to-waist VRM
  framing. If a caller requests `bust_up`, the source-framing plan upgrades it
  unless explicitly allowed to be narrower.
- `full_body` source must use `full_body` / head-to-toe VRM framing.
- `build_source_framing_plan(...)` exposes machine-readable `source_exposure`
  and `visibility_policy` fields so Claude/local AI/review sections can explain
  exactly why a VRM shot is bust-up, half-body, or full-body.

Default `bust_up` guidance for VSeeFace setup:

```json
{
  "target": "head_and_shoulders",
  "composition": "head_to_mid_chest",
  "fov_deg": 20,
  "camera_distance_m": 1.45,
  "camera_height_m": 1.45,
  "pitch_deg": -6,
  "eye_line_y": 0.36,
  "headroom": 0.06
}
```

These are bridge defaults and setup hints. VSeeFace remains the owner of its
own internal camera; TigerCapture records the intended composition so capture
and scene integration stay consistent.

## Source Video Framing

When the input source is a recorded face video, the bridge should mimic that
video's apparent camera distance and angle instead of always using a fixed
avatar camera. This is needed for normal seated VTuber shots where the source
camera shows the face, shoulders, and part of the arms rather than a full-body
performer.

Implementation modules:

```python
from app.vtuber.source_framing_plan import build_source_framing_plan
from app.vtuber.source_framing_control import apply_framing_user_offset, update_live_source_framing
from app.vtuber.source_subject import detect_subject_boxes_for_motion_frames
from app.vtuber.source_framing import solve_source_framing_sequence
```

Contract:

- `build_source_framing_plan(...)` returns
  `tigerstudio.vtuber.source_framing_plan.v1` without invoking the renderer.
- `detect_subject_boxes_for_motion_frames(...)` returns
  `tigerstudio.vtuber.source_subject.v1`.
- `solve_source_framing_sequence(...)` returns per-frame
  `tigerstudio.vtuber.source_framing.v1` camera guidance.
- `app.vtuber.source_framing.vrm_visibility_policy_for_source_exposure(...)`
  maps source exposure to the minimum VRM framing preset and records the
  selected preset in `visibility_policy`.
- The UI should consume only `framing.model_view`, `framing.track_rotation`,
  and user-facing preset names. Raw detector frames stay in diagnostics/QA.
- If OpenCV or the source video is unavailable, the detector falls back to an
  upper-body estimate from the OpenSeeFace face box.
- Preview should default to `subject_detect_scope=selected` so opening a model
  view is fast. Export or QA can use sequence detection when temporal parity is
  more important than startup latency.

Manual placement is a separate offset layer:

```json
{
  "user_offset": {
    "pan_x": 0.12,
    "pan_y": -0.08,
    "pan_z": 0.0,
    "zoom_delta": 0.0,
    "zoom_scale": 1.05,
    "camera_z_delta": 0.0,
    "lower_occlusion_y_delta": -0.03
  }
}
```

The UI must not overwrite automatic `framing.model_view`. It should store the
manual placement as `user_offset`, then render with `final_framing.model_view`.
This keeps re-analysis, preset changes, and reset-to-auto predictable.

Fast plan-only command:

```powershell
.\.venv\Scripts\python.exe tools\vtuber_source_framing_plan.py --video "C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\trump_oval_office_live_GnzWEo_HfE0.mp4" --preset auto --slots neutral,head,mouth --out debugCapture\vtuber_source_framing_plan_trump.json
```

Plan-only command with manual placement:

```powershell
.\.venv\Scripts\python.exe tools\vtuber_source_framing_plan.py --video "C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\trump_oval_office_live_GnzWEo_HfE0.mp4" --preset auto --slots head --user-pan-x 0.12 --user-pan-y -0.08 --user-zoom-scale 1.05 --user-lower-occlusion-y-delta -0.03 --out debugCapture\vtuber_source_framing_plan_trump_user_offset.json
```

Renderer-facing `model_view` example:

```json
{
  "auto_fit": false,
  "zoom": 6.64,
  "camera_z": 3.25,
  "pan_x": 0.11,
  "pan_y": -1.70,
  "pan_z": 0.0,
  "lower_occlusion_y": 0.68,
  "source_face_height": 0.261,
  "source_subject_height": 0.75
}
```

For `bust_up`, `lower_occlusion_y` is part of the contract. Camera framing
alone cannot reproduce a seated source video where a desk hides the body below
the chest; preview/export should apply a foreground/depth/desk mask from that Y
position or from a stronger source-video segmentation result. `half_body` and
`full_body` keep this value lower or disabled.

Local Trump-video proof command:

```powershell
.\.venv\Scripts\python.exe tools\render_milica_vrm_source_framing_preview.py --video "C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\trump_oval_office_live_GnzWEo_HfE0.mp4" --slot head --preset auto --render-size 1440 --out debugCapture\milica_vrm_source_framing_auto_selected_subject.png --json-out debugCapture\milica_vrm_source_framing_auto_selected_subject.json
```

Current local result on 2026-06-30:

```text
selected_indices=[0, 18, 31]
subject_source=grabcut_subject
head_subject_box=[176, 52, 294, 270]
zoom=6.64
pan_y=-1.70
lower_occlusion_y=0.68
tests=39 passed
```

## Live Camera Framing

Live camera input uses the same final composition contract as recorded video:

```text
camera frame tracking -> automatic framing -> live stabilization -> user_offset -> final_framing
```

Implementation:

```python
from app.vtuber.source_framing_control import update_live_source_framing
```

`update_live_source_framing(...)` returns
`tigerstudio.vtuber.source_framing_live.v1` with:

- `automatic`: stabilized camera framing for the current live frame.
- `user_offset`: manual placement delta.
- `final`: the renderer-facing `model_view` and `track_rotation`.
- `state`: pass this object into the next update.

Live controls:

- `smoothing`: retain previous framing to reduce jitter.
- `dead_zone_pan`, `dead_zone_zoom`, `dead_zone_occlusion`: ignore tiny changes.
- `min_update_interval_ms`: avoid per-frame UI churn.
- `lock_framing`: freeze automatic pan/zoom while still applying user offsets.

Recommended UI behavior:

- Drag avatar: edit `user_offset.pan_x` / `user_offset.pan_y`.
- Mouse wheel or pinch: edit `user_offset.zoom_scale`.
- Desk/foreground line handle: edit `user_offset.lower_occlusion_y_delta`.
- Reset button: clear `user_offset`, not the automatic analysis.
- Lock button: set live `lock_framing=true` when the user has composed the shot.

## Broadcast Source

`build_vseeface_broadcast_source(config)` returns a regular BroadcastScene
source:

```json
{
  "id": "vseeface",
  "type": "vseeface",
  "name": "VSeeFace Avatar",
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
  "settings": {
    "bridge_schema": "tigerstudio.vtuber.vseeface_bridge.v1",
    "integration_mode": "external_sidecar",
    "capture_method": "window_capture",
    "window_title_hint": "VSeeFace",
    "framing_preset": "bust_up",
    "camera": {
      "composition": "head_to_mid_chest",
      "lower_frame": "mid_chest"
    },
    "capture_ready": null,
    "capture_status": "not_probed",
    "capture_health": {
      "probed": false,
      "ready": null,
      "status": "not_probed",
      "ui": {
        "label": "Not probed",
        "severity": "info",
        "action": "run_capture_probe"
      },
      "fallback_behavior": "suppress_black_frame"
    },
    "suppress_black_frame": true
  }
}
```

The compositor should receive frames under the source id `vseeface`.
If the capture probe reports `virtual_camera_black_frame` or another known
blocked state, `capture_ready` must be `false` and `capture_status` must carry
that machine-readable state. The UI should show a small human status such as
`Not probed`, `Ready`, or `Black frame`, not a raw JSON/debug panel.

`suppress_black_frame=true` is part of the fallback contract. If a capture
backend returns an all-black VSeeFace frame, the BroadcastScene compositor skips
that source for the frame so the preview/export scene is not replaced by black.
When capture health is explicitly failed/black, `build_vseeface_broadcast_scene`
also adds an `internal_vrm_fallback` source of type `internal_vrm`. That source
is the Program Output fallback and does not require VSeeFace virtual-camera
frames.

For thin main-editor integration, use:

```python
from app.vtuber.vseeface_bridge import build_vseeface_broadcast_scene

scene = build_vseeface_broadcast_scene(config, capture_diagnostics=probe_report)
```

This returns a full BroadcastScene-compatible payload with a background source,
the VSeeFace source, optional internal VRM fallback source, audio channel
placeholders, and capture fallback metadata.

## VTuber Broadcast Studio UI

The studio UI separates broadcast output from avatar tracking input:

- `Program Output`: what would actually be recorded/streamed. It uses capture
  clips first, then normal video/image clips, then green chroma fallback. It
  composites the avatar over that background.
- `Source Tracking`: shows the active Performance Source frame and overlays
  face box, subject box, and confidence.
- `Avatar Mapping`: shows how Performance Source motion maps into avatar pose,
  framing, mouth, blink, and occlusion/desk-line controls.
- `Studio Controls`: avatar position, zoom, lock framing, and occlusion line.

Performance Source clips can be webcam/video driven and may change over time,
for example webcam from 0-10s, a face video from 10-20s, then another source
after 20s. The active source is selected by timeline time and drives tracking
only. It must not be used as Program Output background.

UI naming:

- user-facing label: `Performance Source` / `퍼포먼스 소스`
- compact badge: `PERF`
- internal schema/type: `vtuber_performance_source` or
  `performance_source_track`
- shared studio avatar selector: `Avatar Target`
- VRM target label: `VRM / VSeeFace Bridge`
- banned surface split: do not create separate `VRM Studio` or `Live2D Studio`
  windows for this workflow.

Use `app.vtuber.performance_source.program_output_contract(...)` and
`app.vtuber.broadcast_studio_layout.build_vtuber_broadcast_studio_layout(...)`
when building the Studio UI. The returned layout explicitly marks
`performance_source_direct_output=false`. It also exposes `avatar_target` so
VRM/VSeeFace and Live2D actor targets can share the same Program Output and
Live Target route without creating separate Studio windows.

Current main-UI integration contract:

- `app.vtuber.performance_source.performance_source_ui_contract()` is the
  stable handoff for the renewed editor UI.
- `vtuber.performance_source.summary` returns the same `ui_contract` payload so
  automation and UI code can read one source of truth.
- The shared `VTuberBroadcastStudioWindow` owns avatar-target selection for
  VRM/VSeeFace, Live2D, and future avatar types. Use
  `vtuber.studio.open`, `vtuber.avatar_target.summary`,
  `vtuber.avatar_target.select`, `vtuber.vrm.bridge_status`, and
  `vtuber.vrm.pose_stream_preview` for automation. VRM/VSeeFace targets use
  the pose-stream route, while `actor.live2d.apply_performance_source` remains
  Live2D-only direct key baking.
- Media Pool VRM UX: `.vrm` files are imported as `VRM Avatar` / `Avatar
  Target` assets, not as normal media and not as Program Output clips. The item
  badge is `VRM`. Double-click selects the asset as `VRM / VSeeFace Bridge`
  and opens the shared VTuber Studio. The context menu provides `Use as Avatar
  Target`, `Open VTuber Studio`, and `Set as VRM / VSeeFace Bridge Avatar`.
  Selection writes `vseeface_bridge.avatar_vrm` and
  `vtuber_studio.avatar_target_id = "vrm:vseeface_bridge"`. Direct `.vrm`
  drops are routed to this Avatar Target flow, not AR/PBR Program Output
  placement.
- Media Pool UX: only video items can be marked as Performance Source, marked
  items show a `PERF` badge, and their drags include
  `application/x-tigerstudio-performance-source`.
- Timeline UX: dropping marked media creates or reuses one dedicated
  `vtuber_performance_source` track; the active clip at timeline time drives
  avatar tracking and may change over time.
- Program Output must keep using `program_output_contract(...)` and must never
  render the Performance Source clip as the broadcast background.

Deferred TODO after the current UI/track pass:

- Live2D-specific production tuning beyond the shared Performance Source
  bridge.
- Real camera/capture device selection and reconnect UX.
- VTuber avatar renderer quality/performance hardening.
- Actual live/record output controls on top of the BroadcastScene compositor.

### Live2D Performance Source Bridge

Live2D can consume the same Performance Source timeline contract without
rendering the source video into Program Output. The bridge lives in:

- `app.live2d.performance_source_bridge`
- schema: `tigerstudio.live2d.performance_source_bridge.v1`
- Python Action: `actor.live2d.apply_performance_source`

The action resolves the active Performance Source at a timeline time, then:

1. applies Live2D mocap parameter keyframes when a mocap payload, mocap frames,
   or analyzable local video source is available;
2. applies VTuber source-framing payloads such as
   `tigerstudio.vtuber.source_framing_control.v1`;
3. maps `model_view.zoom/pan_x/pan_y` into conservative Live2D
   `pos_x/pos_y/scale` keyframes;
4. stores the original framing payload on the Live2D clip for project
   roundtrip and diagnostics.

Performance Source video remains input-only. Program Output must still use the
broadcast scene background contract: capture, normal media, or green chroma
fallback.

Current Live2D Performance Source mapping contract:

- The public subject types are `face_only`, `upper_body`, `full_body`, and
  `unknown`.
- `face_only` locks Live2D actor position/scale. It drives head, eye, mouth,
  and blink parameters without letting close-up talking-head footage move the
  actor body around.
- `upper_body` keeps face/eye/mouth parameters active but damps actor
  translation and zoom.
- `full_body` allows the wider actor transform range.
- `unknown` uses conservative transform limits when explicit subject guidance
  exists.
- Canonical Cubism parameters such as `ParamAngleX/Y/Z`,
  `ParamBodyAngleX/Y/Z`, `ParamBreath`, `ParamEyeBallX/Y`,
  `ParamMouthOpenY`, `ParamEyeLOpen`, and `ParamEyeROpen` remain the
  primary tracks.
- 2026-07-01 production tuning first pass: Live2D mocap smooths
  head yaw/pitch/roll, gaze, mouth, and eye-open channels separately, emits
  aggregate `ParamEyeOpen` / `ParamEyeBlink`, and adds subtle breath/body
  follow-through tracks so mapped clips look less like pure zoom/scale.
  Mouth/eye detail capability is still only reported when real gaze, mouth, or
  eye-open measurements exist.
- `app.live2d.performance_source_bridge.live2d_parameter_alias_contract()`
  documents fallback ids copied from canonical tracks for models that use
  alternate parameter names.
- The action stores `mocap_subject_type`,
  `mocap_movement_constraints`, `mocap_parameter_aliases`,
  `performance_source_subject_type`, and
  `performance_source_mapping_constraints` on the Live2D actor clip, so
  project save/load and preview/export can inspect the resolved behavior.

Implemented UI/preview contract:

- Existing Live2D placement remains unchanged: dragging a Live2D item creates a
  Live2D actor track/clip, and double-clicking that actor clip opens the normal
  Live2D model/motion viewer. That viewer is still the place for selecting the
  model, authored motions, scale, and placement.
- VTuber Studio is a separate avatar-agnostic operator/status surface. It is
  opened from the top toolbar, Actor menu, Command Palette, or the selected
  actor workbench card. It shows Program Output, Source Tracking, Avatar
  Mapping, and Studio Controls for VRM/VSeeFace, Live2D, and future avatar
  targets; it does not replace the Live2D viewer.
- Selecting a Live2D actor clip in the timeline should surface the same three
  actions in the Workbench: open the Live2D viewer, map the active Performance
  Source, and open VTuber Studio. This keeps model/motion editing, tracking
  mapping, and broadcast monitoring discoverable without changing the original
  actor-track workflow.
- Keep the Live2D editor/right-click entry named `Performance Source Mapping`
  or localized `퍼포먼스 소스 매핑`.
- Avoid an apply-button-only workflow. The editor should behave like Spine:
  select/adjust, then closing the editor leaves the actor clip updated.
- When the playhead is outside the actor clip while editing, either move the
  playhead to the actor clip start or force the actor preview visible inside
  the editor. Pick the route with less timeline surprise during UI integration.
- Main preview and popout preview must both evaluate Live2D animation plus
  Performance Source mapping results. This is preview/export parity work, not
  a Performance Source action contract change.
- 2026-06-30: `Live2DActorLaneRow` and `Live2DEditorWindow` route
  `Performance Source Mapping` into the registered
  `actor.live2d.apply_performance_source` action. Main preview and Preview
  Popout both receive the current composited preview frame.
- 2026-07-01: `VideoEditorWindow` exposes a first-pass avatar-agnostic VTuber
  Studio window and selected-Live2D Workbench card so users can see where
  Program Output, input-only Performance Source tracking, VRM/VSeeFace bridge
  monitoring, and Live2D mapping live. The studio must not be positioned as
  Live2D-exclusive.

## Bridge Status Report

For product UI integration, prefer the single status entry point:

```python
from app.vtuber.vseeface_bridge import build_vseeface_bridge_status

status = build_vseeface_bridge_status(config, capture_diagnostics=probe_report)
```

It returns:

```json
{
  "state": "degraded",
  "ok": true,
  "ui": {
    "label": "Black frame",
    "severity": "blocked",
    "action": "fix_vseeface_rendering_or_start_scene"
  },
  "actions": [
    {
      "id": "use_internal_vrm_fallback",
      "label": "Use internal VRM fallback",
      "kind": "fallback",
      "primary": true,
      "blocking": false,
      "auto_run": false,
      "plan": {
        "schema": "tigerstudio.vtuber.vseeface_bridge.action_plan.v1",
        "action_id": "use_internal_vrm_fallback",
        "auto_run": false,
        "requires_user_initiation": true,
        "requires_admin": false,
        "steps": [
          {"id": "enable_internal_vrm_fallback", "kind": "ui", "control": "scene_update", "auto_run": false}
        ]
      }
    },
    {
      "id": "fix_vseeface_rendering_or_start_scene",
      "label": "Fix VSeeFace render",
      "kind": "manual_setup",
      "primary": false,
      "blocking": false,
      "auto_run": false
    }
  ],
  "view": {
    "schema": "tigerstudio.vtuber.vseeface_bridge.view_model.v1",
    "title": "VSeeFace Bridge",
    "state": "degraded",
    "show_debug": false,
    "badge": {"text": "Black frame", "tone": "blocked"},
    "summary": "VSeeFace capture is black; Program Output falls back to the internal VRM renderer.",
    "fallback": {
      "mode": "internal_vrm_renderer",
      "active": true,
      "source_id": "internal_vrm_fallback",
      "label": "Internal VRM fallback",
      "program_output": true,
      "requires_vseeface_capture": false
    },
    "primary_action": {
      "id": "use_internal_vrm_fallback",
      "label": "Use internal VRM fallback",
      "kind": "fallback",
      "enabled": true,
      "primary": true,
      "auto_run": false
    },
    "secondary_actions": [],
    "cards": [
      {"id": "setup", "title": "Setup", "text": "VSeeFace executable and VRM avatar are configured.", "tone": "ok"},
      {"id": "capture", "title": "Capture", "text": "Black frame", "tone": "blocked"},
      {"id": "scene", "title": "Scene", "text": "Scene OK through internal VRM fallback.", "tone": "warning"}
    ]
  },
  "preflight": {},
  "capture": {},
  "scene_diagnostics": {},
  "scene": {}
}
```

State meanings:

- `ready`: VSeeFace exe/VRM preflight passed and capture is ready.
- `needs_probe`: VSeeFace exe/VRM preflight passed but capture has not been
  probed yet.
- `degraded`: preflight passed, but VSeeFace capture is blocked or black;
  Program Output remains usable through `internal_vrm_fallback`, while VSeeFace
  repair/setup actions stay secondary.
- `blocked`: setup is incomplete, such as missing `VSeeFace.exe` or a non-VRM0
  avatar.

The UI should use `status["ui"]` for labels/actions and avoid showing raw
diagnostic JSON by default.

`status["actions"]` is the product-facing action list. All actions currently
set `auto_run=false`; even probe/setup actions should be explicitly initiated
by the UI/user, not silently launched as part of project open.

Each action includes a `plan` with manual/tool/UI steps. Plans are declarative:
the bridge never executes them automatically. `register_vseeface_camera` has
`requires_admin=true` and includes the explicit registration tool step, so the
UI can ask for administrator approval before launching anything.

Action preview CLI:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_bridge_action.py --status-report debugCapture\vseeface_bridge_status.json --out debugCapture\vseeface_bridge_action_preview.json
```

This CLI is dry-run only. It resolves the primary action or `--action-id`,
validates the plan, and reports whether administrator confirmation is required.
It does not launch VSeeFace, FFmpeg, regsvr32, or any setup batch.

Important degraded capture states:

- `virtual_camera_black_frame`: VSeeFaceCamera opens, but the captured pixels are
  black. Primary action: `use_internal_vrm_fallback`; VSeeFace repair is
  secondary.
- `blocked_registration_required`: VSeeFaceCamera is not registered. Primary
  action: `use_internal_vrm_fallback`; `register_vseeface_camera` remains a
  secondary manual/admin setup action and must not run automatically.
- `virtual_camera_capture_failed`: virtual-camera capture failed after setup.
  Primary action: `use_internal_vrm_fallback`; `confirm_vseeface_camera_enabled`
  remains secondary.

`status["view"]` is the UI-facing ViewModel. It intentionally omits raw
preflight/capture JSON and provides only a badge, summary, cards, and display
actions. Use this for normal UI; keep the full status report for diagnostics
and QA logs.

CLI wrapper:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_bridge_status.py --capture-report debugCapture\vseeface_post_install_report.json --out debugCapture\vseeface_bridge_status.json
```

To include Media Pool and timeline clip choices in that report:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_bridge_status.py --project-snapshot debugCapture\project_snapshot.json --camera-device "webcam0=USB Camera" --out debugCapture\vseeface_bridge_status.json
```

When the capture report is a VSeeFace post-install/virtual-camera report, the
bridge status infers `capture.method=virtual_camera` even if the saved config
still has the default `window_capture`. This keeps UI labels and source settings
aligned with the probe that actually ran.

For local smoke checks without a real probe report:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_bridge_status.py --capture-status virtual_camera_black_frame --out debugCapture\vseeface_bridge_status_black.json
```

## VRM Pose Application Verification

There are two separate levels of verification:

- Pose-channel verification: TigerCapture can prove that face tracking data maps
  into VRM/VMC-compatible humanoid bones and blendshapes.
- Render verification: VSeeFace must visually render the VRM moving through a
  working capture backend such as Spout2, virtual camera, or window capture.

Current local result on 2026-06-29:

- Pose-channel verification passes.
- VSeeFace render verification is still blocked by the local window capture
  issue documented above.

Pose verification modules:

```python
from app.vtuber.openseeface_motion import load_openseeface_motion_csv, summarize_openseeface_motion
from app.vtuber.vrm_pose_driver import build_vrm_pose_frames, summarize_vrm_pose_frames
```

Visual proof tool:

```powershell
.\.venv\Scripts\python.exe tools\render_openseeface_vrm_pose_preview.py --csv debugCapture\openseeface_trump_to_vseeface_39540_data.csv
```

Trump face-video probe result:

```json
{
  "tracking_frames": 36,
  "confidence_mean": 0.903,
  "animated_bones": ["Chest", "Head", "Neck", "Spine"],
  "animated_blends": ["A", "Blink_L", "Blink_R"],
  "head_rotation_range": 0.0749
}
```

This means the current bridge can generate a VRM-compatible animation stream for
head/upper-torso follow-through plus mouth/blink blendshapes. It does not yet
prove that VSeeFace renders that animation in the current remote session.

## Face Video Driver

The bridge can be tested without a webcam by driving VSeeFace through its VMC
protocol receiver. This path still keeps VSeeFace external:

```text
face video -> TigerCapture face-video driver -> VMC/OSC UDP -> VSeeFace -> capture source
```

Implementation modules:

```python
from app.vtuber.video_face_driver import VideoFaceMotionExtractor, motion_from_face_box
from app.vtuber.vmc_protocol import VmcEndpoint, build_vmc_messages_from_face_frame, send_vmc_messages
```

CLI dry run:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_video_driver.py --video C:\path\face.mp4
```

Live send:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_video_driver.py --video C:\path\face.mp4 --send
```

Live readiness check:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_live_check.py --port 39539
```

The live check must report `ready=true` before VSeeFace can visibly react to
video-driven VMC packets. If it reports `vmc_receiver_port_not_open`, VSeeFace
is running but its VMC receiver is not enabled yet.

Important setting distinction:

- `settings.ini` keys `IP` and `Port` belong to VSeeFace's
  `[OpenSeeFace tracking]` input mode.
- They do not enable the VMC receiver.
- In v1.13.38c, reflection shows `VMCReceiverManager.SetVMCEnabled` and
  `SetVMCPort` are runtime UI callbacks, not stable `settings.ini` keys.

The live check also inspects the installed VSeeFace `Assembly-CSharp.dll` for
VMC receiver runtime symbols. The current local build reports:

```text
VMCReceiverManager=true
SetVMCEnabled=true
SetVMCPort=true
EVMC4U.ExternalReceiver=true
/VMC/Ext/Bone/Pos=true
/VMC/Ext/Blend/Val=true
```

This means the installed VSeeFace build contains the receiver API, even though
the current remote/black-window session has not enabled the receiver port.

VSeeFace's default VMC receiver port is `39539`. Its default VMC sender port is
`39540`. TigerCapture can send to either if the VSeeFace UI is configured that
way, but the bridge default follows VSeeFace's receiver default: `39539`.

Bridge loopback check without VSeeFace:

```powershell
.\.venv\Scripts\python.exe tools\vmc_udp_loopback_check.py --video C:\path\face.mp4 --backend auto --duration-seconds 5 --fps 15
```

Use the loopback check to prove TigerCapture's face-video extraction and UDP
packet generation before blaming VSeeFace. It binds a local UDP listener, sends
the generated VMC/OSC packets to it, and records `sent_packets` plus
`received_packets`.

## Face Input Modes

Bridge `input.mode` has two supported values:

- `webcam`: VSeeFace uses its normal camera/device input.
- `openseeface_video`: TigerCapture decodes a video file and feeds raw RGB
  frames to VSeeFace's bundled `facetracker.exe`, which sends OpenSeeFace UDP
  tracking packets to VSeeFace.

This is intentionally separate from `tracking`. `tracking` describes the
VMC/OSC bridge contract. `input` describes how VSeeFace gets face-tracking
data.

Native OpenSeeFace video source:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_openseeface_video_source.py --video C:\path\face.mp4 --port 39540 --duration-seconds 5 --realtime
```

Product code should call the UI-neutral module directly:

```python
from app.vtuber.openseeface_video_source import parse_crop, run_video_source
```

This uses VSeeFace's bundled `facetracker.exe` instead of TigerCapture's
MediaPipe/VMC sender. It decodes the input video with OpenCV, feeds raw RGB
frames into `facetracker.exe --raw-rgb 1`, and sends native OpenSeeFace tracking
UDP packets to VSeeFace's `[OpenSeeFace tracking]` input port.

For videos where the face is small in frame, pass a normalized crop:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_openseeface_video_source.py --video "C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\trump_oval_office_live_GnzWEo_HfE0.mp4" --port 39540 --duration-seconds 3 --fps 12 --try-hard --detection-threshold 0.2 --crop "0.32,0.05,0.36,0.75"
```

Local cropped Trump-video probe result:

```text
frames_written=36
tracking_rows=73
udp_packets=36
confidence_tail~=0.90
```

This proves a camera-free VSeeFace-native tracking source is possible. It still
requires VSeeFace itself to have a VRM avatar loaded and `[OpenSeeFace tracking]`
selected before the avatar can visibly move.

Port matrix loopback check:

```powershell
.\.venv\Scripts\python.exe tools\vmc_port_matrix_check.py --video C:\path\face.mp4 --backend auto --duration-seconds 5 --fps 15
```

This checks both common VSeeFace ports in one report:

- `39539`: VSeeFace's documented VMC receiver default.
- `39540`: VSeeFace's documented VMC sender default and a common iPhone/Waidayo receiver override.

Recommended quality path:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_video_driver.py --video C:\path\face.mp4 --backend auto --calibrate-seconds 0.8 --smoothing 0.35 --send
```

MediaPipe Tasks model path used by durable local setups:

```text
E:\ClaudeCodeApp\GifCam\resources\mediapipe\face_landmarker.task
```

`--backend auto` searches for `face_landmarker.task` next to the input video,
then in `resources/mediapipe`. Older `debugCapture` model locations were
temporary diagnostics and must not be treated as durable dependencies.

VSeeFace setup for live send:

- Load a VRM0 avatar.
- Enable the VMC protocol receiver.
- Keep the receiver port at `39539`, or pass `--port` if you change it in VSeeFace.
- Keep VSeeFace running while the driver sends motion.

Prepare sidecar settings without touching the editor:

```powershell
.\.venv\Scripts\python.exe tools\configure_vseeface_sidecar.py --avatar-vrm E:\path\avatar.vrm --openseeface-port 39540
```

This writes one `[OpenSeeDemo]` section using ASCII when possible and UTF-16
when non-ASCII paths require it. Do not write this file as UTF-8 with BOM:
local testing showed VSeeFace can ignore those keys and append a duplicate
`[OpenSeeDemo]` section.

For the virtual camera capture backend, the sidecar writer also sets
`KeepVirtualCamEnabled=1`. This key is present in VSeeFace v1.13.38c's managed
assembly and is used to keep the bundled UnityCapture output available across
launches. It is separate from VMC receiver enablement.

Local post-install verification now distinguishes these states:

- `VSeeFaceCamera` DirectShow registration: registry/device availability.
- OpenCV camera probing: best effort only; local OpenCV cannot open the
  registered DirectShow source by name or index.
- FFmpeg DirectShow probing: authoritative local capture fallback via
  `imageio_ffmpeg`.
- `virtual_camera_black_frame`: FFmpeg opened `VSeeFaceCamera` and captured a
  valid 1280x720 frame, but the pixels were black. This means the bridge has
  passed device registration/capture and is blocked on VSeeFace rendering or
  start-scene activation.

Current extended graphics probe findings:

- `default_native`, `default_windowed`, `d3d11_windowed`,
  `d3d11_popupwindow`, `d3d11_no_singlethreaded`, and
  `d3d11_singlethreaded` all create a responsive VSeeFace window, but the
  client area remains black.
- `vulkan_windowed` and `glcore_windowed` show Unity
  `InitializeEngineGraphics failed` error dialogs and are not usable render
  backends.
- `VSeeFaceCamera` opens through FFmpeg DirectShow for every variant tested,
  but its pixels remain black, so this is not an OpenCV-only capture problem.
- A temporary minimal `settings.ini` did not change the black render result;
  the original sidecar settings were restored after the test.

Current local Trump-video test:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_video_driver.py --video "C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\trump_oval_office_live_GnzWEo_HfE0.mp4" --backend auto --duration-seconds 5 --fps 15 --send
```

Observed sender result:

```text
selected_backend=mediapipe_tasks
frame_count=76
sent_packets=836
endpoint=127.0.0.1:39540
```

The earlier local send used `39540`, which is valid only if the VSeeFace
receiver port is manually changed to `39540`. For default VSeeFace receiver
settings, use:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_video_driver.py --video "C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\trump_oval_office_live_GnzWEo_HfE0.mp4" --backend auto --duration-seconds 5 --fps 15 --port 39539 --send
```

Observed loopback result:

```text
ports=39539,39540
frame_count=76 on each port
sent_packets=836 on each port
received_packets=836 on each port
selected_backend=mediapipe_tasks
```

Observed sidecar state:

```text
VSeeFace process: running
VSeeFace window capture: black in current remote/capture environment
VMC receiver port 39539/39540: not open
VMC receiver runtime API: present in Assembly-CSharp.dll
```

So the face-video sender path is verified, but live VSeeFace application needs
the receiver enabled from the VSeeFace UI or an identified settings key before
avatar motion can be visually confirmed.

Do not disable VSeeFace's Leap plugin DLLs as a workaround for missing Leap
hardware. Local testing showed that renaming `LeapCV4.dll`/`LeapCV5.dll` causes
Leap `NullReferenceException` spam and does not enable the VMC receiver.

Additional local sidecar findings:

- A clean VSeeFace `settings.ini` still produces a black client-area capture in
  this remote environment.
- `-force-opengl` is not usable for this VSeeFace build; Unity reports
  `InitializeEngineGraphics failed`.
- `-force-d3d11 -screen-fullscreen 0` starts the sidecar, but the captured
  client area remains black and the VMC receiver port remains closed.
- `tools\vseeface_click_probe.py` tested lower-row start/select button
  candidates against the black VSeeFace window. None opened the VMC receiver.
- Sending the documented `L` model-load hotkey does not open a file dialog while
  the window is in this black state.
- Sending the documented `Ctrl+Shift+F7` Leap toggle hotkey does not open the
  VMC receiver port or change the black capture state.
- VSeeFace release notes say the VMC receiver enable state is saved, but
  reflection shows `VMCReceiverManager.SetVMCEnabled` is a runtime UI callback,
  not a direct `settings.ini` key reader. The reliable automation route is still
  unknown.
- Candidate `VMCReceive*` settings.ini keys were tested and removed after they
  failed to open the receiver port. The current local settings keep only the
  avatar path, OpenSeeFace input endpoint, `KeepVirtualCamEnabled=1`, and Leap
  disable keys.
- Local DLL patching to suppress Leap startup retries is a sidecar diagnostic
  aid only. It is not part of the product bridge and must not become a
  TigerCapture runtime dependency.

Current recommended engineering fallback:

1. Keep TigerCapture's video-face driver and VMC/OSC sender as an independent,
   tested bridge layer.
2. Use `vmc_udp_loopback_check.py` as the local CI/smoke test until a visible
   VSeeFace receiver can be enabled manually or by a stable automation path.
3. Treat live VSeeFace visual confirmation as blocked on sidecar UI/receiver
   access, not on TigerCapture packet generation.

2026-07-01 confirmed launch/probe result:

- `start_vseeface_and_probe` starts the local VSeeFace sidecar and writes
  `debugCapture\vseeface_start_probe_execute.json`.
- `tools\verify_vseeface_post_install.py --launch-vseeface` can open
  `VSeeFaceCamera` through FFmpeg DirectShow, but the captured frame remains
  black.
- Running the same verification with the Trump test video enabled generates
  OpenSeeFace tracking rows, but the VSeeFace client area and virtual camera
  output remain black.
- `tools\vseeface_graphics_probe.py --wait-seconds 10 --include-glcore`
  reports no usable graphics variant in the current environment. D3D11 variants
  stay black; Vulkan/GLCore show Unity graphics initialization errors.
- Status reports should pass the capture report explicitly:

```powershell
.\.venv\Scripts\python.exe tools\vseeface_bridge_status.py --capture-report debugCapture\vseeface_post_install_with_video_report.json --out debugCapture\vseeface_bridge_status_after_black_probe_explicit.json
.\.venv\Scripts\python.exe tools\render_vseeface_broadcast_scene_summary.py --capture-report debugCapture\vseeface_post_install_with_video_report.json --out debugCapture\vseeface_broadcast_scene_summary_black_probe_report.png
```

Expected product state from that report is `state=degraded`,
`capture_status=virtual_camera_black_frame`, `suppress_black_frame=true`,
`fallback.mode=internal_vrm_renderer`, and primary action
`use_internal_vrm_fallback`.

Internal fallback Program Output is implemented separately from the VSeeFace
sidecar:

```text
app/vtuber/internal_vrm_fallback.py
tools/render_internal_vrm_fallback_program_output.py
```

The renderer consumes the same VRM avatar plus OpenSeeFace motion CSV and
returns a transparent avatar frame for the `internal_vrm_fallback` BroadcastScene
source. The proof tool feeds a black `vseeface` frame and the fallback avatar
frame into `composite_broadcast_frame()`, so the expected compositor diagnostics
are:

```text
vseeface.suppressed_black_frame=true
internal_vrm_fallback.rendered=true
program_output_excludes_performance_source=true
```

## Shared VTuber Studio

Do not create a separate VRM Studio window. The shared editor window is
`VTuberBroadcastStudioWindow`, and it must remain avatar-agnostic. Live2D and
VRM use the same Studio UI; selecting an asset or `Avatar Target` changes the
workflow inside the Studio, not the window or product surface:

- `Avatar Target`: selected VRM/VSeeFace, Live2D actor clip, or future avatar.
- `Performance Source`: camera/video tracking input only.
- `Program Output`: final broadcast/record picture; never the Performance
  Source video directly.
- `Live Target`: final Program Output destination for record, RTMP/RTMPS, or
  video-call/window-share output.
- `VRM / VSeeFace Bridge`: VRM target that uses bridge pose stream, VMC/
  OpenSeeFace status, and optional VSeeFace capture output.

The shared operator flow is:

```text
VTuberBroadcastStudioWindow
-> Avatar Target selection
-> target-specific mapping controls
-> Program Output / Source Tracking / Avatar Mapping monitors
-> Live Target output controls
```

Registered action ids:

```text
vtuber.studio.open
vtuber.avatar_target.summary
vtuber.avatar_target.select
vtuber.vrm.bridge_status
vtuber.vrm.pose_stream_preview
broadcast.live_target.summary
broadcast.live_target.select
broadcast.platform_evidence_checklist
broadcast.platform_evidence.preflight
broadcast.platform_evidence.register
```

Live2D direct key baking remains separate:

```text
actor.live2d.apply_performance_source
```

VRM/VSeeFace does not use that Live2D baking action. Its path is:

```text
Performance Source -> OpenSeeFace -> VMC/pose stream -> VRM / VSeeFace Bridge
```

Media Pool `.vrm` import is the product UX for choosing this target. A VRM
item is classified as `VRM Avatar` / `Avatar Target`, carries a `VRM` badge,
and stores the chosen file in `project_settings["vseeface_bridge"]["avatar_vrm"]`
while selecting `project_settings["vtuber_studio"]["avatar_target_id"] =
"vrm:vseeface_bridge"`. Double-clicking a VRM item opens this shared Studio;
right-click exposes explicit target/studio/bridge actions. The VRM file itself
must never be treated as Program Output media.

The driver prefers MediaPipe Tasks FaceLandmarker when a `.task` model is
available. It then falls back to legacy MediaPipe FaceMesh when the
`mp.solutions.face_mesh` API is available, and finally to OpenCV face-box
tracking. The output includes head yaw/pitch/roll, mouth open, blink values,
neutral-pose calibration, and exponential smoothing. Higher quality
ARKit-style blendshape tracking can replace the extractor behind the same VMC
sender contract.

Useful tuning flags:

- `--backend auto|mediapipe_tasks|mediapipe|opencv`
- `--face-landmarker-model C:\path\face_landmarker.task`
- `--calibrate-seconds 0.8`
- `--smoothing 0.35`
- `--no-blink-calibration`
- `--calibrate-mouth`
- `--yaw-scale`, `--pitch-scale`, `--roll-scale`
- `--mouth-scale`, `--blink-scale`

Blink calibration is enabled by default in the live sender and loopback tools.
MediaPipe blendshape scores can sit around a high neutral eye baseline for some
videos. Without calibration, this can make the avatar look half-closed even
when the source face is only relaxed. The current Trump-video QC run reduced the
decoded VMC blink values from roughly `0.7` to:

```text
Blink_L=0.103
Blink_R=0.057
```

The raw detector score is still available by passing `--no-blink-calibration`
for diagnostics.

## VRM Compatibility

VSeeFace supports VRM0 avatars. The bridge preflight reports:

- `vseeface_compatible=true` for VRM0.
- `vseeface_compatible=false` for VRM1.

VRM1 can still be useful for internal preview, but it is not accepted as a
VSeeFace bridge avatar unless converted to VRM0 outside this bridge.

## Local Test Assets

Current local sidecar executable:

```text
E:\ClaudeCodeApp\GifCam\external\tools\vseeface\VSeeFace\VSeeFace.exe
```

Current local VRM0 avatar:

```text
E:\ClaudeCodeApp\GifCam\external\assets\vtuber\booth_milica\Milica1.3free\Milica_v1.3.vrm
```

These paths are test defaults only. They are not required for normal editor
startup.
