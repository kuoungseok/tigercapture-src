from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap

from app.media_pool import (
    FEATURED_THUMB_H,
    FEATURED_THUMB_W,
    ROLE_MMD_BADGE,
    ROLE_PERFORMANCE_SOURCE,
    _decorate_media_thumb,
    _draw_actor_qa_badge,
    _draw_kind_badge,
    _format_duration,
    _make_ar_pbr_thumbnail,
    _make_audio_thumbnail,
    _make_image_list_thumbnail,
    _make_image_thumbnail,
    _make_mmd_thumbnail,
    _make_spine_thumbnail,
    _make_video_list_thumbnail,
    _make_video_thumbnail,
    _make_video_thumbnail_at,
    _make_vrm_avatar_thumbnail,
    _mmd_badge_label_for_path,
    _mmd_kind_name_for_path,
    _placeholder_pixmap,
    _proxy_state_for_video,
)

def _item_metadata_text(self, item: QListWidgetItem | None) -> str:
    if item is None:
        return "No media selected"
    path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
    kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "?")
    duration = int(item.data(Qt.ItemDataRole.UserRole + 3) or 0)
    kind_name = {
        "V": "Video",
        "A": "Audio",
        "I": "Image",
        "S": "Actor",
        "R": "VRM Avatar",
        "M": _mmd_kind_name_for_path(path),
        "3": "3D Asset",
    }.get(kind, "Media")
    duration_text = _format_duration(duration) or "--"
    proxy_line = ""
    if kind == "V":
        proxy_state = str(item.data(Qt.ItemDataRole.UserRole + 7) or _proxy_state_for_video(path) or "")
        proxy_line = {
            "ready": "Proxy: ready",
            "stale": "Proxy: stale - regenerate recommended",
            "": "Proxy: missing",
        }.get(proxy_state, f"Proxy: {proxy_state}")
    ingest_line = ""
    try:
        manifest = self.ingest_manifest_payload(selected_only=True)
        rows = manifest.get("items", []) if isinstance(manifest, dict) else []
        if rows:
            digest = str(rows[0].get("checksum_sha256", ""))
            ingest_line = f"Ingest: verified · sha256 {digest[:12]}..." if digest else "Ingest: verified"
    except Exception:
        ingest_line = ""
    actor_qa = ""
    if kind == "S":
        try:
            from app.actor_qa_status import actor_status_detail_lines

            actor_lines = actor_status_detail_lines(item.data(Qt.ItemDataRole.UserRole + 5))
            actor_qa = "\n".join(actor_lines)
        except Exception:
            actor_qa = ""
    auto_polish = ""
    if kind == "V":
        if bool(item.data(ROLE_PERFORMANCE_SOURCE)):
            auto_polish = (
                "Performance Source: avatar tracking input only; "
                "not used as Program Output background."
            )
        report = item.data(Qt.ItemDataRole.UserRole + 6)
        if isinstance(report, dict) and int(report.get("event_count", 0) or 0) > 0:
            counts = report.get("counts", {}) or {}
            labels = ", ".join(report.get("hotkey_labels", []) or [])
            polish_line = (
                f"Auto Polish: {int(report.get('readiness', 0) or 0)}% ready, "
                f"{int(report.get('auto_zoom_count', 0) or 0)} zoom"
                f" · click {counts.get('click', 0)} / drag {counts.get('drag', 0)} / "
                f"hotkey {counts.get('hotkey', 0) + counts.get('key', 0)}"
                + (f"\nKeys: {labels}" if labels else "")
            )
            auto_polish = f"{auto_polish}\n{polish_line}" if auto_polish else polish_line
        elif isinstance(report, dict) and "missing_cursor_sidecar" in set(report.get("warnings", []) or []):
            line = "Auto Polish: no cursor sidecar"
            auto_polish = f"{auto_polish}\n{line}" if auto_polish else line
    ar_pbr_status = ""
    if kind == "3":
        ar_pbr_status = "3D support: checked on preview/place"
    avatar_status = ""
    if kind == "R":
        avatar_status = (
            "Avatar Target: use this in the shared VTuber Studio.\n"
            "Program Output does not render this VRM file directly; "
            "Performance Source drives the pose stream."
        )
    mmd_status = ""
    if kind == "M":
        badge = str(item.data(ROLE_MMD_BADGE) or _mmd_badge_label_for_path(path))
        mmd_status = (
            f"Badge: {badge}\n"
            f"MMD Asset: {_mmd_kind_name_for_path(path)}\n"
            "MMD asset: pair PMX/PMD/PBX models with VMD motion on MMD tracks."
        )
    return (
        f"{path.name}\n"
        f"Type: {kind_name}   Duration: {duration_text}\n"
        f"{proxy_line + chr(10) if proxy_line else ''}"
        f"{ingest_line + chr(10) if ingest_line else ''}"
        f"{actor_qa + chr(10) if actor_qa else ''}"
        f"{auto_polish + chr(10) if auto_polish else ''}"
        f"{ar_pbr_status + chr(10) if ar_pbr_status else ''}"
        f"{avatar_status + chr(10) if avatar_status else ''}"
        f"{mmd_status + chr(10) if mmd_status else ''}"
        f"{path}"
    )

