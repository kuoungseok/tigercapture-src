"""Credential storage helpers for broadcast stream keys."""
from __future__ import annotations

from typing import Any


SERVICE_NAME = "TigerStudio Broadcast"
SECRET_SCHEMA = "tigerstudio.broadcast.secret_store.v1"


def stream_key_credential_name(target_id: str, account: str = "") -> str:
    suffix = str(account or "default").strip() or "default"
    return f"stream_key:{str(target_id or '').strip() or 'custom'}:{suffix}"


def stream_key_store_status(*, backend: Any | None = None) -> dict[str, Any]:
    resolved = _resolve_backend(backend)
    return {
        "schema": SECRET_SCHEMA,
        "available": resolved is not None,
        "backend": type(resolved).__name__ if resolved is not None else "",
        "storage": "os_credential_store" if resolved is not None else "session_only",
    }


def store_stream_key(
    target_id: str,
    stream_key: str,
    *,
    account: str = "",
    backend: Any | None = None,
) -> dict[str, Any]:
    resolved = _resolve_backend(backend)
    if resolved is None:
        return _unavailable()
    name = stream_key_credential_name(target_id, account)
    resolved.set_password(SERVICE_NAME, name, str(stream_key or ""))
    return {
        "schema": SECRET_SCHEMA,
        "ok": True,
        "stored": True,
        "target_id": str(target_id or ""),
        "credential_name": name,
        "storage": "os_credential_store",
    }


def load_stream_key(
    target_id: str,
    *,
    account: str = "",
    backend: Any | None = None,
) -> dict[str, Any]:
    resolved = _resolve_backend(backend)
    if resolved is None:
        return _unavailable()
    name = stream_key_credential_name(target_id, account)
    secret = resolved.get_password(SERVICE_NAME, name)
    return {
        "schema": SECRET_SCHEMA,
        "ok": secret is not None,
        "found": secret is not None,
        "target_id": str(target_id or ""),
        "credential_name": name,
        "stream_key": str(secret or ""),
        "storage": "os_credential_store",
    }


def delete_stream_key(
    target_id: str,
    *,
    account: str = "",
    backend: Any | None = None,
) -> dict[str, Any]:
    resolved = _resolve_backend(backend)
    if resolved is None:
        return _unavailable()
    name = stream_key_credential_name(target_id, account)
    try:
        resolved.delete_password(SERVICE_NAME, name)
        deleted = True
    except Exception:
        deleted = False
    return {
        "schema": SECRET_SCHEMA,
        "ok": True,
        "deleted": deleted,
        "target_id": str(target_id or ""),
        "credential_name": name,
        "storage": "os_credential_store",
    }


def _resolve_backend(backend: Any | None) -> Any | None:
    if backend is not None:
        return backend
    try:
        import keyring  # type: ignore

        return keyring
    except Exception:
        return None


def _unavailable() -> dict[str, Any]:
    return {
        "schema": SECRET_SCHEMA,
        "ok": False,
        "available": False,
        "storage": "session_only",
        "reason": "credential_backend_unavailable",
    }
