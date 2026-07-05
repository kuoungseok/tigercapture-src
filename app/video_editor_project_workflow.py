from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from app.i18n import tr


def _on_new_project(self) -> None:
    """Open the New Project dialog and reset the session."""
    from app.new_project_dialog import NewProjectDialog
    from app.project_io import _clear_editor

    # Warn if there are unsaved changes
    if self._tracks or self._audio_tracks:
        btn = QMessageBox.question(
            self,
            "New project",
            "Current project has unsaved changes.\nCreate a new project and discard the current session?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if btn != QMessageBox.StandardButton.Yes:
            return

    dlg = NewProjectDialog(self)
    if dlg.exec() != NewProjectDialog.DialogCode.Accepted:
        return
    s = dlg.result_settings
    if s is None:
        return

    # Store project settings on the editor
    try:
        from app.color_management import default_color_management

        color_management = default_color_management().to_dict()
    except Exception:
        color_management = {}
    project_settings = {
        "name": s.name,
        "canvas_width": s.width,
        "canvas_height": s.height,
        "fps": s.fps,
        "ratio_label": s.ratio_label,
        "starter_template_id": s.starter_template_id,
        "starter_template_label": s.starter_template_label,
        "color_management": color_management,
    }
    try:
        from app.screenstudio_parity import screenstudio_simple_mode_project_patch
        from app.screenstudio_polish import (
            screenstudio_default_export_settings,
            screenstudio_starter_defaults,
        )

        starter_id = str(s.starter_template_id or "blank")
        if starter_id in {"screen-recording-demo", "vertical-shorts", "product-demo"}:
            project_settings.update(screenstudio_simple_mode_project_patch(project_settings))
        elif starter_id != "blank":
            project_settings["screenstudio_polish"] = screenstudio_starter_defaults(
                s.starter_template_id
            )
        export_defaults = dict(
            project_settings.get("screenstudio_export_defaults")
            or screenstudio_default_export_settings(project_settings)
        )
        self._export_format_id = str(export_defaults.get("format_id") or self._export_format_id)
        self._export_quality_id = str(export_defaults.get("quality_id") or self._export_quality_id)
        project_settings["screenstudio_export_defaults"] = export_defaults
    except Exception:
        export_defaults = {}
    self._project_settings = project_settings

    # Apply FPS to the player reference rate
    self._player.REFERENCE_FPS = s.fps

    # Apply canvas ratio to the export defaults. Screen Studio starter
    # templates may intentionally choose a higher delivery FPS than the
    # edit timeline, so keep the computed export preset instead of
    # immediately overwriting it with project FPS.
    self._export_resolution = export_defaults.get("resolution") or (s.width, s.height)
    self._export_fps = export_defaults.get("fps") or s.fps
    if hasattr(self._player, "set_project_settings"):
        self._player.set_project_settings(self._project_settings)
    try:
        self._apply_screenstudio_simple_mode_ui()
    except Exception:
        pass
    try:
        self._refresh_format_btn_label()
        self._refresh_quality_btn_label()
        self._refresh_resolution_btn_label()
        self._refresh_fps_btn_label()
        if self.format_btn.menu() is not None:
            self._build_format_menu()
        if self.quality_btn.menu() is not None:
            self._build_quality_menu()
        if self.resolution_btn.menu() is not None:
            self._build_resolution_menu()
        if self.fps_btn.menu() is not None:
            self._build_fps_menu()
    except Exception:
        pass

    # Clear current session
    _clear_editor(self)
    self._project_path = None
    self._refresh_window_title()
    self._refresh_player_tracks()

    # Show project settings badge in toolbar
    if not hasattr(self, "_proj_info_label"):
        from PySide6.QtWidgets import QLabel as _QLabel

        self._proj_info_label = _QLabel()
        self._proj_info_label.setStyleSheet(
            "color:#8899cc; font-size:10px; padding:2px 6px;"
            "background:#202030; border-radius:3px;"
        )
        # Insert after new_project_btn in toolbar (best-effort)
        try:
            self.new_project_btn.parentWidget().layout().insertWidget(1, self._proj_info_label)
        except Exception:
            pass
    self._proj_info_label.setText(f"{s.ratio_label}  {s.width}x{s.height}  {s.fps:.3g}fps")


def _current_project_name(self) -> str:
    """Best-guess display name for the current project."""
    if self._project_path is not None:
        stem = self._project_path.stem
        if stem:
            return stem
    settings = getattr(self, "_project_settings", None) or {}
    name = str(settings.get("name") or "").strip()
    return name or "Untitled"


def _refresh_top_project_breadcrumb(self) -> None:
    from app import video_editor_localization_controller as _localization_controller

    return _localization_controller._refresh_top_project_breadcrumb(self)


def _refresh_window_title(self) -> None:
    self.setWindowTitle(f"{tr('veditor.brand')} - {self._current_project_name()}")


def _on_save_project(self) -> None:
    """Save the current session to a .tgp file."""
    from app.project_io import EXTENSION, save_project

    # Seed the save dialog with the current project name so users
    # who never rename can just hit Enter and get a sensibly-named
    # file. Falls back to the project_path's directory when we
    # already have one (= "Save As" defaults to the same folder).
    default_name = f"{self._current_project_name()}{EXTENSION}"
    if self._project_path is not None:
        default_dir = self._project_path.parent
    else:
        try:
            from app.paths import default_save_dir

            default_dir = default_save_dir()
        except Exception:
            default_dir = Path.home()
    default_path = str(Path(default_dir) / default_name)
    path, _ = QFileDialog.getSaveFileName(
        self,
        "Save project",
        default_path,
        f"TigerCapture project (*{EXTENSION});;All files (*.*)",
    )
    if not path:
        return
    try:
        save_project(self, path)
        self._project_path = Path(path)
        from app.project_io import remember_last_project

        remember_last_project(self._project_path)
        self._refresh_window_title()
        QMessageBox.information(self, "Save complete", f"Saved:\n{path}")
    except Exception as e:
        QMessageBox.warning(self, "Save failed", str(e))


def _do_autosave_legacy(self) -> None:
    """Auto-save handler for legacy autosave timer wiring."""
    from app.project_io import save_project

    try:
        if self._project_path is not None:
            autosave_path = self._project_path.with_name(
                self._project_path.stem + "~autosave.tgp"
            )
        else:
            autosave_path = Path.home() / "autosave.tgp"
        save_project(self, autosave_path)
        # Stash so the next launch can offer "resume?" - applies
        # to both the named-project autosave sibling and the
        # home-dir fallback.
        from app.project_io import remember_last_project

        remember_last_project(autosave_path)
        self._flash_status("Autosaved project")
    except Exception:
        pass  # Never interrupt the user


def _has_recoverable_project_state(self) -> bool:
    try:
        if any(getattr(t, "clips", None) for t in getattr(self, "_tracks", []) or []):
            return True
        if any(getattr(t, "clips", None) for t in getattr(self, "_audio_tracks", []) or []):
            return True
        if any(getattr(t, "clips", None) for t in getattr(self, "_spine_actor_tracks", []) or []):
            return True
        if any(getattr(t, "clips", None) for t in getattr(self, "_live2d_actor_tracks", []) or []):
            return True
        if getattr(self, "_strokes", None) or getattr(self, "_bubbles", None):
            return True
        if getattr(self, "_stickers", None):
            return True
        pool = getattr(self, "_media_pool", None)
        if pool is not None and hasattr(pool, "items") and list(pool.items()):
            return True
        sub_panel = getattr(self, "_subtitle_panel", None)
        if sub_panel is not None and hasattr(sub_panel, "layer"):
            return bool(list(sub_panel.layer.items()))
    except Exception:
        return True
    return False


def _autosave_path(self) -> Path:
    if self._project_path is not None:
        return self._project_path.with_name(self._project_path.stem + "~autosave.tgp")
    try:
        from app.paths import default_save_dir

        return default_save_dir() / "untitled~autosave.tgp"
    except Exception:
        return Path.home() / "untitled~autosave.tgp"


def _recovery_dir(self) -> Path:
    if self._project_path is not None:
        return self._project_path.parent / ".tigercapture_recovery"
    try:
        from app.paths import default_save_dir

        return default_save_dir() / ".recovery"
    except Exception:
        return Path.home() / ".tigercapture_recovery"


def _write_recovery_snapshot(self, autosave_path: Path, reason: str) -> Path | None:
    try:
        recovery_dir = self._recovery_dir()
        recovery_dir.mkdir(parents=True, exist_ok=True)
        stem = self._project_path.stem if self._project_path is not None else "untitled"
        reason_slug = "".join(ch if ch.isalnum() else "_" for ch in str(reason or "auto"))[:24]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot = recovery_dir / f"{stem}_{stamp}_{reason_slug}.tgp"
        shutil.copy2(autosave_path, snapshot)
        snapshots = sorted(
            recovery_dir.glob(f"{stem}_*.tgp"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        try:
            keep = max(12, int(os.environ.get("TIGERCAPTURE_RECOVERY_KEEP", "24")))
        except Exception:
            keep = 24
        for old in snapshots[keep:]:
            try:
                old.unlink()
            except Exception:
                pass
        return snapshot
    except Exception:
        return None


def _do_autosave(self, reason: str = "timer") -> Path | None:
    """Save a resumable autosave and a rotating recovery snapshot."""
    from app.project_io import remember_last_project, save_project

    try:
        self._record_editor_action("autosave.start", reason=reason)
        if not self._has_recoverable_project_state():
            self._record_editor_action("autosave.skip_empty", reason=reason)
            return None
        if (
            str(reason) == "timer"
            and not bool(getattr(self, "_autosave_dirty", True))
            and getattr(self, "_last_autosave_path", None) is not None
        ):
            self._record_editor_action("autosave.skip_clean", reason=reason)
            return self._last_autosave_path
        autosave_path = self._autosave_path()
        autosave_path.parent.mkdir(parents=True, exist_ok=True)
        save_project(self, autosave_path)
        self._last_autosave_path = autosave_path
        self._last_autosave_at = datetime.now()
        snapshot = self._write_recovery_snapshot(autosave_path, reason)
        remember_last_project(autosave_path)
        if str(reason) != "close":
            self._flash_status("Autosaved recovery copy")
        self._record_editor_action(
            "autosave.done",
            reason=reason,
            path=str(autosave_path),
            snapshot=str(snapshot) if snapshot is not None else "",
        )
        self._autosave_dirty = False
        return autosave_path
    except Exception as exc:
        self._record_editor_action("autosave.failed", reason=reason, error=repr(exc))
        try:
            print(f"[autosave] failed: {exc}", file=sys.stderr)
        except Exception:
            pass
    return None


def _show_recovery_candidates(self) -> None:
    """Show ranked autosave/recovery candidates and optionally open one."""
    from app.project_io import load_project, remember_last_project
    from tools.repair_project import (
        _candidate_paths_from_roots,
        audit_recovery_candidates,
    )

    roots: list[Path] = []
    if self._project_path is not None:
        roots.extend([self._project_path.parent, self._recovery_dir()])
    try:
        from app.paths import default_save_dir

        roots.append(default_save_dir())
    except Exception:
        roots.append(Path.home())

    report = audit_recovery_candidates(
        _candidate_paths_from_roots(roots),
        limit=8,
    )
    candidates = list(report.get("candidates", []) or [])
    best = report.get("best")
    if not candidates or best is None:
        self._record_editor_action("recovery.none_found")
        QMessageBox.information(
            self,
            "Recovery",
            "No autosave or recovery project was found.",
        )
        return

    from app.recovery_dialog import RecoveryCandidatesDialog

    dlg = RecoveryCandidatesDialog(report, self)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    selected = dlg.selected_candidate()
    if not selected or not selected.get("readable"):
        return
    best_path = Path(str(selected.get("path", "")))
    if not best_path.is_file():
        QMessageBox.warning(self, "Recovery failed", f"Recovery file is missing:\n{best_path}")
        return
    try:
        self._do_autosave("before_recovery_open")
        load_project(self, best_path)
        self._project_path = best_path
        remember_last_project(best_path)
        self._refresh_window_title()
        self._flash_status(f"Opened recovery: {best_path.name}")
        self._record_editor_action("recovery.opened", path=str(best_path))
    except Exception as exc:
        self._record_editor_action("recovery.failed", path=str(best_path), error=repr(exc))
        import traceback

        detail = traceback.format_exc()
        QMessageBox.warning(self, "Recovery failed", f"{exc}\n\n{detail[:800]}")


def _show_media_health(self) -> None:
    """Audit current project media/proxy state without saving first."""
    from app.media_health_dialog import (
        MediaHealthDialog,
        build_editor_media_health_doc,
        suggest_media_health_roots,
    )
    from app.media_relink import build_media_health_report
    from app.professional_readiness import build_professional_readiness_report

    while True:
        try:
            doc = build_editor_media_health_doc(self)
            roots = suggest_media_health_roots(doc, getattr(self, "_project_path", None))
            report = build_media_health_report(doc, roots)
            report["professional_readiness"] = build_professional_readiness_report(doc)
            edge_summary = getattr(type(self), "_timeline_edge_issue_summary", None)
            if edge_summary is None:
                edge_summary = getattr(self, "_timeline_edge_issue_summary", None)
            if edge_summary is None:
                from app.video_editor_window import VideoEditorWindow

                edge_summary = VideoEditorWindow._timeline_edge_issue_summary
            report["timeline_edge_cleanup"] = edge_summary(
                getattr(self, "_tracks", []),
                getattr(self, "_project_settings", None),
            )
            try:
                from app.preset_library import preset_pack_marketplace_report

                report["preset_pack_marketplace"] = preset_pack_marketplace_report()
            except Exception:
                report["preset_pack_marketplace"] = {}
        except Exception as exc:
            import traceback

            detail = traceback.format_exc()
            QMessageBox.warning(self, "Media Health failed", f"{exc}\n\n{detail[:800]}")
            return
        dlg = MediaHealthDialog(report, self)
        dlg.exec()
        changed = 0
        if getattr(dlg, "wants_timeline_cleanup", lambda: False)():
            changed = self._cleanup_timeline_micro_edges()
            if int(changed or 0) > 0:
                continue
        if getattr(dlg, "wants_relink", lambda: False)():
            self._on_relink_project_media()
        if getattr(dlg, "wants_preset_packs", lambda: False)():
            self._manage_preset_packs()
        if getattr(dlg, "wants_preset_qa", lambda: False)():
            self._show_preset_qa_report()
        if getattr(dlg, "wants_preset_corpus", lambda: False)():
            self._show_preset_application_corpus_report()
        return


def _on_relink_project_media(self) -> None:
    """Repair missing media/model paths in a project file, then optionally open it."""
    from app.media_relink import relink_project_file
    from app.media_relink_dialog import MissingMediaRelinkDialog
    from app.project_io import EXTENSION, load_project, remember_last_project

    project_path = self._project_path if self._project_path is not None else None
    if project_path is None or not Path(project_path).is_file():
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose project to relink",
            "",
            f"TigerCapture project (*{EXTENSION});;All files (*.*)",
        )
        if not path:
            return
        project_path = Path(path)

    try:
        raw_doc = json.loads(Path(project_path).read_text(encoding="utf-8"))
    except Exception as exc:
        import traceback

        detail = traceback.format_exc()
        QMessageBox.warning(self, "Relink failed", f"Could not read project:\n{exc}\n\n{detail[:800]}")
        return

    dlg = MissingMediaRelinkDialog(
        project_path=Path(project_path),
        project_doc=raw_doc,
        parent=self,
    )
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    choices = dlg.selected_choices()
    search_roots = dlg.search_roots()
    plan = dlg.plan()
    try:
        out_path, report = relink_project_file(
            project_path,
            search_roots,
            choices=choices,
        )
    except Exception as exc:
        import traceback

        detail = traceback.format_exc()
        QMessageBox.warning(self, "Relink failed", f"{exc}\n\n{detail[:800]}")
        return

    changed = int(report.get("changed", 0) or 0)
    unresolved = list(report.get("missing_after", []) or report.get("unresolved", []) or [])
    changes = list(report.get("changes", []) or [])

    def _short_path(value: str) -> str:
        try:
            return Path(value).name or str(value)
        except Exception:
            return str(value)

    changed_preview = "\n".join(
        f"- {_short_path(str(row.get('old_path', '')))} -> {_short_path(str(row.get('new_path', '')))}"
        for row in changes[:8]
    )
    unresolved_preview = "\n".join(f"- {_short_path(str(path))}" for path in unresolved[:8])
    roots_preview = "\n".join(f"- {root}" for root in search_roots[:6])
    if len(search_roots) > 6:
        roots_preview += f"\n- ... {len(search_roots) - 6} more"
    message = (
        f"Project: {Path(project_path).name}\n"
        f"Search roots: {len(search_roots)}\n"
        f"Missing before: {int(plan.get('missing_count', 0) or 0)}\n"
        f"Conflict rows reviewed: {int(plan.get('conflict_count', 0) or 0)}\n"
        f"Relinked entries: {changed}\n"
        f"Still missing: {len(unresolved)}\n"
        f"Output: {out_path}"
    )
    if roots_preview:
        message += f"\n\nSearch roots:\n{roots_preview}"
    if changed_preview:
        message += f"\n\nRelinked:\n{changed_preview}"
    if unresolved_preview:
        message += f"\n\nStill missing:\n{unresolved_preview}"

    if changed <= 0:
        QMessageBox.information(self, "Relink complete", message)
        return

    reply = QMessageBox.question(
        self,
        "Relink complete",
        message + "\n\nOpen the relinked project now? The current session will be replaced.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    try:
        self._do_autosave("before_relink_open")
        load_project(self, out_path)
        self._project_path = Path(out_path)
        remember_last_project(self._project_path)
        self._refresh_window_title()
        self._flash_status(f"Opened relinked project: {Path(out_path).name}")
    except Exception as exc:
        import traceback

        detail = traceback.format_exc()
        QMessageBox.warning(self, "Open relinked project failed", f"{exc}\n\n{detail[:800]}")


def _on_open_project(self) -> None:
    """Open a .tgp project file, replacing the current session."""
    from app.project_io import EXTENSION, load_project

    path, _ = QFileDialog.getOpenFileName(
        self,
        "Open project",
        "",
        f"TigerCapture project (*{EXTENSION});;All files (*.*)",
    )
    if not path:
        return
    reply = QMessageBox.question(
        self,
        "Open project",
        "Current session will be replaced.\nUnsaved changes may be lost.\nOpen this project?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return
    try:
        load_project(self, path)
        self._project_path = Path(path)
        from app.project_io import remember_last_project

        remember_last_project(self._project_path)
        self._refresh_window_title()
    except Exception as e:
        import traceback

        detail = traceback.format_exc()
        QMessageBox.warning(self, "Open failed", f"{e}\n\n{detail[:800]}")