def _featured_pixmap_for_item(self, item: QListWidgetItem) -> QPixmap:
    path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
    kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "?")
    if kind == "V":
        pm = _make_video_list_thumbnail(
            path,
            width=FEATURED_THUMB_W,
            height=FEATURED_THUMB_H,
        )
        if pm is not None and not pm.isNull():
            return _decorate_media_thumb(
                pm,
                kind,
                path,
                hdr_info=item.data(Qt.ItemDataRole.UserRole + 1),
                auto_polish_report=item.data(Qt.ItemDataRole.UserRole + 6),
                performance_source=bool(item.data(ROLE_PERFORMANCE_SOURCE)),
            )
    base = item.data(Qt.ItemDataRole.UserRole + 4)
    if isinstance(base, QPixmap) and not base.isNull():
        decorated = _decorate_media_thumb(
            base,
            kind,
            path,
            hdr_info=item.data(Qt.ItemDataRole.UserRole + 1),
            auto_polish_report=item.data(Qt.ItemDataRole.UserRole + 6),
            performance_source=bool(item.data(ROLE_PERFORMANCE_SOURCE)),
        )
        return decorated.scaled(
            QSize(FEATURED_THUMB_W, FEATURED_THUMB_H),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    pm = item.icon().pixmap(FEATURED_THUMB_W, FEATURED_THUMB_H)
    if pm.isNull():
        pm = _placeholder_pixmap(FEATURED_THUMB_H)
    return pm.scaled(
        QSize(FEATURED_THUMB_W, FEATURED_THUMB_H),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

def _refresh_item_thumbnail(self, item: QListWidgetItem) -> None:
    if item is None:
        return
    path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
    kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "?")
    if kind == "M":
        item.setData(ROLE_MMD_BADGE, _mmd_badge_label_for_path(path))
    base_thumb = item.data(Qt.ItemDataRole.UserRole + 4)
    if not isinstance(base_thumb, QPixmap) or base_thumb.isNull():
        if kind == "V":
            base_thumb = _make_video_thumbnail(path) or _placeholder_pixmap()
        elif kind == "A":
            base_thumb = _make_audio_thumbnail(path)
        elif kind == "I":
            base_thumb = _make_image_thumbnail(path) or _placeholder_pixmap()
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
        item.setData(Qt.ItemDataRole.UserRole + 4, base_thumb)
    decorated = _decorate_media_thumb(
        base_thumb,
        kind,
        path,
        hdr_info=item.data(Qt.ItemDataRole.UserRole + 1),
        auto_polish_report=item.data(Qt.ItemDataRole.UserRole + 6),
        performance_source=bool(item.data(ROLE_PERFORMANCE_SOURCE)),
    )
    if self._view_mode == "list" and kind == "V":
        list_base = _make_video_list_thumbnail(path)
        if list_base is not None and not list_base.isNull():
            decorated = _decorate_media_thumb(
                list_base,
                kind,
                path,
                hdr_info=item.data(Qt.ItemDataRole.UserRole + 1),
                auto_polish_report=item.data(Qt.ItemDataRole.UserRole + 6),
                performance_source=bool(item.data(ROLE_PERFORMANCE_SOURCE)),
            )
        item.setIcon(QIcon(decorated))
    elif self._view_mode == "list" and kind == "I":
        list_base = _make_image_list_thumbnail(path)
        if list_base is not None and not list_base.isNull():
            decorated = _decorate_media_thumb(
                list_base,
                kind,
                path,
                hdr_info=item.data(Qt.ItemDataRole.UserRole + 1),
                auto_polish_report=item.data(Qt.ItemDataRole.UserRole + 6),
                performance_source=bool(item.data(ROLE_PERFORMANCE_SOURCE)),
            )
        item.setIcon(QIcon(decorated))
    else:
        item.setIcon(QIcon(decorated))

def _set_scrub_preview_for_item(self, item: QListWidgetItem | None, ratio: float) -> None:
    if item is None:
        return
    kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "?")
    if kind != "V":
        self._set_preview_for_item(item)
        return
    path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
    pm = _make_video_thumbnail_at(path, ratio, size=64)
    if pm is None or pm.isNull():
        self._set_preview_for_item(item)
        return
    decorated = _decorate_media_thumb(
        pm,
        kind,
        path,
        hdr_info=item.data(Qt.ItemDataRole.UserRole + 1),
        auto_polish_report=item.data(Qt.ItemDataRole.UserRole + 6),
        performance_source=bool(item.data(ROLE_PERFORMANCE_SOURCE)),
    )
    self._preview_label.setText("")
    self._preview_label.setPixmap(decorated.scaled(
        QSize(52, 52),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    ))
    dur = int(item.data(Qt.ItemDataRole.UserRole + 3) or 0)
    if dur > 0:
        self._status_label.setText(f"Scrub preview {_format_duration(int(dur * max(0.0, min(1.0, ratio))))}")
    self._preview_label.show()

