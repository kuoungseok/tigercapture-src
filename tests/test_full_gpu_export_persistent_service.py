import sys

import numpy as np


def test_full_gpu_export_service_reuses_persistent_stdio_helper(tmp_path, monkeypatch):
    from app.ar_pbr.full_gpu_export_service import (
        FULL_GPU_EXPORT_SERVICE_COMMAND_ENV,
        render_frame_via_full_gpu_export_service,
    )

    fake_service = tmp_path / "fake_persistent_full_gpu_service.py"
    fake_service.write_text(
        """
import json
import sys
from pathlib import Path
from PIL import Image

if "--probe" in sys.argv:
    print(json.dumps({"ok": True}))
    raise SystemExit(0)
if "--request" in sys.argv:
    request = json.loads(Path(sys.argv[sys.argv.index("--request") + 1]).read_text(encoding="utf-8"))
    Image.open(request["base_frame_path"]).convert("RGBA").save(request["output_frame_path"])
    print(json.dumps({"ok": True, "mode": "full_model_view_gpu_export_service", "rendered_track_count": 1, "persistent_service": False}))
    raise SystemExit(0)
if "--stdio" in sys.argv:
    for line in sys.stdin:
        payload = json.loads(line)
        request = json.loads(Path(payload["request_path"]).read_text(encoding="utf-8"))
        Image.open(request["base_frame_path"]).convert("RGBA").save(request["output_frame_path"])
        print(json.dumps({"ok": True, "mode": "full_model_view_gpu_export_service", "rendered_track_count": 1, "persistent_service": True}), flush=True)
    raise SystemExit(0)
print(json.dumps({"ok": False, "error": "missing mode"}))
raise SystemExit(2)
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv(FULL_GPU_EXPORT_SERVICE_COMMAND_ENV, f'"{sys.executable}" "{fake_service}"')

    base = np.zeros((16, 16, 3), dtype=np.uint8)
    out, diag = render_frame_via_full_gpu_export_service(
        base,
        time_ms=0,
        ar_tracks=[{"id": "avatar", "type": "vrm_avatar", "start_ms": 0, "end_ms": 1000}],
        camera_solution={},
        settings={},
    )

    assert diag["ok"] is True
    assert diag["persistent_service"] is True
    assert diag["rendered_track_count"] == 1
    assert np.asarray(out).shape[:2] == (16, 16)
