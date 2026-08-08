"""Runtime helpers for the optional local TTS sidecar."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.request import Request, urlopen
import subprocess
import time

TTS_SIDECAR_GUIDANCE_SCHEMA = "tigercapture.tts_sidecar.guidance.v1"


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _endpoint_url(endpoint: str, route: str) -> str:
    base = str(endpoint or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/{route.strip('/')}"


def tts_endpoint_health(endpoint: str, *, timeout_s: float = 0.5) -> dict[str, Any]:
    """Return a quick, non-throwing health probe for a TTS HTTP endpoint."""
    timeout = max(0.1, _float(timeout_s, 0.5))
    errors: list[str] = []
    for route in ("status", "models/info"):
        url = _endpoint_url(endpoint, route)
        if not url:
            return {"running": False, "endpoint": str(endpoint or ""), "route": route, "error": "empty endpoint"}
        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=timeout) as response:
                return {
                    "running": True,
                    "endpoint": str(endpoint or ""),
                    "route": route,
                    "status_code": int(getattr(response, "status", 200) or 200),
                    "error": "",
                }
        except Exception as exc:
            errors.append(f"{route}: {exc}")
    return {
        "running": False,
        "endpoint": str(endpoint or ""),
        "route": "",
        "status_code": 0,
        "error": "; ".join(errors[-2:]),
    }


def tts_sidecar_failure_guidance(
    state: str,
    *,
    endpoint: str = "",
    status: Mapping[str, Any] | None = None,
    health: Mapping[str, Any] | None = None,
    launch: Mapping[str, Any] | None = None,
    raw_error: str = "",
) -> dict[str, Any]:
    """Return UI-ready recovery guidance for a failed TTS sidecar connection."""
    provider = status if isinstance(status, Mapping) else {}
    root = provider.get("root") if isinstance(provider.get("root"), Mapping) else {}
    root_path = str(root.get("root") or provider.get("root_path") or "")
    error_text = str(raw_error or (health or {}).get("error") or (launch or {}).get("error") or "").strip()
    key = str(state or "unknown").strip().lower()
    actions = [
        {"id": "tts.setup.view", "label": "Open Voice Lab setup", "primary": True},
        {"id": "tts.provider.status", "label": "Refresh status", "primary": False},
    ]
    if key in {"not_installed", "provider_not_ready", "incomplete_install"}:
        title = "Voice Lab TTS sidecar is not connected"
        summary = "Connect an existing Style-Bert-VITS2 folder or run the install plan before generating voice."
        steps = [
            "Open Voice Lab and use Connect if Style-Bert-VITS2 is already installed.",
            "Use Install only when you want TigerCapture to prepare a project-managed sidecar.",
            "After connecting, press Refresh and then Start server.",
        ]
        actions.insert(1, {"id": "tts.connect_installed_sidecar", "label": "Connect existing install", "primary": False})
        actions.insert(2, {"id": "tts.install.plan", "label": "Show install plan", "primary": False})
    elif key in {"start_failed", "launch_failed"}:
        title = "Voice Lab could not start the TTS server"
        summary = "The sidecar install was found, but server_fastapi.py did not launch."
        steps = [
            "Open Voice Lab and press Start server once to see whether the sidecar opens.",
            "Check that the connected folder contains venv/Scripts/python.exe and server_fastapi.py.",
            "If the sidecar prints Python or CUDA errors, fix that install and press Refresh.",
        ]
        actions.insert(1, {"id": "tts.server.start_plan", "label": "Review start command", "primary": False})
    elif key in {"timeout", "startup_timeout"}:
        title = "Voice Lab TTS server did not become ready"
        summary = "The sidecar launched, but /status or /models/info did not answer before the timeout."
        steps = [
            "Keep the Style-Bert-VITS2 server window open until it finishes loading models.",
            "Retry Subtitles -> Track after Voice Lab shows the server as running.",
            "If model loading is slow, start the server manually first and then generate.",
        ]
        actions.insert(1, {"id": "tts.server.ensure_running", "label": "Retry server check", "primary": False})
    else:
        title = "Voice Lab TTS server is offline"
        summary = "The endpoint did not answer, so subtitle voice generation cannot continue yet."
        steps = [
            "Press Start server in Voice Lab, wait for the sidecar to finish loading, then retry.",
            "Confirm the endpoint matches the running sidecar.",
            "Use Connect if the selected Style-Bert-VITS2 folder moved.",
        ]
        actions.insert(1, {"id": "tts.server.ensure_running", "label": "Start or recheck server", "primary": False})
    return {
        "schema": TTS_SIDECAR_GUIDANCE_SCHEMA,
        "state": key,
        "title": title,
        "summary": summary,
        "endpoint": str(endpoint or provider.get("endpoint") or ""),
        "root": root_path,
        "raw_error": error_text,
        "steps": steps,
        "actions": actions,
    }


def format_tts_sidecar_guidance(guidance: Mapping[str, Any] | None, *, fallback: str = "") -> str:
    """Format guidance for action errors and QMessageBox bodies."""
    if not isinstance(guidance, Mapping):
        return str(fallback or "Voice Lab TTS sidecar is not ready.")
    lines = [
        str(guidance.get("title") or "Voice Lab TTS sidecar is not ready."),
        str(guidance.get("summary") or fallback or "").strip(),
    ]
    endpoint = str(guidance.get("endpoint") or "").strip()
    root = str(guidance.get("root") or "").strip()
    if endpoint:
        lines.append(f"Endpoint: {endpoint}")
    if root:
        lines.append(f"Install: {root}")
    steps = [str(step).strip() for step in list(guidance.get("steps") or []) if str(step).strip()]
    if steps:
        lines.append("Next steps:")
        lines.extend(f"- {step}" for step in steps[:4])
    raw = str(guidance.get("raw_error") or "").strip()
    if raw:
        lines.append(f"Last diagnostic: {raw}")
    return "\n".join(line for line in lines if line)


def start_tts_sidecar(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Launch the configured Style-Bert-VITS2 server without blocking."""
    from app.tts_setup import tts_server_start_plan

    plan = tts_server_start_plan(env)
    command = [str(part) for part in list(plan.get("command") or []) if str(part)]
    if not bool(plan.get("ready")) or len(command) < 2:
        return {
            "started": False,
            "ready": False,
            "endpoint": str(plan.get("endpoint") or ""),
            "plan": plan,
            "error": str(plan.get("message") or "TTS sidecar is not installed or connected."),
        }
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(
            command,
            cwd=str(plan.get("cwd") or "") or None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        return {
            "started": True,
            "ready": False,
            "endpoint": str(plan.get("endpoint") or ""),
            "pid": int(getattr(proc, "pid", 0) or 0),
            "command": command,
            "cwd": str(plan.get("cwd") or ""),
            "error": "",
        }
    except Exception as exc:
        return {
            "started": False,
            "ready": False,
            "endpoint": str(plan.get("endpoint") or ""),
            "command": command,
            "cwd": str(plan.get("cwd") or ""),
            "error": str(exc),
        }


def wait_for_tts_endpoint(endpoint: str, *, timeout_s: float = 90.0, poll_s: float = 1.0) -> dict[str, Any]:
    """Wait until the endpoint answers or the startup window expires."""
    started_at = time.monotonic()
    timeout = max(0.5, _float(timeout_s, 90.0))
    interval = max(0.1, _float(poll_s, 1.0))
    last = {"running": False, "endpoint": str(endpoint or ""), "error": "not checked"}
    while time.monotonic() - started_at <= timeout:
        last = tts_endpoint_health(endpoint, timeout_s=min(1.5, interval))
        if bool(last.get("running")):
            return {
                **last,
                "waited_s": round(time.monotonic() - started_at, 2),
                "timed_out": False,
            }
        time.sleep(interval)
    return {
        **last,
        "waited_s": round(time.monotonic() - started_at, 2),
        "timed_out": True,
    }


def ensure_tts_sidecar_running(
    *,
    auto_start: bool = True,
    wait_timeout_s: float = 90.0,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Check, optionally start, then wait for the local sidecar.

    The function returns a user-facing payload instead of throwing so UI and
    actions can show clear guidance.
    """
    from app.tts_setup import tts_provider_status

    status = tts_provider_status(env)
    endpoint = str(status.get("endpoint") or "")
    if not bool(status.get("installed")):
        guidance = tts_sidecar_failure_guidance(
            "provider_not_ready",
            endpoint=endpoint,
            status=status,
            raw_error=str(status.get("reason") or ""),
        )
        return {
            "ready": False,
            "running": False,
            "started": False,
            "endpoint": endpoint,
            "status": status,
            "guidance": guidance,
            "error": str(guidance.get("summary") or ""),
            "message": format_tts_sidecar_guidance(guidance),
        }

    initial = tts_endpoint_health(endpoint, timeout_s=0.5)
    if bool(initial.get("running")):
        return {
            "ready": True,
            "running": True,
            "started": False,
            "endpoint": endpoint,
            "status": status,
            "health": initial,
            "message": "TTS server is already running.",
            "error": "",
        }
    if not auto_start:
        guidance = tts_sidecar_failure_guidance(
            "server_offline",
            endpoint=endpoint,
            status=status,
            health=initial,
            raw_error=str(initial.get("error") or ""),
        )
        return {
            "ready": False,
            "running": False,
            "started": False,
            "endpoint": endpoint,
            "status": status,
            "health": initial,
            "guidance": guidance,
            "message": format_tts_sidecar_guidance(guidance),
            "error": str(guidance.get("summary") or "TTS server is not running."),
        }

    launch = start_tts_sidecar(env)
    if not bool(launch.get("started")):
        guidance = tts_sidecar_failure_guidance(
            "start_failed",
            endpoint=endpoint,
            status=status,
            health=initial,
            launch=launch,
            raw_error=str(launch.get("error") or ""),
        )
        return {
            "ready": False,
            "running": False,
            "started": False,
            "endpoint": endpoint,
            "status": status,
            "health": initial,
            "launch": launch,
            "guidance": guidance,
            "message": format_tts_sidecar_guidance(guidance),
            "error": str(guidance.get("summary") or "TTS server start failed."),
        }
    waited = wait_for_tts_endpoint(endpoint, timeout_s=wait_timeout_s, poll_s=1.0)
    ready = bool(waited.get("running"))
    guidance = None if ready else tts_sidecar_failure_guidance(
        "startup_timeout",
        endpoint=endpoint,
        status=status,
        health=waited,
        launch=launch,
        raw_error=str(waited.get("error") or ""),
    )
    return {
        "ready": ready,
        "running": ready,
        "started": True,
        "endpoint": endpoint,
        "status": status,
        "health": waited,
        "launch": launch,
        "guidance": guidance or {},
        "message": (
            "TTS server started and is ready."
            if ready
            else format_tts_sidecar_guidance(guidance)
        ),
        "error": "" if ready else str((guidance or {}).get("summary") or "TTS server startup timed out."),
    }


__all__ = [
    "ensure_tts_sidecar_running",
    "format_tts_sidecar_guidance",
    "start_tts_sidecar",
    "tts_sidecar_failure_guidance",
    "tts_endpoint_health",
    "wait_for_tts_endpoint",
]
