from __future__ import annotations

import os
import hashlib
import sys

import pytest

from app.native_worker import (
    NativeWorkerClient,
    NativeWorkerError,
    discover_native_worker_command,
    get_native_worker_capabilities,
    native_audio_spectrum,
    native_audio_waveform,
    native_generate_timeline_thumbnails,
    native_media_probe,
    native_media_probe_many,
    native_timeline_drag_constraints,
    native_timeline_gaps,
    native_timeline_trim_plan,
    native_validate_golden_fixture,
)


def _fake_worker(tmp_path):
    script = tmp_path / "fake_worker.py"
    script.write_text(
        """
import json
import hashlib
import os
import sys

for line in sys.stdin:
    req = json.loads(line)
    method = req.get("method")
    if method == "capabilities":
        result = {
            "name": "fake-worker",
            "version": "0.0-test",
            "protocol": "json-lines-v1",
            "features": ["capabilities", "test"],
        }
        print(json.dumps({"id": req.get("id"), "ok": True, "result": result}), flush=True)
    elif method == "media_probe":
        result = {
            "path": req.get("params", {}).get("path", ""),
            "exists": True,
            "size": 123,
            "mtime_ns": 456,
            "duration_ms": 7890,
            "has_video": True,
            "has_audio": True,
            "width": 1920,
            "height": 1080,
            "fps": 29.97,
        }
        print(json.dumps({"id": req.get("id"), "ok": True, "result": result}), flush=True)
    elif method == "batch_media_probe":
        items = []
        for path in req.get("params", {}).get("paths", []):
            items.append({
                "path": path,
                "ok": True,
                "exists": True,
                "size": 123,
                "mtime_ns": 456,
                "duration_ms": 7890,
                "has_video": True,
                "has_audio": True,
                "width": 1920,
                "height": 1080,
                "fps": 29.97,
            })
        print(json.dumps({"id": req.get("id"), "ok": True, "result": {"count": len(items), "items": items}}), flush=True)
    elif method == "timeline_thumbnails":
        params = req.get("params", {})
        cancel_token = params.get("cancel_token_path")
        if cancel_token and os.path.exists(cancel_token):
            print(json.dumps({
                "id": req.get("id"),
                "ok": False,
                "error": "cancelled",
                "error_code": "cancelled",
            }), flush=True)
            continue
        out_dir = params.get("out_dir")
        os.makedirs(out_dir, exist_ok=True)
        files = []
        for idx in range(2):
            if params.get("emit_progress"):
                print(json.dumps({
                    "id": req.get("id"),
                    "event": "progress",
                    "result": {
                        "current": idx,
                        "total": 2,
                        "message": f"thumb {idx + 1}",
                    },
                }), flush=True)
            p = os.path.join(out_dir, f"{idx:04d}.png")
            with open(p, "wb") as fh:
                fh.write(b"fake")
            files.append(p)
        if params.get("emit_progress"):
            print(json.dumps({
                "id": req.get("id"),
                "event": "progress",
                "result": {"current": 2, "total": 2, "message": "done"},
            }), flush=True)
        result = {"duration_ms": 1000, "count": len(files), "files": files}
        print(json.dumps({"id": req.get("id"), "ok": True, "result": result}), flush=True)
    elif method == "timeline_drag_constraints":
        params = req.get("params", {})
        result = {
            "timeline_in_ms": 5300,
            "requested_timeline_in_ms": params.get("desired_timeline_in_ms", 0),
            "snapped": True,
            "snap_target_ms": 5300,
            "snap_edge": "in",
            "snap_source": "marker/playhead",
            "collided": False,
            "clamped": False,
            "clamp_target_ms": None,
            "backend": "rust_worker",
        }
        print(json.dumps({"id": req.get("id"), "ok": True, "result": result}), flush=True)
    elif method == "timeline_gaps":
        result = {
            "gap_count": 2,
            "gaps": [
                {"index": 0, "start_ms": 1000, "end_ms": 1500, "duration_ms": 500, "next_clip_id": 11},
                {"index": 1, "start_ms": 2000, "end_ms": 3000, "duration_ms": 1000, "next_clip_id": 12},
            ],
            "min_gap_ms": req.get("params", {}).get("min_gap_ms", 1),
            "backend": "rust_worker",
        }
        print(json.dumps({"id": req.get("id"), "ok": True, "result": result}), flush=True)
    elif method == "timeline_trim_plan":
        params = req.get("params", {})
        clips = params.get("clips", [])
        selected = clips[params.get("clip_index", 0)] if clips else {}
        result = {
            "backend": "rust_worker",
            "mode": params.get("mode", "precision_trim"),
            "clip_id": selected.get("id", 10),
            "edge": params.get("edge", ""),
            "requested_delta_ms": params.get("delta_ms", 0),
            "ripple": bool(params.get("ripple", params.get("mode") == "ripple_trim")),
            "ripple_delta_ms": 200,
            "old": {
                "id": selected.get("id", 10),
                "timeline_in_ms": selected.get("timeline_in_ms", 0),
                "timeline_out_ms": selected.get("timeline_out_ms", 1000),
                "source_in_ms": selected.get("source_in_ms", 0),
                "source_out_ms": selected.get("source_out_ms", 1000),
            },
            "new": {
                "id": selected.get("id", 10),
                "timeline_in_ms": selected.get("timeline_in_ms", 0),
                "timeline_out_ms": selected.get("timeline_out_ms", 1000) + 200,
                "source_in_ms": selected.get("source_in_ms", 0),
                "source_out_ms": selected.get("source_out_ms", 1000) + 200,
            },
            "timeline_delta_ms": 0,
            "shifted_clips": [{"clip_id": 12, "timeline_in_ms": 2700}],
            "changed": True,
        }
        print(json.dumps({"id": req.get("id"), "ok": True, "result": result}), flush=True)
    elif method == "audio_waveform":
        result = {"sample_rate": 8000, "buckets_per_sec": 40, "left": [0.1, 0.2], "right": [0.3, 0.4]}
        print(json.dumps({"id": req.get("id"), "ok": True, "result": result}), flush=True)
    elif method == "audio_spectrum":
        result = {"sample_rate": 44100, "samples": 8192, "bins": [0.0, 0.5, 1.0]}
        print(json.dumps({"id": req.get("id"), "ok": True, "result": result}), flush=True)
    elif method == "validate_golden_fixture":
        params = req.get("params", {})
        path = params.get("path", "")
        expected = params.get("expected_sha256", "")
        with open(path, "rb") as fh:
            data = fh.read()
        sha = hashlib.sha256(data).hexdigest()
        if expected and expected != sha:
            print(json.dumps({
                "id": req.get("id"),
                "ok": False,
                "error": "golden fixture sha256 mismatch",
                "error_code": "worker_error",
            }), flush=True)
        else:
            print(json.dumps({
                "id": req.get("id"),
                "ok": True,
                "result": {
                    "path": path,
                    "exists": True,
                    "size": len(data),
                    "sha256": sha,
                    "matched": True,
                },
            }), flush=True)
    elif method == "shutdown":
        print(json.dumps({"id": req.get("id"), "ok": True, "result": {"shutdown": True}}), flush=True)
        break
    else:
        print(json.dumps({"id": req.get("id"), "ok": False, "error": "nope"}), flush=True)
""".strip(),
        encoding="utf-8",
    )
    return [sys.executable, str(script)]


