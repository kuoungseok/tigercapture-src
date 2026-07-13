# Unreal MCP Capture Control

This document is for an Unreal-side Codex/AI agent that needs TigerCapture to
record Unreal Editor work, such as terrain generation, through the MCP/AI
capture action surface.

The important boundary:

- Do not ask for TigerCapture UI buttons, launcher capture UI, or a visible
  editor panel.
- Use the registered MCP/AI actions exposed through
  `tigercapture_execute_action`.
- Capture the Unreal Editor as an external Windows application window.
- Use `backend: "auto"` for Unreal. TigerCapture automatically tries
  `wgc_window` first for Unreal Editor windows, then falls back to visible crop
  if WGC is unavailable.
- Prefer `hwnd` once discovered; it avoids title ambiguity.
- Do not use OBS as the default Unreal recording route. If OBS Program Output
  or an OBS Window/Game Capture source is black, TigerCapture will faithfully
  record that black output. The default route is direct Unreal `hwnd` capture.

## Do Not Default To OBS For Unreal

OBS can be useful for streaming setups, but it is not the default capture path
for Unreal Editor evidence. Unreal/GPU windows often produce black frames in
OBS when the source type, GPU adapter, elevation/admin state, HDR mode, or
window-capture method is mismatched.

For Unreal terrain generation, the Unreal-side agent must prefer:

```json
{
  "action": "capture.window.video.start",
  "params": {
    "session_id": "unreal-terrain",
    "hwnd": 123456,
    "path": "debugCapture/unreal_terrain_generation.mp4",
    "max_duration_ms": 600000,
    "fps": 15,
    "backend": "auto",
    "activate": true
  }
}
```

Do not target the OBS window unless the user explicitly asks to record OBS or
the agent has already verified OBS Program Output is non-black. If a previous
attempt recorded a black OBS output, switch to direct Unreal `hwnd` capture
instead of retrying OBS.

## Quick Contract

If the Unreal-side agent asks "how long should TigerCapture record?", use this
contract:

> Start recording before the Unreal operation begins. Stop recording when the
> Unreal operation completes. Always provide `max_duration_ms` as a hard safety
> timeout in case the stop request never arrives.

For terrain generation or any operation with unknown duration, use:

1. `capture.windows.list`
2. `capture.window.video.start`
3. optional `capture.window.video.status`
4. `capture.window.video.stop`

Use fixed-duration `capture.window.video` only when the exact duration is known
up front.

## MCP Tool Shape

All examples below are arguments for the MCP tool:

```json
{
  "name": "tigercapture_execute_action",
  "arguments": {
    "action": "capture.windows.list",
    "params": {}
  }
}
```

If your MCP client already exposes actions directly, call the `action` and
`params` objects shown in each section.

## 1. Find The Unreal Window

Start by listing Unreal windows:

```json
{
  "action": "capture.windows.list",
  "params": {
    "process_contains": "UnrealEditor",
    "include_invisible": false,
    "limit": 20
  }
}
```

Expected response shape:

```json
{
  "windows": [
    {
      "hwnd": 123456,
      "title": "MyProject - Unreal Editor",
      "process_name": "UnrealEditor.exe",
      "visible": true,
      "minimized": false,
      "width": 1920,
      "height": 1080
    }
  ]
}
```

Pick the visible, non-minimized Unreal Editor window. If several Unreal windows
exist, prefer the one whose title contains the active project/map name. Use the
returned `hwnd` for later calls.

## 2. Start Recording Before The Operation

Use session recording for terrain generation:

```json
{
  "action": "capture.window.video.start",
  "params": {
    "session_id": "unreal-terrain",
    "hwnd": 123456,
    "path": "debugCapture/unreal_terrain_generation.mp4",
    "max_duration_ms": 600000,
    "fps": 15,
    "backend": "auto",
    "activate": true,
    "crf": 23
  }
}
```

Parameter guidance:

- `session_id`: stable id the Unreal-side agent will use for status/stop.
- `hwnd`: preferred target from `capture.windows.list`.
- `path`: output MP4/MOV/MKV. `debugCapture` is acceptable for temporary QA
  evidence.
