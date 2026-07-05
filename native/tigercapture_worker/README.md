# TigerCapture Worker

Rust subprocess worker for cross-platform native helper modules.

Protocol: one JSON request per stdin line, one JSON response or progress event
per stdout line.

Initial request:

```json
{"id":1,"method":"capabilities","params":{}}
```

Initial response:

```json
{"id":1,"ok":true,"result":{"name":"tigercapture-worker","version":"0.1.0","protocol":"json-lines-v1","features":["capabilities","media_probe","batch_media_probe","timeline_thumbnails","timeline_drag_constraints","timeline_gaps","timeline_trim_plan","audio_waveform","audio_spectrum","validate_golden_fixture","file_contracts","progress_events","cancellation","golden_fixture_validation"]}}
```

Timeline drag planning:

```json
{"id":2,"method":"timeline_drag_constraints","params":{"clips":[{"id":10,"timeline_in_ms":0,"timeline_out_ms":1000,"effective_length_ms":1000}],"dragged_clip_id":10,"desired_timeline_in_ms":5200,"snap_ms":150,"extra_snap_targets":[5300]}}
```

This returns the same snap/collision/clamp fields as the Python timeline drag
policy, so UI code can use the Rust result when available and keep Python
fallback behavior when it is not.

Timeline gap detection:

```json
{"id":3,"method":"timeline_gaps","params":{"clips":[{"id":10,"timeline_in_ms":0,"timeline_out_ms":1000},{"id":11,"timeline_in_ms":1500,"timeline_out_ms":2000}],"min_gap_ms":1}}
```

This returns `gap_count` and `gaps` rows compatible with the Python `_track_gaps`
helper used by `timeline.gaps`, `timeline.close_gap`, and
`timeline.close_all_gaps`.

Timeline trim planning:

```json
{"id":4,"method":"timeline_trim_plan","params":{"clips":[{"id":10,"timeline_in_ms":0,"timeline_out_ms":1000,"source_in_ms":0,"source_out_ms":1000,"source_duration_ms":5000},{"id":11,"timeline_in_ms":1500,"timeline_out_ms":2500,"source_in_ms":0,"source_out_ms":1000,"source_duration_ms":5000}],"clip_id":10,"mode":"precision_trim","source_out_ms":700,"ripple":true}}
```

This returns a pure video trim plan with selected clip `old`/`new`,
`ripple_delta_ms`, and `shifted_clips`. Python keeps validation, linked audio,
undo, and timeline mutation.

Progress event:

```json
{"id":2,"event":"progress","result":{"current":1,"total":10,"message":"thumbnail 2/10"}}
```

Cancellation response:

```json
{"id":2,"ok":false,"error":"cancelled","error_code":"cancelled"}
```

Build when Rust is installed:

```powershell
cd native\tigercapture_worker
cargo build --release
```

Windows release builds run this automatically from `build.ps1` before
PyInstaller. PyInstaller bundles the release executable into `bundled/native`,
where `app.native_worker.discover_native_worker_command()` finds it at runtime.
