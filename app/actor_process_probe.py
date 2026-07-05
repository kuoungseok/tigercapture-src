"""Run actor render probes outside the editor process."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from app.subprocess_utils import hidden_subprocess_kwargs


ROOT = Path(__file__).resolve().parents[1]


def _tail(text: str, *, limit: int = 1800) -> str:
    return str(text or "")[-limit:]


def _load_probe_json(stdout: str, json_path: Path) -> dict[str, Any]:
    if json_path.exists():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
    for line in reversed([line for line in str(stdout or "").splitlines() if line.strip()]):
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def run_isolated_actor_probe(
    kind: str,
    path: str,
    *,
    width: int = 256,
    height: int = 256,
    pos_ms: int = 0,
    timeout_ms: int = 25_000,
) -> dict[str, Any]:
    """Run a one-frame actor render in a child process and return JSON status."""
    started = time.perf_counter()
    out_path = Path(tempfile.gettempdir()) / f"tigercapture_actor_probe_{os.getpid()}_{int(started * 1000)}.json"
    cmd = [
        sys.executable or "python",
        str(ROOT / "tools" / "actor_isolated_probe.py"),
        str(kind),
        str(path),
        "--width",
        str(int(width)),
        "--height",
        str(int(height)),
        "--pos-ms",
        str(int(pos_ms)),
        "--out",
        str(out_path),
    ]
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1.0, float(timeout_ms) / 1000.0),
            check=False,
            **hidden_subprocess_kwargs(),
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        return {
            "ok": False,
            "kind": str(kind),
            "path": str(path),
            "status": "timeout",
            "elapsed_ms": elapsed,
            "returncode": None,
            "stdout_tail": _tail(exc.output or ""),
            "stderr_tail": _tail(exc.stderr or ""),
        }
    elapsed = int((time.perf_counter() - started) * 1000)
    payload = _load_probe_json(proc.stdout, out_path)
    status = str(payload.get("status") or ("pass" if proc.returncode == 0 else "crash"))
    payload.update({
        "ok": proc.returncode == 0 and status == "pass",
        "kind": str(kind),
        "path": str(path),
        "status": status,
        "elapsed_ms": int(payload.get("elapsed_ms", elapsed) or elapsed),
        "returncode": int(proc.returncode),
        "stdout_tail": _tail(proc.stdout),
        "stderr_tail": _tail(proc.stderr),
    })
    try:
        out_path.unlink(missing_ok=True)
    except Exception:
        pass
    return payload
