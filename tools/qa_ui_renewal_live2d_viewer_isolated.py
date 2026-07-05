from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _image_nonblank(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 4096:
        return False
    try:
        from PySide6.QtGui import QImage

        img = QImage(str(path))
        if img.isNull() or img.width() < 32 or img.height() < 32:
            return False
        step_x = max(1, img.width() // 32)
        step_y = max(1, img.height() // 32)
        values: list[int] = []
        for y in range(0, img.height(), step_y):
            for x in range(0, img.width(), step_x):
                c = img.pixelColor(x, y)
                values.append((int(c.red()) + int(c.green()) + int(c.blue())) // 3)
        if not values:
            return False
        return (max(values) - min(values)) > 10 and (sum(values) / len(values)) > 4
    except Exception:
        return True


def run_isolated_live2d_viewer_capture(
    *,
    media: str | Path | None = None,
    live2d_model: str | Path | None = None,
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_live2d_viewer_isolated",
    language: str = "ko",
    timeout_s: int = 90,
) -> dict[str, Any]:
    out = Path(out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(ROOT / "tools" / "qa_ui_renewal_actor_workspaces.py"),
        "--out-dir",
        str(out),
        "--language",
        language,
        "--open-live2d-viewer",
    ]
    if media:
        cmd.extend(["--media", str(media)])
    if live2d_model:
        cmd.extend(["--live2d-model", str(live2d_model)])

    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(10, int(timeout_s)),
        )
        returncode = int(proc.returncode)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = -9
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""

    nested_report_path = out / "ui_renewal_actor_workspace_qa.json"
    nested_report: dict[str, Any] = {}
    if nested_report_path.exists():
        try:
            nested_report = json.loads(nested_report_path.read_text(encoding="utf-8"))
        except Exception:
            nested_report = {}

    viewer_png = out / "live2d_viewer_action.png"
    editor_png = out / "editor_live2d_actor_action.png"
    workbench_png = out / "workbench_live2d_actor_action.png"
    viewer_ok = _image_nonblank(viewer_png)
    editor_ok = _image_nonblank(editor_png)
    workbench_ok = _image_nonblank(workbench_png)
    process_ok = returncode == 0
    ok = bool(viewer_ok and editor_ok and workbench_ok)
    warning = ""
    if ok and not process_ok:
        warning = (
            "Viewer artifact was captured, but the isolated subprocess returned "
            f"{returncode}. Keep this outside default QA until native shutdown is stable."
        )

    report = {
        "ok": ok,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "process_ok": process_ok,
        "returncode": returncode,
        "timed_out": timed_out,
        "warning": warning,
        "artifacts": {
            "live2d_viewer": str(viewer_png.resolve()) if viewer_png.exists() else "",
            "editor_live2d": str(editor_png.resolve()) if editor_png.exists() else "",
            "workbench_live2d": str(workbench_png.resolve()) if workbench_png.exists() else "",
        },
        "checks": {
            "viewer_png_nonblank": viewer_ok,
            "editor_png_nonblank": editor_ok,
            "workbench_png_nonblank": workbench_ok,
        },
        "nested_report": nested_report,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }
    report_path = out / "ui_renewal_live2d_viewer_isolated_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report"] = str(report_path.resolve())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture the Live2D Viewer in an isolated subprocess.")
    parser.add_argument("--media", default="")
    parser.add_argument("--live2d-model", default="")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "ui_renewal_live2d_viewer_isolated"))
    parser.add_argument("--language", default="ko")
    parser.add_argument("--timeout-s", type=int, default=90)
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    report = run_isolated_live2d_viewer_capture(
        media=args.media or None,
        live2d_model=args.live2d_model or None,
        out_dir=args.out_dir,
        language=args.language,
        timeout_s=args.timeout_s,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
