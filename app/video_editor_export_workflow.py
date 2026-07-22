from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication as _QApplication,
    QFileDialog as _QFileDialog,
    QMessageBox as _QMessageBox,
    QProgressDialog as _QProgressDialog,
)

from app.audio_tracks import AudioClip, AudioTrack
from app.i18n import tr
from app.video_exporter import (
    VideoExportThread,
    build_project_segments_from_clips,
    build_segments_from_clips,
    get_export_format,
    get_quality_preset,
)
from app.video_editor_export_controls import (
    build_export_format_menu,
    build_export_fps_menu,
    build_export_quality_menu,
    build_export_resolution_menu,
    refresh_export_format_btn_label,
    refresh_export_fps_btn_label,
    refresh_export_quality_btn_label,
    refresh_export_resolution_btn_label,
)


class _QtGlobalProxy:
    def __init__(self, name: str, fallback):
        self._name = name
        self._fallback = fallback

    def _target(self):
        module = sys.modules.get("app.video_editor_window")
        if module is not None:
            return getattr(module, self._name, self._fallback)
        return self._fallback

    def __getattr__(self, attr: str):
        return getattr(self._target(), attr)

    def __call__(self, *args, **kwargs):
        return self._target()(*args, **kwargs)


QApplication = _QtGlobalProxy("QApplication", _QApplication)
QFileDialog = _QtGlobalProxy("QFileDialog", _QFileDialog)
QMessageBox = _QtGlobalProxy("QMessageBox", _QMessageBox)
QProgressDialog = _QtGlobalProxy("QProgressDialog", _QProgressDialog)


def _refresh_export_button_tooltip(self) -> None:
    if not hasattr(self, "export_btn"):
        return
    try:
        note = self._screenstudio_export_badge_note()
    except Exception:
        note = "Screen Studio export defaults"
    self.export_btn.setToolTip(f"{tr('veditor.btn.export')}\n{note}")


def _refresh_quality_btn_label(self) -> None:
    refresh_export_quality_btn_label(self)


def _build_quality_menu(self) -> None:
    build_export_quality_menu(self)


def _on_quality_picked(self, quality_id: str) -> None:
    from app import tier

    quality = get_quality_preset(quality_id)
    if tier.is_locked(quality.feature_id):
        self._show_upsell(quality.feature_id, tr(quality.name_key))
        if self.quality_btn.menu() is not None:
            self._build_quality_menu()
        return
    self._export_quality_id = quality_id
    self._refresh_quality_btn_label()
    if self.quality_btn.menu() is not None:
        self._build_quality_menu()
    self._refresh_export_button_tooltip()


def _refresh_format_btn_label(self) -> None:
    refresh_export_format_btn_label(self)


def _build_format_menu(self) -> None:
    build_export_format_menu(self)


def _on_format_picked(self, format_id: str) -> None:
    from app import tier

    export_format = get_export_format(format_id)
    if tier.is_locked(export_format.feature_id):
        self._show_upsell(export_format.feature_id, tr(export_format.name_key))
        if self.format_btn.menu() is not None:
            self._build_format_menu()
        return
    self._export_format_id = format_id
    self._refresh_format_btn_label()
    if self.format_btn.menu() is not None:
        self._build_format_menu()
    self._refresh_export_button_tooltip()


def _refresh_resolution_btn_label(self) -> None:
    refresh_export_resolution_btn_label(self)


def _build_resolution_menu(self) -> None:
    build_export_resolution_menu(self)


def _on_resolution_picked(self, res) -> None:
    self._export_resolution = res
    self._refresh_resolution_btn_label()
    if self.resolution_btn.menu() is not None:
        self._build_resolution_menu()
    self._refresh_export_button_tooltip()


def _refresh_fps_btn_label(self) -> None:
    refresh_export_fps_btn_label(self)


def _build_fps_menu(self) -> None:
    build_export_fps_menu(self)


def _on_fps_picked(self, fps) -> None:
    self._export_fps = fps
    self._refresh_fps_btn_label()
    if self.fps_btn.menu() is not None:
        self._build_fps_menu()
    self._refresh_export_button_tooltip()


