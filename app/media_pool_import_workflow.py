from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QWidget,
)

from app.i18n import tr
from app.media_pool import (
    GRID_H,
    GRID_W,
    LIST_ROW_H,
    LIST_THUMB_H,
    LIST_THUMB_W,
    MEDIA_EXTS,
    MMD_MOTION_EXTS,
    ROLE_MMD_BADGE,
    ROLE_PERFORMANCE_SOURCE,
    THUMB_SIZE,
    _YouTubeImportThread,
    _auto_polish_report_for_video,
    _badge_label_for_path,
    _draw_actor_qa_badge,
    _draw_auto_polish_badge,
    _draw_hdr_badge,
    _draw_kind_badge,
    _draw_proxy_badge,
    _format_duration,
    _is_3d_import_path,
    _kind_for_path,
    _make_ar_pbr_thumbnail,
    _make_audio_thumbnail,
    _make_image_list_thumbnail,
    _make_image_thumbnail,
    _make_mmd_thumbnail,
    _make_spine_thumbnail,
    _make_video_list_thumbnail,
    _make_video_thumbnail,
    _make_vrm_avatar_thumbnail,
    _media_pool_hdr_probe_enabled,
    _media_pool_item_text,
    _mmd_badge_label_for_path,
    _mmd_kind_name_for_path,
    _placeholder_pixmap,
    _probe_duration_ms,
    _proxy_state_for_video,
)
from app.image_media import DEFAULT_IMAGE_DURATION_MS

