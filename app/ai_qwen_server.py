"""Headless helpers for the optional bundled Qwen local AI server.

The editor already has a Qt/QProcess installer flow. This module is the small
non-UI counterpart used by QA tools and automation: check whether the
OpenAI-compatible endpoint is alive, optionally start the configured runner,
and wait for ``/models`` to respond.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
from typing import Any
import urllib.request

from app.ai_providers import QWEN_DEFAULT_ENDPOINT, QWEN_LLAMA_SERVER_COMMAND, saved_qwen_config


UrlOpen = Callable[..., Any]


@dataclass(frozen=True)
class QwenServerEnsureResult:
    ok: bool
    endpoint: str
    models_url: str
    already_running: bool = False
    process_started: bool = False
    command: str = ""
    pid: int = 0
    error: str = ""
    waited_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "endpoint": self.endpoint,
            "models_url": self.models_url,
            "already_running": bool(self.already_running),
            "process_started": bool(self.process_started),
            "command": self.command,
            "pid": int(self.pid or 0),
            "error": self.error,
            "waited_seconds": round(float(self.waited_seconds or 0.0), 3),
        }


def qwen_models_url(endpoint: str | None = None) -> str:
    base = str(endpoint or QWEN_DEFAULT_ENDPOINT).strip().rstrip("/")
    if not base:
        base = QWEN_DEFAULT_ENDPOINT.rstrip("/")
    return f"{base}/models"


def qwen_endpoint_alive(
    endpoint: str | None = None,
    *,
    timeout_seconds: float = 2.0,
    opener: UrlOpen | None = None,
) -> bool:
    url = qwen_models_url(endpoint)
    open_fn = opener or urllib.request.urlopen
    try:
        response = open_fn(url, timeout=max(0.2, float(timeout_seconds or 0.2)))
        with response:
            raw = response.read(2048)
        if not raw:
            return True
        try:
            payload = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            return True
        return isinstance(payload, dict)
    except Exception:
        return False


def qwen_server_config_from_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = dict(os.environ if env is None else env)
    saved = saved_qwen_config()
    endpoint = str(source.get("TIGERCAPTURE_QWEN_ENDPOINT") or saved.get("endpoint") or QWEN_DEFAULT_ENDPOINT).strip()
    command = str(
        source.get("TIGERCAPTURE_QWEN_RUNNER_COMMAND")
        or saved.get("runner_command")
        or QWEN_LLAMA_SERVER_COMMAND
    ).strip()
    return {"endpoint": endpoint or QWEN_DEFAULT_ENDPOINT, "command": command}


def split_runner_command(command: str) -> list[str]:
    raw = str(command or "").strip()
    if not raw:
        return []
    parts = shlex.split(raw, posix=os.name != "nt")
    return [part.strip().strip('"') for part in parts if str(part).strip()]


def start_qwen_server_process(
    command: str,
    *,
    cwd: str | Path | None = None,
    popen: Callable[..., subprocess.Popen] | None = None,
) -> subprocess.Popen:
    parts = split_runner_command(command)
    if not parts:
        raise ValueError("Qwen runner command is empty")
    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    popen_fn = popen or subprocess.Popen
    return popen_fn(
        parts,
        cwd=str(cwd or Path(__file__).resolve().parents[1]),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        startupinfo=startupinfo,
    )


def ensure_qwen_server(
    *,
    env: Mapping[str, str] | None = None,
    endpoint: str | None = None,
    command: str | None = None,
    wait_seconds: float = 25.0,
    poll_seconds: float = 0.75,
    start: bool = True,
    opener: UrlOpen | None = None,
    popen: Callable[..., subprocess.Popen] | None = None,
) -> QwenServerEnsureResult:
    config = qwen_server_config_from_env(env)
    resolved_endpoint = str(endpoint or config["endpoint"] or QWEN_DEFAULT_ENDPOINT).strip()
    resolved_command = str(command if command is not None else config["command"]).strip()
    models_url = qwen_models_url(resolved_endpoint)
    if qwen_endpoint_alive(resolved_endpoint, timeout_seconds=1.0, opener=opener):
        return QwenServerEnsureResult(
            ok=True,
            endpoint=resolved_endpoint,
            models_url=models_url,
            already_running=True,
            command=resolved_command,
        )
    if not start:
        return QwenServerEnsureResult(
            ok=False,
            endpoint=resolved_endpoint,
            models_url=models_url,
            command=resolved_command,
            error="endpoint_not_running",
        )
    process = None
    started_at = time.monotonic()
    try:
        process = start_qwen_server_process(resolved_command, popen=popen)
    except Exception as exc:
        return QwenServerEnsureResult(
            ok=False,
            endpoint=resolved_endpoint,
            models_url=models_url,
            command=resolved_command,
            error=f"{type(exc).__name__}: {exc}",
        )
    deadline = started_at + max(0.0, float(wait_seconds or 0.0))
    while time.monotonic() < deadline:
        if qwen_endpoint_alive(resolved_endpoint, timeout_seconds=1.0, opener=opener):
            return QwenServerEnsureResult(
                ok=True,
                endpoint=resolved_endpoint,
                models_url=models_url,
                process_started=True,
                command=resolved_command,
                pid=int(getattr(process, "pid", 0) or 0),
                waited_seconds=time.monotonic() - started_at,
            )
        time.sleep(max(0.1, float(poll_seconds or 0.1)))
    return QwenServerEnsureResult(
        ok=False,
        endpoint=resolved_endpoint,
        models_url=models_url,
        process_started=True,
        command=resolved_command,
        pid=int(getattr(process, "pid", 0) or 0),
        error="endpoint_start_timeout",
        waited_seconds=time.monotonic() - started_at,
    )


__all__ = [
    "QwenServerEnsureResult",
    "ensure_qwen_server",
    "qwen_endpoint_alive",
    "qwen_models_url",
    "qwen_server_config_from_env",
    "split_runner_command",
    "start_qwen_server_process",
]