def refresh_proxy_statuses(self) -> None:
    """Refresh P/STALE proxy badges for video items."""
    for i in range(self._list.count()):
        item = self._list.item(i)
        if item is None:
            continue
        path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "?")
        if kind != "V":
            continue
        item.setData(Qt.ItemDataRole.UserRole + 7, _proxy_state_for_video(path))
        base_thumb = item.data(Qt.ItemDataRole.UserRole + 4)
        if not isinstance(base_thumb, QPixmap) or base_thumb.isNull():
            base_thumb = _make_video_thumbnail(path) or _placeholder_pixmap()
            item.setData(Qt.ItemDataRole.UserRole + 4, base_thumb)
        hdr_info = item.data(Qt.ItemDataRole.UserRole + 1)
        auto_polish_report = item.data(Qt.ItemDataRole.UserRole + 6)
        decorated = _decorate_media_thumb(
            base_thumb,
            kind,
            path,
            hdr_info=hdr_info,
            auto_polish_report=auto_polish_report,
            performance_source=bool(item.data(ROLE_PERFORMANCE_SOURCE)),
        )
        if self._view_mode == "list":
            list_base = _make_video_list_thumbnail(path)
            if list_base is not None and not list_base.isNull():
                decorated = _decorate_media_thumb(
                    list_base,
                    kind,
                    path,
                    hdr_info=hdr_info,
                    auto_polish_report=auto_polish_report,
                    performance_source=bool(item.data(ROLE_PERFORMANCE_SOURCE)),
                )
            item.setIcon(QIcon(decorated))
        else:
            item.setIcon(QIcon(decorated))
        if str(getattr(self, "_featured_path", "") or "") == str(path):
            self._set_featured_item(item)

def refresh_actor_qa_status(self, status_path: Path | str | None = None) -> None:
    """Reload actor corpus QA status and refresh actor badges."""
    try:
        from app.actor_qa_status import (
            actor_status_badge,
            actor_status_for_path,
            actor_status_tooltip,
            load_actor_qa_status,
        )

        self._actor_qa_status = load_actor_qa_status(status_path)
    except Exception:
        self._actor_qa_status = {}
        return
    for i in range(self._list.count()):
        item = self._list.item(i)
        if item is None:
            continue
        kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "?")
        if kind != "S":
            continue
        path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        base_thumb = item.data(Qt.ItemDataRole.UserRole + 4)
        if not isinstance(base_thumb, QPixmap) or base_thumb.isNull():
            base_thumb = _make_spine_thumbnail()
            item.setData(Qt.ItemDataRole.UserRole + 4, base_thumb)
        row = actor_status_for_path(self._actor_qa_status, path)
        item.setData(Qt.ItemDataRole.UserRole + 5, row)
        thumb = _draw_kind_badge(base_thumb, kind)
        label, color = actor_status_badge(row)
        item.setIcon(QIcon(_draw_actor_qa_badge(thumb, label, color)))
        tip = actor_status_tooltip(row)
        if tip:
            base_tip = str(path)
            item.setToolTip(f"{base_tip}\n{tip}")
    self._list.viewport().update()

def media_health_payload(self, search_roots: list[Path | str] | None = None) -> dict:
    """Return a relink/proxy health report for the current Media Pool.

    This mirrors the project-level Health Center report, but scopes it to
    the pool so the left rail can explain proxy/relink debt without waiting
    for a full project save.
    """
    doc = {
        "media_pool": [
            {
                "path": str(self._list.item(i).data(Qt.ItemDataRole.UserRole) or ""),
                "kind": str(self._list.item(i).data(Qt.ItemDataRole.UserRole + 2) or ""),
            }
            for i in range(self._list.count())
            if self._list.item(i) is not None
        ]
    }
    roots = list(search_roots or [])
    if not roots:
        seen: set[Path] = set()
        for row in doc["media_pool"]:
            try:
                parent = Path(str(row.get("path") or "")).parent
            except Exception:
                continue
            if parent not in seen:
                seen.add(parent)
                roots.append(parent)
    from app.media_relink import build_media_health_report

    return build_media_health_report(doc, roots)