def eventFilter(self, obj, event):
    if obj in (
        getattr(self, "_featured_host", None),
        getattr(self, "_featured_thumb", None),
        getattr(self, "_featured_title", None),
        getattr(self, "_featured_meta", None),
    ):
        event_type = event.type()
        if event_type == event.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:
            self._featured_press_global = None
            if self._activate_featured_item():
                event.accept()
                return True
        if event_type == event.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._featured_press_global = self._event_global_pos(event)
            event.accept()
            return True
        if (
            event_type == event.Type.MouseMove
            and self._featured_press_global is not None
            and (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            from PySide6.QtWidgets import QApplication

            delta = self._event_global_pos(event) - self._featured_press_global
            if delta.manhattanLength() >= QApplication.startDragDistance():
                self._featured_press_global = None
                if self._begin_featured_drag():
                    event.accept()
                    return True
        if event_type == event.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            self._featured_press_global = None
            event.accept()
            return True
    return QWidget.eventFilter(self, obj, event)

def add_path(self, path: Path | str) -> bool:
    """Register a single media path. Returns True if added (False
    if duplicate or filtered out by extension)."""
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        return False
    if p.suffix.lower() not in MEDIA_EXTS:
        return False
    key = str(p)
    if key in self._registered:
        return False
    self._registered.add(key)

    kind = _kind_for_path(p)
    dur_ms = DEFAULT_IMAGE_DURATION_MS if kind == "I" else _probe_duration_ms(p)
    dur_str = _format_duration(dur_ms)
    # Compact display text for the narrow pool; full file identity stays in tooltip/data.
    item = QListWidgetItem(_media_pool_item_text(p, dur_str, self._view_mode))
    item.setData(Qt.ItemDataRole.UserRole, key)
    item.setData(Qt.ItemDataRole.UserRole + 2, kind)
    item.setData(Qt.ItemDataRole.UserRole + 3, int(dur_ms or 0))
    item.setData(Qt.ItemDataRole.UserRole + 7, _proxy_state_for_video(p) if kind == "V" else "")
    item.setData(ROLE_PERFORMANCE_SOURCE, False)
    if kind == "M":
        item.setData(ROLE_MMD_BADGE, _mmd_badge_label_for_path(p))
    item.setToolTip(f"{key}\n{dur_str}" if dur_str else key)
    if kind == "3":
        item.setData(Qt.ItemDataRole.UserRole + 8, "support_deferred")
        item.setToolTip(
            f"{item.toolTip() or key}\n"
            "3D support: checked on preview/place; media scan stays lightweight."
        )
    elif kind == "R":
        item.setData(Qt.ItemDataRole.UserRole + 8, "avatar_target")
        item.setToolTip(
            f"{item.toolTip() or key}\n"
            "VRM Avatar Target: use as VTuber Studio avatar. "
            "The VRM file itself is not rendered directly as Program Output."
        )
    elif kind == "M":
        item.setData(Qt.ItemDataRole.UserRole + 8, "mmd_asset")
        item.setToolTip(
            f"{item.toolTip() or key}\n"
            f"{_mmd_kind_name_for_path(p)} badge: {_mmd_badge_label_for_path(p)}\n"
            "MMD asset: PMX/PMD/PBX models and VMD motions can be paired on MMD tracks."
        )
    if self._view_mode == "list":
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        item.setSizeHint(QSize(0, LIST_ROW_H))
    else:
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        item.setSizeHint(QSize(GRID_W, GRID_H))
    # Pick a thumbnail strategy by media kind: video → first frame,
    # audio → stylised waveform-bar placeholder. Stamp a V / A
    # badge on the corner so the kind reads at a glance.
    if kind == "V":
        base_thumb = _make_video_thumbnail(p) or _placeholder_pixmap()
    elif kind == "A":
        base_thumb = _make_audio_thumbnail(p)
    elif kind == "I":
        base_thumb = _make_image_thumbnail(p) or _placeholder_pixmap()
    elif kind == "S":
        base_thumb = _make_spine_thumbnail()
    elif kind == "R":
        base_thumb = _make_vrm_avatar_thumbnail()
    elif kind == "M":
        base_thumb = _make_mmd_thumbnail()
    elif kind == "3":
        base_thumb = _make_ar_pbr_thumbnail()
    else:
        base_thumb = _placeholder_pixmap()
    thumb = _draw_kind_badge(base_thumb, kind, _badge_label_for_path(kind, p))
    actor_qa_tip = ""
    if kind == "S":
        try:
            from app.actor_qa_status import actor_status_badge, actor_status_for_path, actor_status_tooltip

            row = actor_status_for_path(self._actor_qa_status, p)
            item.setData(Qt.ItemDataRole.UserRole + 5, row)
            label, color = actor_status_badge(row)
            thumb = _draw_actor_qa_badge(thumb, label, color)
            actor_qa_tip = actor_status_tooltip(row)
        except Exception:
            actor_qa_tip = ""
    # HDR probe is opt-in here. Media Pool ingest happens during
    # project/open flows, and launching ffmpeg once per video made
    # Windows flash small console title bars. Export/QA can still
    # run authoritative color probes when needed.
    hdr_info = None
    auto_polish_report = {}
    if kind == "V" and _media_pool_hdr_probe_enabled():
        try:
            from app.hdr_probe import probe_hdr
            hdr_info = probe_hdr(p)
            if hdr_info.is_hdr:
                thumb = _draw_hdr_badge(thumb, hdr_info.standard_label)
        except Exception:
            # Probe failure is non-fatal — clip still loads as SDR.
            hdr_info = None
        auto_polish_report = _auto_polish_report_for_video(p, int(dur_ms or 0))
    item.setData(Qt.ItemDataRole.UserRole + 4, base_thumb)
    item.setData(Qt.ItemDataRole.UserRole + 6, auto_polish_report)
    if kind == "V":
        thumb = _draw_proxy_badge(thumb, _proxy_state_for_video(p))
        thumb = _draw_auto_polish_badge(thumb, auto_polish_report)
    if self._view_mode == "list" and kind == "V":
        item.setIcon(QIcon(_make_video_list_thumbnail(p) or thumb))
    elif self._view_mode == "list" and kind == "I":
        item.setIcon(QIcon(_make_image_list_thumbnail(p) or thumb))
    else:
        item.setIcon(QIcon(thumb))
    # Stash the probe result on the item so the workbench / future
    # decode paths can read it without re-probing.
    if hdr_info is not None:
        item.setData(Qt.ItemDataRole.UserRole + 1, hdr_info)
        if hdr_info.is_hdr:
            item.setToolTip(
                f"{key}\n{dur_str}\n[{hdr_info.standard_label}] "
                f"transfer={hdr_info.transfer or '?'}, "
                f"primaries={hdr_info.primaries or '?'}, "
                f"pixfmt={hdr_info.pix_fmt or '?'}\n"
                "Note: preview decoded as SDR (HDR Phase 1 pending)"
                if dur_str else
                f"{key}\n[{hdr_info.standard_label}]"
            )
    if actor_qa_tip:
        base_tip = item.toolTip() or key
        item.setToolTip(f"{base_tip}\n{actor_qa_tip}")
    if auto_polish_report and int(auto_polish_report.get("event_count", 0) or 0) > 0:
        counts = auto_polish_report.get("counts", {}) or {}
        labels = ", ".join(auto_polish_report.get("hotkey_labels", []) or [])
        ap_tip = (
            f"Auto Polish: {int(auto_polish_report.get('readiness', 0) or 0)}% ready, "
            f"{int(auto_polish_report.get('auto_zoom_count', 0) or 0)} zoom window(s)\n"
            f"click {counts.get('click', 0)} / drag {counts.get('drag', 0)} / "
            f"hotkey {counts.get('hotkey', 0) + counts.get('key', 0)}"
            + (f"\nkeys: {labels}" if labels else "")
        )
        item.setToolTip(f"{item.toolTip() or key}\n{ap_tip}")
    self._list.addItem(item)
    self._sort_items()
    if not self._featured_path:
        self._list.setCurrentItem(item)
        self._set_featured_item(item)
    self._apply_filter()
    self._status_label.setText(f"Imported: {p.name}")
    self.item_added.emit(key)
    return True

def import_3d_paths(self, paths: list[str] | tuple[str, ...]) -> int:
    """Import model/actor assets through the 3D import route.

    This intentionally excludes VMD. Motion files are scoped to the MMD
    Actor Editor's motion library so the general Media Pool keeps showing
    placeable actors/assets only.
    """
    added = 0
    skipped = 0
    skipped_motion = 0
    for raw_path in paths or []:
        p = Path(raw_path).expanduser().resolve()
        if p.suffix.casefold() in MMD_MOTION_EXTS:
            skipped_motion += 1
            continue
        if not _is_3d_import_path(p):
            skipped += 1
            continue
        if self.add_path(p):
            added += 1
        else:
            skipped += 1
    if added:
        suffix = ""
        if skipped or skipped_motion:
            suffix = f", skipped {skipped + skipped_motion}"
        self._set_status_message(f"Imported {added} 3D/MMD asset(s){suffix}", transient_ms=1800)
    elif skipped_motion:
        self._set_status_message(
            "VMD motions are added from the MMD Actor Editor motion library",
            transient_ms=2200,
        )
    elif skipped:
        self._set_status_message("No supported 3D/MMD asset selected", transient_ms=1800)
    return added

def dropEvent(self, event: QDropEvent) -> None:
    self._set_drop_state("")
    md = event.mimeData()
    if not md.hasUrls():
        self._status_label.hide()
        event.ignore()
        return
    added_any = False
    attempted = 0
    added = 0
    for url in md.urls():
        if not url.isLocalFile():
            continue
        attempted += 1
        if self.add_path(url.toLocalFile()):
            added_any = True
            added += 1
    if added_any:
        event.acceptProposedAction()
        skipped = max(0, attempted - added)
        self._set_status_message(
            f"Imported {added} media file(s)" + (f", skipped {skipped}" if skipped else ""),
            transient_ms=1600,
        )
    else:
        self._set_status_message("No supported new media found in drop", transient_ms=1600)
        event.ignore()

def _show_item_context_menu(self, item: QListWidgetItem, global_pos: QPoint) -> None:
    if item is None:
        self._show_context_menu(global_pos)
        return
    self._list.setCurrentItem(item)
    menu = QMenu(self)
    kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "?")
    perf_enabled = bool(item.data(ROLE_PERFORMANCE_SOURCE))
    path = str(item.data(Qt.ItemDataRole.UserRole) or "")
    act_perf = None
    if kind == "V":
        act_perf = menu.addAction(
            "Clear Performance Source" if perf_enabled else "Mark as Performance Source"
        )
        act_perf.setCheckable(True)
        act_perf.setChecked(perf_enabled)
    act_avatar_target = None
    act_open_studio = None
    act_vseeface_avatar = None
    if kind == "R":
        act_avatar_target = menu.addAction("Use as Avatar Target")
        act_open_studio = menu.addAction("Open VTuber Studio")
        act_vseeface_avatar = menu.addAction("Set as VRM / VSeeFace Bridge Avatar")
    act_auto_polish = None
    report = item.data(Qt.ItemDataRole.UserRole + 6)
    if isinstance(report, dict) and int(report.get("event_count", 0) or 0) > 0:
        act_auto_polish = menu.addAction("Apply Auto Polish")
    act_remove = menu.addAction(tr("media_pool.btn.remove"))
    menu.addSeparator()
    act_load = menu.addAction(tr("media_pool.menu.load_files"))
    act_youtube = menu.addAction("Import YouTube URL as MP4")
    act_import_3d = menu.addAction("Import 3D / MMD Asset...")
    chosen = menu.exec(global_pos)
    if chosen is None:
        return
    if act_perf is not None and chosen is act_perf:
        self._set_item_performance_source(item, not perf_enabled)
        return
    if act_avatar_target is not None and chosen is act_avatar_target:
        if path:
            self._status_label.setText(f"Using VRM avatar target: {Path(path).name}")
            self.avatar_target_requested.emit(path)
        return
    if act_open_studio is not None and chosen is act_open_studio:
        if path:
            self._status_label.setText(f"Opening VTuber Studio for: {Path(path).name}")
            self.vtuber_studio_requested.emit(path)
        return
    if act_vseeface_avatar is not None and chosen is act_vseeface_avatar:
        if path:
            self._status_label.setText(f"Set VRM / VSeeFace avatar: {Path(path).name}")
            self.avatar_target_requested.emit(path)
        return
    if act_auto_polish is not None and chosen is act_auto_polish:
        self._on_auto_polish_item_requested(item)
        return
    if chosen is act_remove:
        if path:
            self.remove_path(path)
        return
    if chosen is act_load:
        self._open_file_dialog()
        return
    if chosen is act_youtube:
        self._open_youtube_url_dialog()
        return
    if chosen is act_import_3d:
        self._open_3d_import_dialog()
        return

def _open_youtube_url_dialog(self) -> None:
    if self._youtube_import_thread is not None and self._youtube_import_thread.isRunning():
        self._status_label.setText("YouTube import is already running")
        return
    url, ok = QInputDialog.getText(
        self,
        "Import YouTube URL",
        "YouTube URL\n권리가 있거나 사용 허가된 영상만 가져오세요:",
    )
    if not ok:
        return
    url = str(url or "").strip()
    if not url:
        return
    from app.youtube_import import is_youtube_url, youtube_import_available

    if not is_youtube_url(url):
        QMessageBox.warning(self, "Import YouTube URL", "YouTube 주소만 지원합니다.")
        return
    if not youtube_import_available():
        QMessageBox.information(
            self,
            "Import YouTube URL",
            "yt-dlp가 설치되어 있지 않습니다.\n\n"
            "현재 가상환경에 yt-dlp를 설치하면 YouTube URL을 MP4로 가져올 수 있습니다:\n"
            ".\\.venv\\Scripts\\python.exe -m pip install yt-dlp",
        )
        return
    from app.youtube_import import youtube_quality_choices, youtube_quality_label

    quality_rows = youtube_quality_choices()
    quality_labels = [label for _preset_id, label in quality_rows]
    selected_label, quality_ok = QInputDialog.getItem(
        self,
        "YouTube Import Quality",
        "Download quality:",
        quality_labels,
        0,
        False,
    )
    if not quality_ok:
        return
    quality_lookup = {label: preset_id for preset_id, label in quality_rows}
    quality = quality_lookup.get(str(selected_label), "auto")
    quality_label = youtube_quality_label(quality)
    try:
        from app.paths import default_save_dir
        out_root = default_save_dir()
    except Exception:
        out_root = Path.home() / "Videos" / "Tiger Studio"

    self._youtube_import_progress = QProgressDialog(
        "YouTube 영상을 MP4로 가져오는 중...",
        None,
        0,
        100,
        self,
    )
    self._youtube_import_progress.setLabelText(
        f"YouTube MP4 import starting...\nQuality: {quality_label}"
    )
    self._youtube_import_progress.setWindowTitle("Import YouTube URL")
    self._youtube_import_progress.setWindowModality(Qt.WindowModality.WindowModal)
    self._youtube_import_progress.setMinimumDuration(0)
    self._youtube_import_progress.setAutoClose(False)
    self._youtube_import_progress.setAutoReset(False)
    self._youtube_import_progress.setCancelButton(None)
    self._youtube_import_progress.show()

    self._youtube_import_thread = _YouTubeImportThread(url, out_root, quality, self)
    self._youtube_import_thread.progress.connect(self._on_youtube_import_progress)
    self._youtube_import_thread.done.connect(self._on_youtube_import_done)
    self._youtube_import_thread.failed.connect(self._on_youtube_import_failed)
    self._youtube_import_thread.finished.connect(self._cleanup_youtube_import_thread)
    self._status_label.setText(f"YouTube import started ({quality_label})")
    self._youtube_import_thread.start()

def _set_view_mode(self, mode: str) -> None:
    self._view_mode = "list" if mode == "list" else "grid"
    if self._view_mode == "list":
        self._list.setViewMode(QListWidget.ViewMode.ListMode)
        self._list.setGridSize(QSize())
        self._list.setIconSize(QSize(LIST_THUMB_W, LIST_THUMB_H))
        self._list.setSpacing(4)
        self._list.setUniformItemSizes(False)
        self._list.setWordWrap(False)
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        size_hint = QSize(0, LIST_ROW_H)
    else:
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self._list.setGridSize(QSize(GRID_W, GRID_H))
        self._list.setSpacing(4)
        self._list.setUniformItemSizes(True)
        self._list.setWordWrap(True)
        align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        size_hint = QSize(GRID_W, GRID_H)
    for i in range(self._list.count()):
        item = self._list.item(i)
        if item is not None:
            path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
            if str(path):
                dur_str = _format_duration(int(item.data(Qt.ItemDataRole.UserRole + 3) or 0))
                item.setText(_media_pool_item_text(path, dur_str, self._view_mode))
            item.setTextAlignment(align)
            item.setSizeHint(size_hint)
    self._list.updateGeometry()

def _sort_items(self) -> None:
    if self._list.count() <= 1:
        return
    items: list[QListWidgetItem] = []
    while self._list.count():
        item = self._list.takeItem(0)
        if item is not None:
            items.append(item)

    kind_order = {"V": 0, "A": 1, "S": 2, "R": 3, "M": 4, "3": 5, "?": 9}

    def _key(item: QListWidgetItem):
        path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "?")
        duration = int(item.data(Qt.ItemDataRole.UserRole + 3) or 0)
        if self._sort_mode == "type":
            return (kind_order.get(kind, 9), path.name.lower())
        if self._sort_mode == "duration":
            return (-duration, path.name.lower())
        return (path.name.lower(), kind_order.get(kind, 9))

    for item in sorted(items, key=_key):
        self._list.addItem(item)