def test_native_worker_capabilities_round_trip(tmp_path):
    with NativeWorkerClient(_fake_worker(tmp_path)) as client:
        caps = client.capabilities()

    assert caps.name == "fake-worker"
    assert caps.protocol == "json-lines-v1"
    assert "test" in caps.features


def test_native_worker_errors_on_failed_response(tmp_path):
    with NativeWorkerClient(_fake_worker(tmp_path)) as client:
        with pytest.raises(NativeWorkerError, match="nope"):
            client.request("missing", {})


def test_native_worker_env_discovery(monkeypatch, tmp_path):
    command = _fake_worker(tmp_path)
    monkeypatch.setenv("TIGERCAPTURE_NATIVE_WORKER", " ".join(command))

    discovered = discover_native_worker_command()
    assert discovered is not None
    assert discovered[0] == sys.executable

    caps = get_native_worker_capabilities()
    assert caps is not None
    assert caps.name == "fake-worker"


def test_native_worker_missing_is_optional(monkeypatch):
    monkeypatch.setenv(
        "TIGERCAPTURE_NATIVE_WORKER",
        r"Z:\definitely-not-installed\tigercapture-worker.exe",
    )

    caps = get_native_worker_capabilities()
    assert caps is None


def test_native_media_helpers_round_trip(monkeypatch, tmp_path):
    command = _fake_worker(tmp_path)
    monkeypatch.setenv("TIGERCAPTURE_NATIVE_WORKER", " ".join(command))

    probe = native_media_probe(tmp_path / "clip.mp4")
    assert probe is not None
    assert probe.duration_ms == 7890
    assert probe.has_video is True
    assert probe.width == 1920

    batch = native_media_probe_many([tmp_path / "clip.mp4", tmp_path / "clip2.mp4"])
    assert batch is not None
    assert [p.duration_ms if p else 0 for p in batch] == [7890, 7890]

    media_path = tmp_path / "clip.mp4"
    media_path.write_bytes(b"fake media")
    progress_events = []
    thumbs = native_generate_timeline_thumbnails(
        media_path,
        tmp_path / "thumbs",
        on_progress=progress_events.append,
    )
    assert thumbs is not None
    assert [p.name for p in thumbs] == ["0000.png", "0001.png"]
    assert [event.current for event in progress_events] == [0, 1, 2]
    assert progress_events[-1].message == "done"

    drag = native_timeline_drag_constraints(
        [
            {"id": 10, "timeline_in_ms": 0, "timeline_out_ms": 1000, "effective_length_ms": 1000},
            {"id": 11, "timeline_in_ms": 7000, "timeline_out_ms": 9000, "effective_length_ms": 2000},
        ],
        dragged_clip_id=10,
        desired_timeline_in_ms=5200,
        snap_ms=150,
        extra_snap_targets=[5300],
    )
    assert drag is not None
    assert drag["timeline_in_ms"] == 5300
    assert drag["backend"] == "rust_worker"

    gaps = native_timeline_gaps(
        [
            {"id": 10, "timeline_in_ms": 0, "timeline_out_ms": 1000, "effective_length_ms": 1000},
            {"id": 11, "timeline_in_ms": 1500, "timeline_out_ms": 2000, "effective_length_ms": 500},
            {"id": 12, "timeline_in_ms": 3000, "timeline_out_ms": 4000, "effective_length_ms": 1000},
        ],
        min_gap_ms=1,
    )
    assert gaps is not None
    assert gaps["gap_count"] == 2
    assert gaps["gaps"][0]["duration_ms"] == 500
    assert gaps["backend"] == "rust_worker"

    trim = native_timeline_trim_plan(
        [
            {"id": 10, "timeline_in_ms": 0, "timeline_out_ms": 1000, "source_in_ms": 0, "source_out_ms": 1000},
            {"id": 12, "timeline_in_ms": 2500, "timeline_out_ms": 3500, "source_in_ms": 0, "source_out_ms": 1000},
        ],
        clip_id=10,
        mode="ripple_trim",
        edge="right",
        delta_ms=200,
    )
    assert trim is not None
    assert trim["backend"] == "rust_worker"
    assert trim["new"]["source_out_ms"] == 1200
    assert trim["shifted_clips"][0]["timeline_in_ms"] == 2700

    waveform = native_audio_waveform(tmp_path / "clip.wav")
    assert waveform is not None
    assert waveform.shape == (2, 2)

    spectrum = native_audio_spectrum(tmp_path / "clip.wav")
    assert spectrum is not None
    assert spectrum.shape == (3,)

    fixture = tmp_path / "fixture.bin"
    fixture.write_bytes(b"golden")
    expected = hashlib.sha256(b"golden").hexdigest()
    validation = native_validate_golden_fixture(
        fixture,
        expected_sha256=expected,
        min_size=3,
    )
    assert validation is not None
    assert validation["matched"] is True
    assert validation["sha256"] == expected


def test_native_worker_cancellation_error_code(monkeypatch, tmp_path):
    command = _fake_worker(tmp_path)
    monkeypatch.setenv("TIGERCAPTURE_NATIVE_WORKER", " ".join(command))
    media_path = tmp_path / "clip.mp4"
    media_path.write_bytes(b"fake media")
    cancel_token = tmp_path / "cancel"
    cancel_token.write_text("cancel", encoding="utf-8")

    with NativeWorkerClient(command) as client:
        with pytest.raises(NativeWorkerError) as exc_info:
            client.request_with_events(
                "timeline_thumbnails",
                {
                    "path": str(media_path),
                    "out_dir": str(tmp_path / "thumbs"),
                    "cancel_token_path": str(cancel_token),
                },
            )
    assert exc_info.value.code == "cancelled"
