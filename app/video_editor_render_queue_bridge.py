"""Duck-typed render queue bridge helpers for ``VideoEditorWindow``.

Keep the editor methods as thin wrappers when this module is wired into the
window. Action and AI-command routes look up the historical private method
names on the editor owner, especially ``_stage_ai_script_render_jobs`` and
``_stage_creator_assist_render_jobs``. Removing those wrappers would break
those command paths even though the implementation lives here.

Expected wrapper shape:

```
def _stage_ai_script_render_jobs(self, payload=None):
    return stage_ai_script_render_jobs(self, payload)

def _queue_creator_assist_exports(self):
    return queue_creator_assist_exports(self)

def _stage_creator_assist_render_jobs(self, bundle=None):
    return stage_creator_assist_render_jobs(self, bundle)

def _toggle_render_queue_popout(self):
    return toggle_render_queue_popout(self)
```
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


StoreFactory = Callable[[], Any]
AddJobsToStore = Callable[[Any, Mapping[str, Any]], Mapping[str, Any] | None]

RENDER_QUEUE_POPOUT_KEY = "render_queue"
RENDER_QUEUE_HOST_ATTR = "_render_queue_section_host"
RENDER_QUEUE_TITLE = "Render Queue"


def _default_store_factory() -> Any:
    from app.render_queue import RenderQueueStore

    return RenderQueueStore()


def _default_add_jobs_to_store(store: Any, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from app.capcut_apply import capcut_add_render_jobs_to_store

    return capcut_add_render_jobs_to_store(store, payload)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _render_queue_rows(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    rows = _as_mapping(payload).get("render_queue_jobs") or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _capcut_feature_disabled(owner: Any, feature_id: str) -> bool:
    checker = getattr(owner, "_capcut_feature_disabled", None)
    if callable(checker):
        try:
            return bool(checker(feature_id))
        except Exception:
            pass
    try:
        from app.capcut_features import capcut_feature_disabled

        return bool(capcut_feature_disabled(feature_id))
    except Exception:
        return False


def _capcut_disabled_reason(owner: Any, feature_id: str) -> str:
    reason = getattr(owner, "_capcut_disabled_reason", None)
    if callable(reason):
        try:
            return str(reason(feature_id))
        except Exception:
            pass
    try:
        from app.capcut_features import capcut_disabled_reason

        return str(capcut_disabled_reason(feature_id))
    except Exception:
        return f"{feature_id} is disabled."


def _job_readiness_notes(rows: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    seen: set[str] = set()
    for row in rows:
        create_kwargs = _as_mapping(row.get("create_kwargs"))
        found = False
        for source in (row, create_kwargs):
            for key in ("readiness_note", "preflight_diagnostics", "diagnostics"):
                text = " ".join(str(source.get(key) or "").split())
                if text and text not in seen:
                    notes.append(text)
                    seen.add(text)
                    found = True
                    break
            if found:
                break
    return notes


def render_queue_staging_readiness_note(
    result: Mapping[str, Any] | None,
    *,
    requested: int,
    source: str,
) -> str:
    """Return a compact status/readiness line for UI status surfaces."""

    data = _as_mapping(result)
    added = _int(data.get("added", 0), 0)
    skipped = _int(data.get("skipped", 0), 0)
    warnings = [str(row) for row in list(data.get("warnings") or []) if str(row)]
    label = {
        "ai_script": "AI script",
        "creator_assist": "Creator Assist",
    }.get(str(source), "Render Queue")
    if warnings and not added:
        return f"{label} render queue needs review: {warnings[0]}"
    if added:
        suffix = f"; skipped {skipped}" if skipped else ""
        if warnings:
            suffix = f"{suffix}; warnings {len(warnings)}"
        return f"{label} render queue ready: added {added} of {max(added, requested)} job(s){suffix}."
    if skipped:
        return f"{label} render queue unchanged: skipped {skipped} duplicate job(s)."
    return f"{label} render queue not ready: no render jobs."


def _empty_result(warning: str, *, source: str) -> dict[str, Any]:
    result = {
        "ok": False,
        "added": 0,
        "skipped": 0,
        "job_ids": [],
        "warnings": [warning],
        "requested": 0,
        "source": source,
        "section_opened": False,
        "panel_refreshed": False,
        "job_readiness_notes": [],
    }
    result["readiness_note"] = render_queue_staging_readiness_note(
        result,
        requested=0,
        source=source,
    )
    return result


class VideoEditorRenderQueueBridge:
    """Bridge a VideoEditorWindow-like owner to the Qt-free queue store.

    The owner is intentionally duck-typed. The bridge only looks for the panel
    store, optional refresh/open methods, Creator Assist analysis, and status
    flashing methods used by the existing editor.
    """

    def __init__(
        self,
        owner: Any,
        *,
        store_factory: StoreFactory | None = None,
        add_jobs_to_store: AddJobsToStore | None = None,
    ) -> None:
        self.owner = owner
        self._store_factory = store_factory or _default_store_factory
        self._add_jobs_to_store = add_jobs_to_store or _default_add_jobs_to_store

    @property
    def panel(self) -> Any:
        return getattr(self.owner, "_render_queue_panel", None)

    @property
    def host(self) -> Any:
        return getattr(self.owner, RENDER_QUEUE_HOST_ATTR, None)

    def store(self) -> Any:
        panel = self.panel
        store = getattr(panel, "_store", None) if panel is not None else None
        return store if store is not None else self._store_factory()

    def refresh_panel(self) -> bool:
        panel = self.panel
        refresh = getattr(panel, "refresh_from_store", None) if panel is not None else None
        if not callable(refresh):
            return False
        try:
            refresh()
            return True
        except Exception:
            return False

    def open_section(self, opened: bool = True) -> bool:
        opener = getattr(self.owner, "_set_collapsible_host_open", None)
        if not callable(opener):
            return False
        try:
            opener(self.host, bool(opened))
            return True
        except Exception:
            return False

    def toggle_popout(self) -> bool:
        toggle = getattr(self.owner, "_toggle_section_popout", None)
        if not callable(toggle):
            return False
        try:
            toggle(
                RENDER_QUEUE_POPOUT_KEY,
                RENDER_QUEUE_HOST_ATTR,
                RENDER_QUEUE_TITLE,
                width=820,
                height=620,
            )
            return True
        except Exception:
            return False

    def flash(self, text: str) -> None:
        flash_status = getattr(self.owner, "_flash_status", None)
        if callable(flash_status):
            try:
                flash_status(str(text))
            except Exception:
                pass

    def _stage_rows(self, rows: list[dict[str, Any]], *, source: str) -> dict[str, Any]:
        if not rows:
            return _empty_result("no render jobs", source=source)
        payload = {"render_queue_jobs": rows}
        store = self.store()
        result = dict(self._add_jobs_to_store(store, payload) or {})
        result.setdefault("job_ids", [])
        result.setdefault("warnings", [])
        result["requested"] = len(rows)
        result["source"] = source
        result["panel_refreshed"] = self.refresh_panel()
        result["section_opened"] = self.open_section(True)
        result["job_readiness_notes"] = _job_readiness_notes(rows)
        result.setdefault(
            "readiness_note",
            render_queue_staging_readiness_note(
                result,
                requested=len(rows),
                source=source,
            ),
        )
        return result

    def stage_ai_script_render_jobs(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._stage_rows(_render_queue_rows(payload), source="ai_script")

    def stage_creator_assist_render_jobs(
        self,
        bundle: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if _capcut_feature_disabled(self.owner, "apply_bundle"):
            reason = _capcut_disabled_reason(self.owner, "apply_bundle")
            result = {
                "ok": False,
                "added": 0,
                "skipped": 0,
                "job_ids": [],
                "warnings": [reason],
                "requested": 0,
                "source": "creator_assist",
                "section_opened": False,
                "panel_refreshed": False,
                "job_readiness_notes": [],
            }
            result["readiness_note"] = render_queue_staging_readiness_note(
                result,
                requested=0,
                source="creator_assist",
            )
            return result

        payload = dict(bundle or getattr(self.owner, "_creator_assist_bundle", {}) or {})
        rows = _render_queue_rows(payload)
        if not rows:
            rows = [
                dict(row)
                for row in list(getattr(self.owner, "_capcut_render_queue_jobs", []) or [])
                if isinstance(row, Mapping)
            ]
        if not rows:
            analyze = getattr(self.owner, "_analyze_creator_assist", None)
            if callable(analyze):
                try:
                    payload = dict(analyze() or {})
                except Exception as exc:
                    return _empty_result(str(exc), source="creator_assist")
                rows = _render_queue_rows(payload)
        if not rows:
            return _empty_result("no render jobs", source="creator_assist")

        result = self._stage_rows(rows, source="creator_assist")
        try:
            setattr(self.owner, "_capcut_render_queue_jobs", rows)
        except Exception:
            pass
        return result

    def queue_creator_assist_exports(self) -> dict[str, Any]:
        if _capcut_feature_disabled(self.owner, "apply_bundle"):
            reason = _capcut_disabled_reason(self.owner, "apply_bundle")
            self.flash(reason)
            result = {
                "ok": False,
                "added": 0,
                "skipped": 0,
                "job_ids": [],
                "warnings": [reason],
                "requested": 0,
                "source": "creator_assist",
                "section_opened": False,
                "panel_refreshed": False,
                "job_readiness_notes": [],
            }
            result["readiness_note"] = render_queue_staging_readiness_note(
                result,
                requested=0,
                source="creator_assist",
            )
            return result

        bundle = dict(getattr(self.owner, "_creator_assist_bundle", {}) or {})
        if not bundle:
            analyze = getattr(self.owner, "_analyze_creator_assist", None)
            if callable(analyze):
                try:
                    bundle = dict(analyze() or {})
                except Exception as exc:
                    result = _empty_result(str(exc), source="creator_assist")
                    self.flash(result["readiness_note"])
                    return result
        result = self.stage_creator_assist_render_jobs(bundle)
        self.flash(str(result.get("readiness_note") or "Creator Assist render queue updated."))
        return result


def stage_ai_script_render_jobs(
    owner: Any,
    payload: Mapping[str, Any] | None = None,
    *,
    store_factory: StoreFactory | None = None,
    add_jobs_to_store: AddJobsToStore | None = None,
) -> dict[str, Any]:
    return VideoEditorRenderQueueBridge(
        owner,
        store_factory=store_factory,
        add_jobs_to_store=add_jobs_to_store,
    ).stage_ai_script_render_jobs(payload)


def stage_creator_assist_render_jobs(
    owner: Any,
    bundle: Mapping[str, Any] | None = None,
    *,
    store_factory: StoreFactory | None = None,
    add_jobs_to_store: AddJobsToStore | None = None,
) -> dict[str, Any]:
    return VideoEditorRenderQueueBridge(
        owner,
        store_factory=store_factory,
        add_jobs_to_store=add_jobs_to_store,
    ).stage_creator_assist_render_jobs(bundle)


def queue_creator_assist_exports(
    owner: Any,
    *,
    store_factory: StoreFactory | None = None,
    add_jobs_to_store: AddJobsToStore | None = None,
) -> dict[str, Any]:
    return VideoEditorRenderQueueBridge(
        owner,
        store_factory=store_factory,
        add_jobs_to_store=add_jobs_to_store,
    ).queue_creator_assist_exports()


def open_render_queue_section(owner: Any, opened: bool = True) -> bool:
    return VideoEditorRenderQueueBridge(owner).open_section(opened)


def toggle_render_queue_popout(owner: Any) -> bool:
    return VideoEditorRenderQueueBridge(owner).toggle_popout()


__all__ = [
    "RENDER_QUEUE_HOST_ATTR",
    "RENDER_QUEUE_POPOUT_KEY",
    "RENDER_QUEUE_TITLE",
    "VideoEditorRenderQueueBridge",
    "open_render_queue_section",
    "queue_creator_assist_exports",
    "render_queue_staging_readiness_note",
    "stage_ai_script_render_jobs",
    "stage_creator_assist_render_jobs",
    "toggle_render_queue_popout",
]