- `max_duration_ms`: hard timeout. Recommended defaults:
  - short terrain operation: `300000` (5 minutes)
  - normal terrain generation: `600000` (10 minutes)
  - long batch: up to `14400000` (4 hours)
  - for multi-hour QA evidence, prefer stopping and starting a new segment at
    natural operation boundaries instead of leaving one unbounded capture
- `fps`: use `15` for evidence capture; use `30` only when motion fidelity is
  important.
- `backend`: use `auto`. For Unreal Editor this prefers `wgc_window`, which can
  capture the Unreal window even when other windows overlap it. If WGC is not
  available, TigerCapture falls back to visible crop.
- `activate`: use `true` when it is acceptable to foreground Unreal. Use
  `false` if the Unreal-side agent must avoid stealing focus; WGC can still
  capture an overlapped non-minimized window.
- `crf`: `23` is normal; lower is larger/higher quality, higher is smaller.

After this call returns, the Unreal-side agent can begin the terrain operation.

## 3. Poll Status If Needed

Status is optional but useful for long operations:

```json
{
  "action": "capture.window.video.status",
  "params": {
    "session_id": "unreal-terrain"
  }
}
```

Use the response to verify:

- `running: true` while recording continues.
- `elapsed_ms` is below `max_duration_ms`.
- `error` is empty.
- `path` points to the output file.

If status becomes `completed`, TigerCapture reached `max_duration_ms` before
the Unreal-side agent sent stop. Treat this as a timeout and start a new segment
if more capture is needed.

## 4. Stop When Unreal Finishes

When terrain generation completes:

```json
{
  "action": "capture.window.video.stop",
  "params": {
    "session_id": "unreal-terrain",
    "wait_ms": 30000
  }
}
```

Expected success indicators:

- `running: false`
- `status: "stopped"` or `"completed"`
- `result.path` or top-level session `path` exists
- `result.stopped_by: "request"` when the stop command ended the recording

## Fixed-Duration Alternative

Use this only when the Unreal-side agent already knows the exact recording
length:

```json
{
  "action": "capture.window.video",
  "params": {
    "hwnd": 123456,
    "path": "debugCapture/unreal_terrain_30s.mp4",
    "duration_ms": 30000,
    "fps": 15,
    "backend": "auto",
    "activate": true
  }
}
```

This blocks until the fixed-duration recording completes. Do not use it for
terrain generation with unknown duration.

## Failure Handling

If no Unreal window is found:

1. Open or foreground Unreal Editor.
2. Retry `capture.windows.list` with `process_contains: "UnrealEditor"`.
3. If needed, add `title_contains` with the project or map title.
4. Use `include_invisible: true` only for diagnostics; recording requires a
   visible, non-minimized window.

If the video is black or wrong:

- If the target was OBS, discard that route and capture the Unreal Editor
  window directly by `hwnd` with `backend: "auto"`.
- Use `backend: "auto"` first. It prefers `wgc_window` for Unreal.
- Avoid `printwindow` for Unreal. GPU windows often fail with that backend.
- If `wgc_window` is unavailable and TigerCapture falls back to visible crop,
  keep Unreal visible and not covered by another window.
- Use `activate: true` before starting if focus stealing is acceptable.
- Lower `fps` if terrain generation is heavy.
- If the recording times out, stop the current session and start a new segment
  with a higher `max_duration_ms`.

If multiple Unreal windows exist:

- Prefer `hwnd` from the exact listed row.
- Do not rely only on `title_contains` if two windows share a similar title.

## Minimal Unreal-Side Agent Procedure

1. List windows with `process_contains: "UnrealEditor"`.
2. Select a visible, non-minimized `hwnd`.
3. Start `capture.window.video.start` with `session_id`, `hwnd`, `path`,
   `backend: "auto"`, and `max_duration_ms`.
4. Run the Unreal terrain generation.
5. Stop with `capture.window.video.stop` using the same `session_id`.
6. Report the output `path` and any `error`.