def _format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _screenstudio_post_export_handoff_note(self, output_path: Path) -> str:
    try:
        from app.screenstudio_polish import screenstudio_default_export_settings

        project_settings = dict(getattr(self, "_project_settings", {}) or {})
        defaults = dict(project_settings.get("screenstudio_export_defaults") or {})
        if not defaults:
            defaults = screenstudio_default_export_settings(project_settings)
    except Exception:
        defaults = {}
    actions = {str(action) for action in list(defaults.get("post_export_actions") or [])}
    notes: list[str] = []
    if "copy_path" in actions:
        try:
            QApplication.clipboard().setText(str(output_path))
            notes.append("Screen Studio handoff: export path copied to clipboard.")
        except Exception:
            notes.append("Screen Studio handoff: clipboard copy failed.")
    if "local_share_package" in actions:
        share_manifest = self._screenstudio_write_local_share_package(output_path, defaults)
        destinations = ", ".join(str(item) for item in list(defaults.get("destinations") or [])[:3])
        if destinations:
            notes.append(f"Local share package ready for {destinations}.")
        else:
            notes.append("Local share package ready.")
        if share_manifest is not None:
            notes.append(f"Share manifest: {share_manifest}")
    if "copy_share_link" in actions:
        try:
            from app.screenstudio_polish import screenstudio_build_share_link

            share = screenstudio_build_share_link(output_path, defaults)
        except Exception:
            share = {}
        provider = str(defaults.get("share_provider_label") or defaults.get("share_provider") or "share provider")
        share_url = str(share.get("share_url") or "")
        if share_url:
            try:
                QApplication.clipboard().setText(share_url)
                notes.append(f"Share-link ready through {provider}; link copied.")
            except Exception:
                notes.append(f"Share-link ready through {provider}: {share_url}")
        else:
            notes.append(f"Share-link handoff is configured through {provider}.")
    return "\n".join(notes)


def _screenstudio_write_local_share_package(self, output_path: Path, defaults: dict) -> Path | None:
    try:
        from app.screenstudio_polish import screenstudio_write_local_share_manifest

        return screenstudio_write_local_share_manifest(output_path, defaults)
    except Exception:
        return None


def _screenstudio_export_defaults_for_current_project(self) -> dict:
    try:
        from app.screenstudio_polish import screenstudio_default_export_settings

        project_settings = dict(getattr(self, "_project_settings", {}) or {})
        defaults = dict(project_settings.get("screenstudio_export_defaults") or {})
        if not defaults:
            defaults = screenstudio_default_export_settings(project_settings)
        return defaults
    except Exception:
        return {}


def _show_screenstudio_export_complete_dialog(
    self,
    output_path: Path,
    size: int,
    *,
    handoff_note: str = "",
    color_note: str = "",
    readiness_note: str = "",
) -> None:
    try:
        from app.screenstudio_polish import screenstudio_export_completion_summary

        defaults = self._screenstudio_export_defaults_for_current_project()
        notes = [
            line
            for block in (handoff_note, color_note, readiness_note)
            for line in str(block or "").splitlines()
            if line.strip()
        ]
        summary = screenstudio_export_completion_summary(output_path, defaults, notes=notes)
    except Exception:
        summary = {
            "summary_line": "Export",
            "file_name": output_path.name,
            "output_path": str(output_path),
            "action_labels": ["Reveal output", "Copy path"],
            "notes": [line for line in (handoff_note, color_note, readiness_note) if line],
            "attention": [],
        }

    info_lines = [
        str(summary.get("summary_line") or "Export complete"),
        str(output_path),
        f"Size: {_format_size(int(size or summary.get('size_bytes') or 0))}",
    ]
    if summary.get("handoff_label"):
        info_lines.append(f"Handoff: {summary.get('handoff_label')}")
    if summary.get("share_manifest_exists"):
        info_lines.append(f"Share manifest: {summary.get('share_manifest_path')}")

    details = []
    for note in list(summary.get("notes") or []):
        if str(note).strip():
            details.append(str(note))
    for attention in list(summary.get("attention") or []):
        details.append(f"Attention: {attention}")
    if not details:
        details.append("No additional readiness diagnostics.")

    box = QMessageBox(self)
    box.setWindowTitle("Export Complete")
    box.setIcon(
        QMessageBox.Icon.Warning
        if summary.get("status") == "attention"
        else QMessageBox.Icon.Information
    )
    box.setText("Export complete")
    box.setInformativeText("\n".join(info_lines))
    box.setDetailedText("\n".join(details))
    reveal_btn = box.addButton("Reveal Output", QMessageBox.ButtonRole.ActionRole)
    copy_btn = box.addButton("Copy Path", QMessageBox.ButtonRole.ActionRole)
    box.addButton(QMessageBox.StandardButton.Ok)
    box.exec()
    clicked = box.clickedButton()
    if clicked is reveal_btn:
        try:
            from app.paths import open_in_explorer

            open_in_explorer(output_path)
        except Exception as exc:
            QMessageBox.information(self, "Export Complete", f"Could not reveal output:\n{exc}")
    elif clicked is copy_btn:
        try:
            QApplication.clipboard().setText(str(output_path))
            self._flash_status("Export path copied")
        except Exception:
            pass


