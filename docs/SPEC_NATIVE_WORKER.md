# TigerCapture Native Worker Spec

Last updated: 2026-07-03

TigerCapture uses a subprocess-first native worker strategy. The Python UI
stays in control of timeline semantics, project state, and Qt rendering; native
helpers handle isolated file/media work that benefits from Rust/FFmpeg speed.

## Protocol

- Transport: JSON-lines over stdin/stdout.
- Version: `json-lines-v1`.
- Request shape:

```json
{"id":1,"method":"timeline_thumbnails","params":{}}
```

- Final response shape:

```json
{"id":1,"ok":true,"result":{}}
```

- Error response shape:

```json
{"id":1,"ok":false,"error":"cancelled","error_code":"cancelled","details":{}}
```

- Progress event shape:

```json
{"id":1,"event":"progress","result":{"current":3,"total":10,"message":"thumbnail 4/10"}}
```

Existing callers can continue using `NativeWorkerClient.request()`. Long-running
commands that need progress/cancel use `request_with_events()`.

## File Contracts

Python wrappers attach file contracts under `params.files` while preserving the
older flat params such as `path` and `out_dir`.

```json
{
  "files": [
    {"role":"source_media","kind":"file","path":"clip.mp4","must_exist":true},
    {"role":"thumbnail_dir","kind":"directory","path":"cache","must_exist":false}
  ]
}
```

`app.native_worker.NativeWorkerFileContract` validates local existence and
creates output directories before a worker call. The Rust worker may also use
the metadata for future stricter validation.

## Cancellation

Long-running commands accept `cancel_token_path`. If that file exists while the
worker is between work units, the worker returns:

```json
{"ok":false,"error":"cancelled","error_code":"cancelled"}
```

This keeps cancellation process-safe without requiring thread sharing inside the
Rust worker.

## Current Methods

- `capabilities`
- `shutdown`
- `media_probe`
- `batch_media_probe`
- `timeline_thumbnails`
- `timeline_drag_constraints`
- `timeline_gaps`
- `timeline_trim_plan`
- `audio_waveform`
- `audio_spectrum`
- `validate_golden_fixture`

`batch_media_probe` accepts a `paths` array and optional `ffmpeg_path`, then
returns one item per source. Use it for media-pool/project-open scans so the
UI pays the worker startup cost once instead of once per file.

`timeline_thumbnails` supports `emit_progress=true` and `cancel_token_path`.
`timeline_drag_constraints` is the first Rust timeline-core operation. It
accepts a UI-neutral clip array, dragged clip id/index, requested timeline-in
position, snap tolerance, and optional marker/playhead targets. It returns the
same snap/collision/clamp fields as Python `DragConstraintResult`, including
`timeline_in_ms`, `requested_timeline_in_ms`, `snapped`, `snap_target_ms`,
`snap_edge`, `snap_source`, `collided`, `clamped`, and `clamp_target_ms`.
`clip.move_snapped` uses this native result when available and falls back to the
established Python implementation when the worker is missing or outdated.
`timeline_gaps` accepts the same UI-neutral clip array plus `min_gap_ms` and
returns `gap_count` and `gaps` rows compatible with the existing Python
`_track_gaps` helper. The `timeline.gaps`, `timeline.close_gap`, and
`timeline.close_all_gaps` action paths automatically use it through the helper
when available and fall back to Python otherwise.
`timeline_trim_plan` is the third Rust timeline-core operation. It accepts a
UI-neutral clip array, selected clip id/index, and either `mode=ripple_trim`
with `edge`/`delta_ms` or `mode=precision_trim` with exact source/timeline
values and optional delta/slip/ripple fields. It returns only the pure
video-window plan: selected clip `old`/`new`, `ripple_delta_ms`, and
`shifted_clips`. Python remains responsible for validation, linked audio,
undo transactions, and project mutation. `clip.ripple_trim`,
`timeline.precision_trim`, and `timeline.trim_to_playhead` use this result when
available and fall back to the established Python calculations otherwise.
`validate_golden_fixture` verifies fixture existence, minimum size, and optional
SHA-256 match.

## Native Migration Rule

Only move code after profiling proves a repeated hotspot:

- media probing and indexing
- timeline thumbnail generation
- waveform/spectrum generation
- timeline drag/snap/collision planning
- timeline gap detection and close-gap planning
- object-tracking cache generation
- raw frame pre-render stages

Do not move project format, undo/redo semantics, or timeline editing behavior to
native code until their Python behavior is stable and exhaustively tested.