def _apply_filter(self) -> None:
    query = self._search_edit.text().strip().lower()
    featured_path = str(getattr(self, "_featured_path", "") or "")
    basename_counts: dict[str, int] = {}
    for i in range(self._list.count()):
        item = self._list.item(i)
        path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        if path.name:
            basename_counts[path.name.casefold()] = basename_counts.get(path.name.casefold(), 0) + 1
    for i in range(self._list.count()):
        item = self._list.item(i)
        path = str(item.data(Qt.ItemDataRole.UserRole) or "")
        kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "")
        text = item.text().lower()
        active_kind = self._bin_kind if self._bin_kind != "all" else self._filter_kind
        matches_kind = self._matches_smart_bin(item, active_kind, basename_counts) if active_kind not in {"all", "V", "A", "S", "R", "M", "3"} else (active_kind == "all" or kind == active_kind)
        matches_query = not query or query in text or query in path.lower()
        # 3D assets remain visible even when featured. Users often compare
        # several models, and hiding the selected one makes the pool look
        # like it lost or reordered an asset after import/selection.
        is_featured = bool(featured_path) and path == featured_path and kind != "3"
        item.setHidden(is_featured or not (matches_kind and matches_query))
    self._refresh_empty_state()
    visible = sum(
        1 for i in range(self._list.count())
        if not self._list.item(i).isHidden()
    )
    state = self._media_pool_state(total=self._list.count(), visible=visible)
    self._status_label.setText(state.title)