def _show_export_final_checklist(self, readiness_note: str, *, job_count: int = 1) -> bool:
    details = str(readiness_note or "").strip()
    actor_count = sum(len(getattr(track, "clips", []) or []) for track in getattr(self, "_spine_actor_tracks", []) or [])
    actor_count += sum(len(getattr(track, "clips", []) or []) for track in getattr(self, "_live2d_actor_tracks", []) or [])
    screenstudio_note = self._screenstudio_export_badge_note()
    summary_bits = [
        f"Jobs: {int(job_count)}",
        f"Actor clips: {actor_count}",
        screenstudio_note,
        self._color_audio_export_badge_note(),
    ]
    has_attention = bool(
        "FAIL" in details
        or "high=" in details and "high=0" not in details
        or "no recent report" in details.casefold()
        or "needs Auto Polish" in screenstudio_note
        or actor_count > 0
    )
    box = QMessageBox(self)
    box.setWindowTitle("Export Final Checklist")
    box.setIcon(QMessageBox.Icon.Warning if has_attention else QMessageBox.Icon.Information)
    box.setText("Export final checklist")
    box.setInformativeText("\n".join(summary_bits))
    box.setDetailedText(details or "No additional readiness diagnostics.")
    box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(QMessageBox.StandardButton.Ok)
    return box.exec() == QMessageBox.StandardButton.Ok


def _on_export_live2d_only(self) -> None:
    """Render Live2D actor tracks to a normal video file without a video track."""
    live2d_tracks = list(getattr(self, "_live2d_actor_tracks", []) or [])
    duration_ms = max(1, self._live2d_actor_extent_ms())
    if not live2d_tracks or duration_ms <= 1:
        QMessageBox.warning(self, tr("veditor.title"), "?대낫??Live2D ?대┰???놁뒿?덈떎.")
        return
    from app.paths import default_save_dir
    from app.video_exporter import get_export_format, get_quality_preset

    fmt = get_export_format(getattr(self, "_export_format_id", "mp4"))
    default_path = default_save_dir() / f"live2d_actor_export{fmt.extension}"
    path, _ = QFileDialog.getSaveFileName(
        self,
        tr("veditor.export.dialog_title"),
        str(default_path),
        tr(f"veditor.export.filter.{fmt.id}"),
    )
    if not path:
        return
    out = Path(path)
    if out.suffix.lower() != fmt.extension:
        out = out.with_suffix(fmt.extension)

    _res = getattr(self, "_export_resolution", None)
    width = int(_res[0]) if _res is not None else 1920
    height = int(_res[1]) if _res is not None else 1080
    fps = int(getattr(self, "_export_fps", None) or 30)
    duration_s = max(0.001, duration_ms / 1000.0)

    dlg = QProgressDialog("Live2D ?≫꽣瑜?鍮꾨뵒???뚯씪濡?援쎈뒗 以?..", None, 0, 100, self)
    dlg.setWindowTitle(tr("veditor.export.progress_title"))
    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    dlg.setMinimumDuration(0)
    dlg.setAutoClose(False)
    dlg.setAutoReset(False)
    dlg.setCancelButton(None)
    dlg.show()
    QApplication.processEvents()

    live2d_pre_rendered: list = []
    try:
        live2d_pre_rendered = VideoExportThread.pre_render_live2d_actors(
            tracks=live2d_tracks,
            source_path="",
            fps=fps,
            segments=[(0, duration_ms, 1.0)],
            progress_cb=lambda p: (dlg.setValue(min(55, int(p * 0.55))), QApplication.processEvents()),
            frame_size=(width, height),
        )
        if not live2d_pre_rendered:
            raise RuntimeError("Live2D pre-render produced no frames. 紐⑤뜽??吏?뺣맂 Live2D ?대┰?몄? ?뺤씤?섏꽭??")

        from imageio_ffmpeg import get_ffmpeg_exe
        from app.subprocess_utils import hidden_subprocess_kwargs
        import subprocess

        cmd = [
            get_ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x05060A:s={width}x{height}:r={fps}:d={duration_s:.3f}",
        ]
        for mov_path, _start, _end in live2d_pre_rendered:
            cmd.extend(["-i", str(mov_path)])

        filters: list[str] = ["[0:v]format=rgba[base0]"]
        last_label = "base0"
        for idx, (_mov_path, start_s, end_s) in enumerate(live2d_pre_rendered, start=1):
            shifted = f"l2d{idx}"
            out_label = f"v{idx}"
            start = max(0.0, float(start_s))
            end = max(start, float(end_s))
            filters.append(f"[{idx}:v]setpts=PTS+{start:.6f}/TB[{shifted}]")
            filters.append(
                f"[{last_label}][{shifted}]overlay=0:0:"
                f"enable='between(t,{start:.6f},{end:.6f})':format=auto[{out_label}]"
            )
            last_label = out_label
        filters.append(f"[{last_label}]format=yuv420p[vout]")

        quality = get_quality_preset(getattr(self, "_export_quality_id", "high"))
        cmd.extend([
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
            "-an",
        ])
        cmd.extend(fmt.build_video_args(quality))
        if fmt.extension in (".mp4", ".mov"):
            cmd.extend(["-movflags", "+faststart"])
        cmd.append(str(out))

        dlg.setLabelText("Live2D ?≫꽣 ?뚯씪 ?몄퐫??以?..")
        dlg.setValue(70)
        QApplication.processEvents()
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            **hidden_subprocess_kwargs(),
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "ffmpeg failed")[-1600:]
            raise RuntimeError(tail)
        dlg.setValue(100)
        self._record_editor_action("export.live2d_only.success", path=str(out), duration_ms=duration_ms)
        self._flash_status(f"Live2D video exported: {out.name}")
        QMessageBox.information(self, tr("veditor.title"), f"Live2D 鍮꾨뵒???뚯씪????ν뻽?듬땲??\n{out}")
    except Exception as exc:
        self._record_editor_action("export.live2d_only.failed", error=str(exc))
        self._flash_status(f"Live2D export failed: {exc}")
        QMessageBox.warning(self, tr("veditor.title"), f"Live2D 鍮꾨뵒???뚯씪 ?대낫?닿린???ㅽ뙣?덉뒿?덈떎.\n\n{exc}")
    finally:
        for mov_path, _start, _end in live2d_pre_rendered:
            try:
                Path(mov_path).unlink(missing_ok=True)
            except Exception:
                pass
        dlg.close()


