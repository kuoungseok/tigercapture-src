from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class FakeStore:
    def __init__(self) -> None:
        self.jobs: list[Any] = []
        self.load_count = 0

    def load(self) -> list[Any]:
        self.load_count += 1
        return self.jobs


class FakePanel:
    def __init__(self, store: FakeStore) -> None:
        self._store = store
        self.refresh_count = 0

    def refresh_from_store(self) -> None:
        self.refresh_count += 1


def _fake_add_calls(calls: list[dict[str, Any]]):
    def add_jobs_to_store(store: Any, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append({"store": store, "payload": payload})
        rows = list(payload.get("render_queue_jobs") or [])
        return {
            "ok": True,
            "added": len(rows),
            "skipped": 0,
            "job_ids": [f"job-{idx + 1}" for idx, _row in enumerate(rows)],
            "warnings": [],
        }

    return add_jobs_to_store


def _owner(panel: FakePanel | None = None) -> SimpleNamespace:
    host = object()
    opened: list[tuple[Any, bool]] = []
    statuses: list[str] = []
    owner = SimpleNamespace(
        _render_queue_panel=panel,
        _render_queue_section_host=host,
        _capcut_render_queue_jobs=[],
        opened=opened,
        statuses=statuses,
    )
    owner._set_collapsible_host_open = lambda opened_host, state: opened.append((opened_host, bool(state)))
    owner._flash_status = lambda text: statuses.append(str(text))
    return owner


def test_stage_ai_script_render_jobs_uses_panel_store_and_preserves_payload_readiness_note() -> None:
    from app.video_editor_render_queue_bridge import stage_ai_script_render_jobs

    store = FakeStore()
    panel = FakePanel(store)
    owner = _owner(panel)
    calls: list[dict[str, Any]] = []
    job = {
        "label": "AI cut export",
        "out_path": "debugCapture/render/ai_cut.mp4",
        "in_ms": 100,
        "out_ms": 2100,
        "diagnostics": "Professional Readiness: OK | Color Scope QA: OK",
    }

    result = stage_ai_script_render_jobs(
        owner,
        {"render_queue_jobs": [job], "ignored": True},
        add_jobs_to_store=_fake_add_calls(calls),
    )

    assert calls[0]["store"] is store
    assert calls[0]["payload"] == {"render_queue_jobs": [job]}
    assert panel.refresh_count == 1
    assert owner.opened == [(owner._render_queue_section_host, True)]
    assert result["requested"] == 1
    assert result["job_readiness_notes"] == ["Professional Readiness: OK | Color Scope QA: OK"]
    assert result["readiness_note"] == "AI script render queue ready: added 1 of 1 job(s)."


def test_stage_creator_assist_render_jobs_analyzes_missing_bundle_and_caches_payload(monkeypatch) -> None:
    from app.video_editor_render_queue_bridge import stage_creator_assist_render_jobs

    monkeypatch.delenv("TIGERCAPTURE_CAPCUT_DISABLED", raising=False)
    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_APPLY_BUNDLE_ENABLED", "1")

    store = FakeStore()
    panel = FakePanel(store)
    owner = _owner(panel)
    bundle = {
        "render_queue_jobs": [
            {
                "label": "Creator short 01",
                "out_path": "exports/short_01.mp4",
                "in_ms": 0,
                "out_ms": 15000,
                "readiness_note": "Professional Readiness: review offline media before export",
            }
        ]
    }
    owner._creator_assist_bundle = {}
    owner._analyze_creator_assist = lambda: bundle
    calls: list[dict[str, Any]] = []

    result = stage_creator_assist_render_jobs(
        owner,
        add_jobs_to_store=_fake_add_calls(calls),
    )

    assert calls[0]["payload"] == {"render_queue_jobs": bundle["render_queue_jobs"]}
    assert owner._capcut_render_queue_jobs == bundle["render_queue_jobs"]
    assert panel.refresh_count == 1
    assert owner.opened == [(owner._render_queue_section_host, True)]
    assert result["source"] == "creator_assist"
    assert result["job_readiness_notes"] == ["Professional Readiness: review offline media before export"]
    assert result["readiness_note"] == "Creator Assist render queue ready: added 1 of 1 job(s)."


def test_queue_creator_assist_exports_flashes_bridge_readiness_note(monkeypatch) -> None:
    from app.video_editor_render_queue_bridge import queue_creator_assist_exports

    monkeypatch.delenv("TIGERCAPTURE_CAPCUT_DISABLED", raising=False)
    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_APPLY_BUNDLE_ENABLED", "1")

    store = FakeStore()
    panel = FakePanel(store)
    owner = _owner(panel)
    owner._creator_assist_bundle = {
        "render_queue_jobs": [
            {
                "label": "Creator short 02",
                "out_path": "exports/short_02.mp4",
                "in_ms": 2000,
                "out_ms": 17000,
                "preflight_diagnostics": "Professional Readiness: OK",
            }
        ]
    }

    result = queue_creator_assist_exports(
        owner,
        add_jobs_to_store=_fake_add_calls([]),
    )

    assert result["added"] == 1
    assert result["job_readiness_notes"] == ["Professional Readiness: OK"]
    assert owner.statuses == ["Creator Assist render queue ready: added 1 of 1 job(s)."]


def test_render_queue_section_and_popout_glue_use_duck_typed_owner() -> None:
    from app.video_editor_render_queue_bridge import open_render_queue_section, toggle_render_queue_popout

    calls: list[tuple[Any, ...]] = []
    host = object()
    owner = SimpleNamespace(_render_queue_section_host=host)
    owner._set_collapsible_host_open = lambda opened_host, state: calls.append(("open", opened_host, state))
    owner._toggle_section_popout = lambda *args, **kwargs: calls.append(("popout", args, kwargs))

    assert open_render_queue_section(owner) is True
    assert toggle_render_queue_popout(owner) is True

    assert calls == [
        ("open", host, True),
        (
            "popout",
            ("render_queue", "_render_queue_section_host", "Render Queue"),
            {"width": 820, "height": 620},
        ),
    ]
