"""Domain slice of editing action adapter methods."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from pathlib import Path
from typing import Any

from app.actions.editor_adapter_scalars import _bool, _float, _int



class EditingReviewAdapterMixin:
    """Focused action adapter methods split from EditingAdapterMixin."""

    def focus_ui_surface(
            self,
            *,
            surface: str = "timeline",
            kind: str = "video",
            track_id: int | None = None,
            clip_id: int | None = None,
            inspector_tab: str = "",
            show_audio_mixer: bool = False,
            show_audio_scopes: bool = False,
            open_aux_window: bool = False,
        ) -> dict[str, Any]:
            """Focus real editor UI surfaces before review/evidence capture.

            This is intentionally a thin bridge over existing editor widgets.  It
            does not draw demo UI or synthesize screenshots; it only selects real
            timeline items and reveals the corresponding dock/page that the live
            editor already owns.
            """

            owner = self._require_owner()
            surface_text = str(surface or "timeline").strip().lower().replace("-", "_")
            kind_text = str(kind or "video").strip().lower()
            if kind_text not in {"video", "audio", "live2d", "spine", "actor", ""}:
                raise ValueError("kind must be video, audio, live2d, spine, or actor")
            focused: list[str] = []

            if track_id is not None:
                try:
                    if kind_text == "audio":
                        tid = _int(track_id)
                        cid = _int(clip_id) if clip_id is not None else None
                        if cid is None:
                            clips = list(getattr(self._audio_track(tid), "clips", []) or [])
                            if clips:
                                cid = _int(getattr(clips[0], "id", 0))
                        if cid is not None:
                            self.set_selection(kind="audio", track_id=tid, clip_id=cid, mode="replace")
                            selected = getattr(owner, "_on_audio_clip_selection_changed", None)
                            if callable(selected):
                                selected(tid, cid, 0, 0)
                            focused.append("audio_selection")
                        else:
                            self.select_track(kind="audio", track_id=tid)
                            focused.append("audio_track")
                    elif kind_text in {"video", ""}:
                        tid = _int(track_id)
                        cid = _int(clip_id) if clip_id is not None else None
                        if cid is None:
                            clips = list(getattr(self._video_track(tid), "clips", []) or [])
                            if clips:
                                cid = _int(getattr(clips[0], "id", 0))
                        if cid is not None:
                            self.set_selection(kind="video", track_id=tid, clip_id=cid, mode="replace")
                            focused.append("video_selection")
                        else:
                            self.select_track(kind="video", track_id=tid)
                            focused.append("video_track")
                except Exception:
                    # Review focus should not make a successful edit scenario fail.
                    pass

            refresh = getattr(owner, "_refresh_workbench", None)
            if callable(refresh):
                try:
                    refresh()
                    focused.append("workbench")
                except Exception:
                    pass

            if surface_text in {"color", "color_grade", "color_grading", "grading"}:
                show = getattr(owner, "_show_color_dock_page", None)
                if callable(show):
                    try:
                        show()
                        focused.append("color_dock")
                    except Exception:
                        pass
            elif surface_text not in {"color", "color_grade", "color_grading", "grading"}:
                switch = getattr(owner, "_switch_page", None)
                if callable(switch):
                    try:
                        switch("edit")
                    except Exception:
                        pass

            if surface_text in {"audio", "sound", "sound_editor", "audio_cleanup"} or show_audio_mixer:
                mixer = getattr(owner, "_on_audio_mixer_toggled", None)
                if callable(mixer):
                    try:
                        mixer(True)
                        focused.append("audio_mixer")
                    except Exception:
                        pass
            if surface_text in {"audio", "sound", "sound_editor", "audio_cleanup"} or show_audio_scopes:
                scopes = getattr(owner, "_on_audio_scopes_toggled", None)
                if callable(scopes):
                    try:
                        scopes(True)
                        focused.append("audio_scopes")
                    except Exception:
                        pass
                refresh_audio = getattr(owner, "_refresh_audio_workspace_panel", None)
                if callable(refresh_audio):
                    try:
                        refresh_audio()
                        focused.append("audio_workspace")
                    except Exception:
                        pass

            if surface_text in {"export", "render", "render_queue", "release"}:
                panels = getattr(owner, "_set_screenstudio_advanced_visible", None)
                if callable(panels):
                    try:
                        panels(True, quiet=True)
                        focused.append("secondary_panels")
                    except Exception:
                        pass
                set_open = getattr(owner, "_set_collapsible_host_open", None)
                host = getattr(owner, "_render_queue_section_host", None)
                if callable(set_open) and host is not None:
                    try:
                        set_open(host, True)
                        focused.append("render_queue")
                    except Exception:
                        pass
                    for attr in (
                        "_creator_assist_section_host",
                        "_ai_script_edit_section_host",
                        "_audio_workspace_section_host",
                        "_subtitle_section_host",
                    ):
                        sibling = getattr(owner, attr, None)
                        if sibling is None or sibling is host:
                            continue
                        try:
                            set_open(sibling, False)
                        except Exception:
                            pass
                scroll = getattr(owner, "_right_dock_scroll", None)
                ensure_visible = getattr(scroll, "ensureWidgetVisible", None)
                if callable(ensure_visible) and host is not None:
                    try:
                        ensure_visible(host, 0, 8)
                        focused.append("right_dock_scroll")
                    except Exception:
                        pass

            wb = getattr(owner, "_workbench_panel", None)
            tab = str(inspector_tab or "").strip().lower()
            if not tab:
                if surface_text in {"node", "nodes", "node_graph", "vfx", "ar_pbr"}:
                    tab = "fx"
                elif surface_text in {"mask", "rotoscope", "chroma", "background_removal"}:
                    tab = "mask"
                elif surface_text in {"audio", "sound", "sound_editor", "audio_cleanup"}:
                    tab = "audio"
                elif surface_text in {"metadata", "export", "render", "release"}:
                    tab = "meta"
            set_tab = getattr(wb, "_set_inspector_tab", None)
            if callable(set_tab) and tab:
                try:
                    set_tab(tab)
                    focused.append(f"inspector:{tab}")
                except Exception:
                    pass

            if open_aux_window:
                if surface_text in {"live2d", "actor", "actors"} or kind_text == "live2d":
                    opener = getattr(owner, "_open_live2d_viewer", None)
                    if callable(opener):
                        try:
                            opener()
                            focused.append("live2d_viewer")
                        except Exception:
                            pass
                elif surface_text in {"spine"} or kind_text == "spine":
                    opener = getattr(owner, "_open_spine_editor", None)
                    if callable(opener):
                        try:
                            opener()
                            focused.append("spine_editor")
                        except Exception:
                            pass

            self._process_capture_events()
            return {
                "surface": surface_text,
                "kind": kind_text or "video",
                "track_id": _int(track_id, 0) if track_id is not None else None,
                "clip_id": _int(clip_id, 0) if clip_id is not None else None,
                "focused": focused,
            }

    def stage_render_queue_jobs(
            self,
            *,
            jobs: Sequence[Mapping[str, Any]] | None = None,
            render_queue_jobs: Sequence[Mapping[str, Any]] | None = None,
            open_panel: bool = True,
            **_unused: Any,
        ) -> dict[str, Any]:
            """Stage render queue jobs through the editor's real queue path."""

            owner = self._require_owner()
            rows = list(render_queue_jobs or jobs or [])
            payload = {"render_queue_jobs": [dict(row) for row in rows if isinstance(row, Mapping)]}
            if not payload["render_queue_jobs"]:
                raise ValueError("render.queue.stage requires jobs or render_queue_jobs")

            method = getattr(owner, "_stage_ai_script_render_jobs", None)
            if callable(method):
                result = dict(method(payload) or {})
            else:
                from app.capcut_apply import capcut_add_render_jobs_to_store
                from app.render_queue import RenderQueueStore

                panel = getattr(owner, "_render_queue_panel", None)
                store = getattr(panel, "_store", None) if panel is not None else None
                if store is None:
                    store = RenderQueueStore()
                result = dict(capcut_add_render_jobs_to_store(store, payload) or {})
                if panel is not None:
                    refresh = getattr(panel, "refresh_from_store", None)
                    if callable(refresh):
                        refresh()

            if open_panel:
                try:
                    owner._set_collapsible_host_open(getattr(owner, "_render_queue_section_host", None), True)
                except Exception:
                    pass
            self._process_capture_events()
            return {
                "requested": len(payload["render_queue_jobs"]),
                "added": _int(result.get("added", 0), 0),
                "skipped": _int(result.get("skipped", 0), 0),
                "job_ids": list(result.get("job_ids") or []),
                "warnings": list(result.get("warnings") or []),
                "open_panel": bool(open_panel),
            }

    def capture_screenshot(self, *, path: str = "", target: str = "editor") -> dict[str, Any]:
            owner = self._require_owner()
            out = Path(str(path or "debugCapture/action_screenshot.png")).expanduser()
            out.parent.mkdir(parents=True, exist_ok=True)
            widget = self._capture_target_widget(owner, target)
            grab = getattr(widget, "grab", None)
            if not callable(grab):
                raise RuntimeError("capture.screenshot requires a Qt widget with grab()")
            pixmap = grab()
            if not pixmap.save(str(out)):
                raise RuntimeError(f"failed to save screenshot: {out}")
            return {"path": str(out.resolve()), "target": str(target or "editor")}

    def capture_gif(self, *, path: str = "", target: str = "editor", duration_ms: int = 3000, fps: int = 8) -> dict[str, Any]:
            owner = self._require_owner()
            method = getattr(owner, "_capture_action_gif", None)
            if not callable(method):
                return self._capture_gif_from_widget(path=path, target=target, duration_ms=duration_ms, fps=fps)
            out = method(path=str(path or ""), target=str(target or "editor"), duration_ms=max(1, _int(duration_ms, 3000)), fps=max(1, _int(fps, 8)))
            return {"path": str(out or path), "target": str(target or "editor"), "duration_ms": max(1, _int(duration_ms, 3000))}

    def list_capture_windows(
            self,
            *,
            title_contains: str = "",
            process_contains: str = "",
            pid: int = 0,
            include_invisible: bool = False,
            limit: int = 100,
        ) -> dict[str, Any]:
            from app.window_capture import list_capture_windows

            return list_capture_windows(
                title_contains=str(title_contains or ""),
                process_contains=str(process_contains or ""),
                pid=_int(pid, 0),
                include_invisible=_bool(include_invisible, False),
                limit=_int(limit, 100),
            )

    def capture_window_screenshot(
            self,
            *,
            path: str = "",
            title_contains: str = "",
            process_contains: str = "",
            pid: int = 0,
            hwnd: int = 0,
            backend: str = "auto",
            activate: bool = False,
        ) -> dict[str, Any]:
            from app.window_capture import save_window_screenshot

            return save_window_screenshot(
                path=path,
                title_contains=str(title_contains or ""),
                process_contains=str(process_contains or ""),
                pid=_int(pid, 0),
                hwnd=_int(hwnd, 0),
                backend=str(backend or "auto"),
                activate=_bool(activate, False),
            )

    def capture_window_video(
            self,
            *,
            path: str = "",
            title_contains: str = "",
            process_contains: str = "",
            pid: int = 0,
            hwnd: int = 0,
            duration_ms: int = 3000,
            fps: int = 15,
            backend: str = "auto",
            activate: bool = False,
            crf: int = 23,
        ) -> dict[str, Any]:
            from app.window_capture import record_window_video

            return record_window_video(
                path=path,
                title_contains=str(title_contains or ""),
                process_contains=str(process_contains or ""),
                pid=_int(pid, 0),
                hwnd=_int(hwnd, 0),
                duration_ms=_int(duration_ms, 3000),
                fps=_int(fps, 15),
                backend=str(backend or "auto"),
                activate=_bool(activate, False),
                crf=_int(crf, 23),
            )

    def capture_window_video_start(
            self,
            *,
            session_id: str = "",
            path: str = "",
            title_contains: str = "",
            process_contains: str = "",
            pid: int = 0,
            hwnd: int = 0,
            max_duration_ms: int = 600_000,
            fps: int = 15,
            backend: str = "auto",
            activate: bool = False,
            crf: int = 23,
        ) -> dict[str, Any]:
            from app.window_capture import start_window_video_capture

            return start_window_video_capture(
                session_id=str(session_id or ""),
                path=path,
                title_contains=str(title_contains or ""),
                process_contains=str(process_contains or ""),
                pid=_int(pid, 0),
                hwnd=_int(hwnd, 0),
                max_duration_ms=_int(max_duration_ms, 600_000),
                fps=_int(fps, 15),
                backend=str(backend or "auto"),
                activate=_bool(activate, False),
                crf=_int(crf, 23),
            )

    def capture_window_video_status(self, *, session_id: str = "") -> dict[str, Any]:
            from app.window_capture import window_video_capture_status

            return window_video_capture_status(session_id=str(session_id or ""))

    def capture_window_video_stop(self, *, session_id: str = "", wait_ms: int = 30_000) -> dict[str, Any]:
            from app.window_capture import stop_window_video_capture

            return stop_window_video_capture(
                session_id=str(session_id or ""),
                wait_ms=_int(wait_ms, 30_000),
            )

    def run_review_scenario(self, *, scenario: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
            owner = self.owner
            method = getattr(owner, "_run_review_scenario", None) if owner is not None else None
            if callable(method):
                result = method(str(scenario or ""), dict(params or {}))
                return dict(result or {})
            options = dict(params or {})
            from app.review_automation.deck_modes import normalize_deck_mode
            from app.review_automation.action_scenarios import run_action_review_scenario
            from app.review_automation.paths import (
                DEFAULT_REVIEW_OUTPUT_DIR,
                DEFAULT_REVIEW_REPORT,
                DEFAULT_REVIEW_SAMPLE_MANIFEST,
            )
            from app.review_automation.runner import build_review_automation_report

            scenario_text = str(scenario or "summary").strip() or "summary"
            deck_mode = normalize_deck_mode(str(options.pop("deck_mode", "") or scenario_text))
            project_root = Path(options.pop("project_root", Path.cwd()))
            out_dir = Path(options.pop("out_dir", DEFAULT_REVIEW_OUTPUT_DIR))
            report_path = Path(options.pop("report_path", DEFAULT_REVIEW_REPORT))
            sample_manifest = Path(options.pop("sample_manifest", DEFAULT_REVIEW_SAMPLE_MANIFEST))
            force = _bool(options.pop("force", False), False)
            run_action_scenario = _bool(options.pop("run_action_scenario", True), True)
            action_result: dict[str, Any] | None = None
            if run_action_scenario:
                action_result = run_action_review_scenario(
                    project_root=project_root,
                    out_dir=out_dir,
                    sample_manifest=sample_manifest,
                    scenario=scenario_text,
                    force=force,
                )
            report = build_review_automation_report(
                project_root=project_root,
                out_dir=out_dir,
                report_path=report_path,
                sample_manifest=sample_manifest,
                write_html=_bool(options.pop("write_html", True), True),
                write_ppt=_bool(options.pop("write_ppt", False), False),
                deck_mode=deck_mode,
                force=force,
            )
            return {
                "scenario": scenario_text,
                "deck_mode": deck_mode,
                "executed": True,
                "ok": bool(report.get("ok")),
                "action_scenario": action_result or {},
                "report_path": str(report.get("report_path") or ""),
                "output_dir": str(report.get("output_dir") or ""),
                "summary": dict(report.get("summary") or {}),
                "warnings": list(report.get("warnings") or []),
                "ignored_params": options,
            }