def _on_export(self) -> None:
    track = self._active_track()
    if track is None:
        if self._has_live2d_actor_clips():
            self._on_export_live2d_only()
        return

    def _first_source_path_from_clips(clips) -> Path | None:
        for clip in clips or []:
            tracks = clip.nested_tracks() if hasattr(clip, "nested_tracks") else []
            if tracks:
                for child_track in tracks:
                    found = _first_source_path_from_clips(child_track)
                    if found is not None:
                        return found
            sp = getattr(clip, "source_path", None)
            if sp is not None:
                return Path(sp)
        return None

    source_path_for_export = Path(track.source_path) if track.source_path is not None else _first_source_path_from_clips(getattr(track, "clips", []) or [])
    if source_path_for_export is None:
        # If only Live2D clips exist, give a more helpful message.
        has_live2d = any(
            bool(t.clips)
            for t in getattr(self, "_live2d_actor_tracks", [])
        )
        if has_live2d:
            self._on_export_live2d_only()
        else:
            QMessageBox.warning(
                self, tr("veditor.title"), tr("veditor.export.no_source")
            )
        return
    try:
        self._rebuild_active_chain()
    except Exception:
        pass
    has_nested_or_multisource = any(
        bool(getattr(c, "is_nested_sequence", False))
        or (
            getattr(c, "source_path", None) is not None
            and track.source_path is not None
            and Path(getattr(c, "source_path")) != Path(track.source_path)
        )
        for c in (getattr(track, "clips", []) or [])
    ) or track.source_path is None
    # Phase 1.5e: drive segments from ``track.clips`` so user splits
    # + per-clip drags actually show up in the exported file.
    # ``build_segments_from_clips`` falls back to one segment per
    # clip in project-time order; for a single-clip track the
    # output is byte-equivalent to the legacy ``build_segments``.
    if has_nested_or_multisource:
        segments = build_project_segments_from_clips(track.clips)
    else:
        segments = build_segments_from_clips(
            track.clips, track.speed_segments,
        )
    export_zoom_actors = (
        self._export_track_zoom_actors_only(track)
        if has_nested_or_multisource
        else self._export_zoom_actors_for_track(track)
    )
    if not segments:
        QMessageBox.warning(
            self, tr("veditor.title"), tr("veditor.export.no_segments")
        )
        return

    def _project_ms_to_output_ms(project_ms: int) -> int | None:
        acc_ms = 0.0
        for seg_start, seg_end, seg_speed in segments:
            speed = max(float(seg_speed), 0.001)
            seg_out_ms = (int(seg_end) - int(seg_start)) / speed
            if project_ms < int(seg_start):
                return None
            if int(seg_start) <= project_ms < int(seg_end):
                return int(round(acc_ms + (project_ms - int(seg_start)) / speed))
            acc_ms += seg_out_ms
        return None

    def _remap_audio_tracks_for_export(audio_tracks: list[AudioTrack]) -> list[AudioTrack]:
        if not has_nested_or_multisource:
            return list(audio_tracks)
        import copy
        remapped: list[AudioTrack] = []
        for src_track in audio_tracks:
            out_track = AudioTrack(
                id=int(getattr(src_track, "id", 0)),
                volume=float(getattr(src_track, "volume", 1.0)),
                pan=float(getattr(src_track, "pan", 0.0)),
                label=str(getattr(src_track, "label", "") or ""),
            )
            for src_clip in getattr(src_track, "clips", []) or []:
                out_offset = _project_ms_to_output_ms(int(getattr(src_clip, "offset_ms", 0)))
                if out_offset is None:
                    continue
                dst_clip = copy.deepcopy(src_clip)
                dst_clip.offset_ms = int(out_offset)
                out_track.clips.append(dst_clip)
            if out_track.is_loaded:
                remapped.append(out_track)
        return remapped

    def _collect_nested_audio_clips(clips: list, base_ms: int = 0) -> list[AudioClip]:
        import copy
        collected: list[AudioClip] = []
        for clip in clips or []:
            clip_base = int(base_ms) + int(getattr(clip, "timeline_in_ms", 0))
            for audio_lane in getattr(clip, "nested_audio_tracks", []) or []:
                for audio_clip in audio_lane or []:
                    out_offset = _project_ms_to_output_ms(
                        clip_base + int(getattr(audio_clip, "offset_ms", 0))
                    )
                    if out_offset is None:
                        continue
                    copied = copy.deepcopy(audio_clip)
                    copied.offset_ms = int(out_offset)
                    collected.append(copied)
            nested_tracks = clip.nested_tracks() if hasattr(clip, "nested_tracks") else []
            for child_track in nested_tracks:
                collected.extend(_collect_nested_audio_clips(child_track, clip_base))
        return collected

    export_audio_tracks = _remap_audio_tracks_for_export(
        [t for t in self._audio_tracks if t.is_loaded]
    )
    nested_audio_clips = _collect_nested_audio_clips(list(getattr(track, "clips", []) or []))
    if nested_audio_clips:
        export_audio_tracks.append(
            AudioTrack(id=-9001, clips=nested_audio_clips, label="Nested audio")
        )

    from app.video_exporter import get_export_format
    fmt = get_export_format(getattr(self, "_export_format_id", "mp4"))
    default_name = f"{source_path_for_export.stem}_edited{fmt.extension}"
    default_path = source_path_for_export.parent / default_name
    filter_str = tr(f"veditor.export.filter.{fmt.id}")
    path, _ = QFileDialog.getSaveFileName(
        self,
        tr("veditor.export.dialog_title"),
        str(default_path),
        filter_str,
    )
    if not path:
        return
    out = Path(path)
    if out.suffix.lower() != fmt.extension:
        out = out.with_suffix(fmt.extension)

    # HDR Phase 2b: when the source is HDR and the container can
    # carry HEVC (mp4 / mov), offer the user a passthrough vs
    # tonemap choice. WebM doesn't support HEVC, so HDR sources
    # always tonemap into VP9 SDR there. The dialog defaults to
    # "Keep HDR" for HEVC-friendly containers because that's the
    # losslessness expectation.
    hdr_info = getattr(track, "hdr_info", None)
    hdr_passthrough = False
    if (
        hdr_info is not None
        and getattr(hdr_info, "is_hdr", False)
        and fmt.extension in (".mp4", ".mov")
    ):
        label = getattr(hdr_info, "standard_label", "HDR")
        choice = QMessageBox.question(
            self,
            tr("veditor.export.hdr_dialog.title"),
            tr("veditor.export.hdr_dialog.body", label=label),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        hdr_passthrough = choice == QMessageBox.StandardButton.Yes

    from PySide6.QtWidgets import QProgressDialog

    total = int(sum((e - s) / sp for (s, e, sp) in segments) + 0.5)
    dlg = QProgressDialog(
        tr("veditor.export.note"),
        None,
        0,
        max(1, total),
        self,
    )
    dlg.setWindowTitle(tr("veditor.export.progress_title"))
    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    dlg.setMinimumDuration(0)
    dlg.setAutoClose(False)
    dlg.setAutoReset(False)
    dlg.setCancelButton(None)
    dlg.show()

    # Typography actors live per-VideoTrack in track-local source
    # ms. Pass the active track's actors as (start, end, clip)
    # tuples ??they'll be rendered to alpha MOVs and overlaid by
    # the exporter. (Phase 5b: support actors on inactive tracks
    # via project-time mapping.)
    from app import tier
    all_actors = [
        (actor.start_ms, actor.end_ms, actor)
        for actor in getattr(track, "typography_actors", [])
        if actor.end_ms > actor.start_ms
    ]
    if all_actors and tier.is_locked("export.typography"):
        # Free user has typography placed but it can't ship in the
        # rendered file. Confirm before stripping so they know why
        # the output looks different from preview.
        choice = QMessageBox.warning(
            self,
            tr("upsell.title"),
            tr("export.typography.locked.body", count=len(all_actors)),
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Ok,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return
        text_actors_source: list = []
    else:
        text_actors_source = all_actors

    _res = getattr(self, "_export_resolution", None)
    _fps = getattr(self, "_export_fps", None)
    export_fps = int(_fps or 30)
    readiness_note = ""
    try:
        from app.media_health_dialog import build_editor_media_health_doc
        from app.professional_readiness import (
            build_professional_readiness_report,
            format_professional_readiness_diagnostics,
        )

        readiness_note = format_professional_readiness_diagnostics(
            build_professional_readiness_report(build_editor_media_health_doc(self))
        )
    except Exception:
        readiness_note = ""
    readiness_note = "\n".join(
        part for part in (readiness_note, self._color_audio_export_badge_note(), self._audio_delivery_export_note()) if part
    )
    if not self._show_export_final_checklist(readiness_note, job_count=1):
        dlg.close()
        return

    # Pre-render Live2D actors on the main thread (OpenGL requirement).
    from PySide6.QtWidgets import QApplication as _QApp
    live2d_tracks = list(getattr(self, "_live2d_actor_tracks", []) or [])
    live2d_pre_rendered: list = []
    if live2d_tracks:
        dlg.setLabelText("Pre-rendering Live2D actors...")
        dlg.setValue(0)
        live2d_pre_rendered = VideoExportThread.pre_render_live2d_actors(
            tracks=live2d_tracks,
            source_path=str(source_path_for_export),
            fps=export_fps,
            segments=segments,
            progress_cb=lambda p: (dlg.setValue(p), _QApp.processEvents()),
        )
        dlg.setLabelText(tr("veditor.export.note"))
        dlg.setValue(0)

    mmd_tracks = list(getattr(self, "_mmd_tracks", []) or [])
    mmd_pre_rendered: list = []
    if mmd_tracks:
        dlg.setLabelText("Pre-rendering MMD actors...")
        dlg.setValue(0)
        mmd_pre_rendered = VideoExportThread.pre_render_mmd_actors(
            tracks=mmd_tracks,
            source_path=str(source_path_for_export),
            fps=export_fps,
            segments=segments,
            progress_cb=lambda p: (dlg.setValue(p), _QApp.processEvents()),
            frame_size=_res,
        )
        dlg.setLabelText(tr("veditor.export.note"))
        dlg.setValue(0)

    node_item_chain_for_export = self._snapshot_node_item_chain_for_export(track)
    clip_effects_for_export = self._snapshot_clip_effects_for_export(track)
    thread = VideoExportThread(
        source_path_for_export,
        out,
        segments,
        self._subtitle_panel.subtitles(),
        self._strokes,
        cuts=track.cuts,
        fade_segments=track.fades,
        bubbles=self._bubbles,
        stickers=self._stickers,
        audio_tracks=export_audio_tracks,
        text_actors_source=text_actors_source,
        spine_actor_tracks=list(getattr(self, "_spine_actor_tracks", []) or []),
        live2d_pre_rendered=live2d_pre_rendered,
        quality_id=getattr(self, "_export_quality_id", "high"),
        format_id=getattr(self, "_export_format_id", "mp4"),
        color_grade=getattr(track, "color_grade", None),
        node_item_chain=node_item_chain_for_export,
        clip_effects=clip_effects_for_export,
        zoom_actors=export_zoom_actors,
        hdr_info=hdr_info,
        hdr_passthrough=hdr_passthrough,
        target_width=_res[0] if _res is not None else None,
        target_height=_res[1] if _res is not None else None,
        target_fps=_fps,
        render_clip_tracks=[list(getattr(track, "clips", []) or [])] if has_nested_or_multisource else None,
        force_prerender_base=has_nested_or_multisource,
        project_settings=getattr(self, "_project_settings", {}) or {},
        ar_pbr_tracks=list(getattr(self, "_ar_pbr_tracks", []) or []),
        ar_pbr_asset_descriptors=dict(
            getattr(getattr(self, "_player", None), "_ar_pbr_asset_descriptor_cache", {}) or {}
        ),
        mmd_tracks=mmd_tracks,
        mmd_pre_rendered=mmd_pre_rendered,
        motion_compositions=getattr(self, "_motion_compositions", {}) or {},
        motion_clips=list(getattr(self, "_motion_clips", []) or []),
    )
    thread.progress.connect(
        lambda cur, tot: (dlg.setMaximum(max(1, tot)), dlg.setValue(cur))
    )
    thread.stage.connect(
        lambda s: dlg.setLabelText(f"{s}\n\n{tr('veditor.export.note')}")
    )

    def _on_success(p: Path, size: int) -> None:
        dlg.close()
        color_note = ""
        try:
            from app.color_management import probe_export_color_metadata

            report = probe_export_color_metadata(
                p,
                getattr(self, "_project_settings", {}) or {},
            )
            color_note = str(report.get("diagnostics") or "")
        except Exception:
            color_note = ""
        handoff_note = self._screenstudio_post_export_handoff_note(p)
        self._show_screenstudio_export_complete_dialog(
            p,
            size,
            handoff_note=handoff_note,
            color_note=color_note,
            readiness_note=readiness_note,
        )

    def _on_error(msg: str) -> None:
        dlg.close()
        try:
            from app.render_diagnostics import format_render_failure_message

            body = format_render_failure_message(msg)
        except Exception:
            body = msg
        if readiness_note:
            body = f"{body}\n\n{readiness_note}"
        QMessageBox.critical(
            self, tr("veditor.export.failed"), body
        )

    thread.finished_success.connect(_on_success)
    thread.finished_error.connect(_on_error)
    thread.finished.connect(thread.deleteLater)
    self._export_thread = thread  # keep reference
    thread.start()


def _on_batch_export(self) -> None:
    """Open the batch-export queue dialog.

    Marker segments on the timeline ruler become individual export jobs.
    If no markers are set, a single job for the full project is created.
    Each job exports the active video track's content trimmed to that
    time range.  The user picks an output folder via QFileDialog, and the
    dialog runs the jobs sequentially.
    """
    from app.batch_export_dialog import BatchExportDialog, BatchExportItem

    track = self._active_track()
    if track is None or track.source_path is None:
        QMessageBox.warning(
            self, tr("veditor.title"), tr("veditor.export.no_source")
        )
        return

    # Collect marker-defined ranges.  Markers are stored as
    # {"ms": int, "color": str, "label": str} in self._timeline_markers.
    markers = sorted(self._timeline_markers, key=lambda m: m["ms"])
    project_end_ms = max(self._player.duration(), 1)

    if len(markers) >= 2:
        ranges = [
            (markers[i]["ms"], markers[i + 1]["ms"],
             markers[i].get("label") or f"Segment {i + 1}")
            for i in range(len(markers) - 1)
        ]
    elif len(markers) == 1:
        ranges = [(markers[0]["ms"], project_end_ms,
                   markers[0].get("label") or "Segment 1")]
    else:
        ranges = [(0, project_end_ms, "Full export")]

    # Filter out zero-length segments.
    ranges = [(s, e, lbl) for s, e, lbl in ranges if e > s]
    if not ranges:
        QMessageBox.information(
            self, "?쇨큵 ?대낫?닿린", "?대낫??援ш컙???놁뒿?덈떎."
        )
        return

    from app.video_exporter import get_export_format
    fmt = get_export_format(getattr(self, "_export_format_id", "mp4"))

    # Ask for output folder.
    out_folder = QFileDialog.getExistingDirectory(
        self, "異쒕젰 ?대뜑 ?좏깮", str(track.source_path.parent)
    )
    if not out_folder:
        return
    out_dir = Path(out_folder)
    try:
        self._rebuild_active_chain()
    except Exception:
        pass
    readiness_note = ""
    try:
        from app.media_health_dialog import build_editor_media_health_doc
        from app.professional_readiness import (
            build_professional_readiness_report,
            format_professional_readiness_diagnostics,
        )

        readiness_note = format_professional_readiness_diagnostics(
            build_professional_readiness_report(build_editor_media_health_doc(self))
        )
    except Exception:
        readiness_note = ""
    readiness_note = "\n".join(
        part for part in (readiness_note, self._color_audio_export_badge_note(), self._audio_delivery_export_note()) if part
    )
    if not self._show_export_final_checklist(readiness_note, job_count=len(ranges)):
        return
    node_item_chain_for_export = self._snapshot_node_item_chain_for_export(track)
    clip_effects_for_export = self._snapshot_clip_effects_for_export(track)

    items = [
        BatchExportItem(
            label=lbl,
            out_path=str(out_dir / f"{track.source_path.stem}_{lbl}{fmt.extension}"),
            in_ms=in_ms,
            out_ms=out_ms,
        )
        for in_ms, out_ms, lbl in ranges
    ]

    # Per-segment export factory passed to BatchExportDialog.
    # Returns a QThread with .start() and .finished signal.
    def _export_fn(in_ms: int, out_ms: int, out_path: str, progress_cb=None):
        from app.video_exporter import VideoExportThread, build_segments_from_clips

        segments = build_segments_from_clips(track.clips, track.speed_segments)
        trimmed = []
        trimmed_effects = []
        for idx, (seg_start, seg_end, speed) in enumerate(segments):
            s = max(seg_start, in_ms)
            e = min(seg_end, out_ms)
            if e > s:
                trimmed.append((s, e, speed))
                if clip_effects_for_export and idx < len(clip_effects_for_export):
                    trimmed_effects.append(clip_effects_for_export[idx])
                else:
                    trimmed_effects.append(None)
        if not trimmed:
            trimmed = [(in_ms, out_ms, 1.0)]
            trimmed_effects = [None]

        mmd_tracks = list(getattr(self, "_mmd_tracks", []) or [])
        mmd_pre_rendered = []
        if mmd_tracks:
            export_fps = int(getattr(self, "_export_fps", None) or 30)
            export_size = getattr(self, "_export_resolution", None)
            mmd_pre_rendered = VideoExportThread.pre_render_mmd_actors(
                tracks=mmd_tracks,
                source_path=str(track.source_path),
                fps=export_fps,
                segments=trimmed,
                progress_cb=(
                    (lambda p: progress_cb(min(35, int(p * 0.35))))
                    if progress_cb is not None
                    else None
                ),
                frame_size=export_size,
            )

        _t = VideoExportThread(
            track.source_path,
            Path(out_path),
            trimmed,
            self._subtitle_panel.subtitles(),
            self._strokes,
            cuts=track.cuts,
            fade_segments=track.fades,
            bubbles=self._bubbles,
            stickers=self._stickers,
            audio_tracks=[_a for _a in self._audio_tracks if _a.is_loaded],
            text_actors_source=[],
            quality_id=getattr(self, "_export_quality_id", "high"),
            format_id=getattr(self, "_export_format_id", "mp4"),
            color_grade=getattr(track, "color_grade", None),
            node_item_chain=node_item_chain_for_export,
            clip_effects=trimmed_effects,
            zoom_actors=self._export_zoom_actors_for_track(track),
            project_settings=getattr(self, "_project_settings", {}) or {},
            ar_pbr_tracks=list(getattr(self, "_ar_pbr_tracks", []) or []),
            ar_pbr_asset_descriptors=dict(
                getattr(getattr(self, "_player", None), "_ar_pbr_asset_descriptor_cache", {}) or {}
            ),
            mmd_tracks=mmd_tracks,
            mmd_pre_rendered=mmd_pre_rendered,
            motion_compositions=getattr(self, "_motion_compositions", {}) or {},
            motion_clips=list(getattr(self, "_motion_clips", []) or []),
        )
        if progress_cb is not None:
            _t.progress.connect(
                lambda cur, tot: progress_cb(int(cur * 100 / max(tot, 1)))
            )
        return _t

    panel = getattr(self, "_render_queue_panel", None)
    if panel is not None:
        panel.queue_items(
            items,
            _export_fn,
            project_path=str(getattr(self, "_project_path", "") or ""),
            source_path=str(track.source_path),
            format_id=getattr(self, "_export_format_id", "mp4"),
            quality_id=getattr(self, "_export_quality_id", "high"),
            project_settings=getattr(self, "_project_settings", {}) or {},
            preflight_diagnostics=readiness_note,
            auto_start=True,
        )
        self._flash_status(f"Queued {len(items)} render job(s)")
        return

    dlg = BatchExportDialog(items, _export_fn, parent=self)
    dlg.exec()
