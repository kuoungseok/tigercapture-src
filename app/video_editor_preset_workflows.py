from __future__ import annotations

import json
import os
import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.audio_tracks import AUDIO_EXTS, VIDEO_EXTS
from app.editor_observability import append_ux_event as _append_ux_event
from app.i18n import tr
from app.icons import app_icon
from app.timeline_model import ZoomActor
from app.timeline_track_row import TrackRow
from app.typography import TextClip
from app.video_editor_preset_browser_style import make_pack_icon
from app.video_editor_preset_cards import (
    WorkflowPresetPanel,
    _hash_palette,
    _preset_category_from_tags,
    _preset_preview_cache_root,
    _render_contextual_preset_preview,
    _render_preset_ab_application_preview,
    _render_static_preset_preview,
    _render_template_timeline_preview,
)
from app import video_editor_preset_context as _preset_context


def _show_preset_overlay_preview(self, kind: str, payload: dict, label: str = "") -> None:
    self._clear_preset_overlay_preview()
    canvas = getattr(self, "_drawing_canvas", None)
    if canvas is None or canvas.width() <= 0 or canvas.height() <= 0:
        return
    kind_text = str(kind or "").casefold()
    payload = dict(payload or {})
    title = str(
        label
        or payload.get("name")
        or payload.get("text")
        or kind_text.replace("_", " ").title()
        or "Preset"
    )
    def _payload_hint() -> str:
        hints: list[str] = []
        filters = payload.get("video_filters") or payload.get("filters")
        if isinstance(filters, dict):
            for key, value in filters.items():
                if key in {"enabled", "name"}:
                    continue
                if value in (None, False, 0, 0.0, ""):
                    continue
                hints.append(str(key).replace("_", " ").title())
        chroma = payload.get("chroma_key")
        if isinstance(chroma, dict) and chroma.get("enabled", bool(chroma)):
            hints.append("Chroma Key")
        for key in ("effect", "mode", "style"):
            value = payload.get(key)
            if value:
                hints.append(str(value).replace("_", " ").title())
        seen: set[str] = set()
        compact: list[str] = []
        for hint in hints:
            if hint in seen:
                continue
            seen.add(hint)
            compact.append(hint)
        return " / ".join(compact[:3])

    if "template" in kind_text:
        steps = payload.get("sequence")
        count = len(steps) if isinstance(steps, list) else 0
        step_lines: list[str] = []
        if isinstance(steps, list):
            for idx, step in enumerate(steps[:5]):
                if not isinstance(step, dict):
                    continue
                at_ms = int(step.get("at_ms", 0) or 0)
                name = str(step.get("name") or step.get("preset_id") or step.get("kind") or "step")
                kind_label = str(step.get("kind", "preset") or "preset")
                step_lines.append(f"+{at_ms}ms {kind_label}: {name}")
            if len(steps) > 5:
                step_lines.append(f"+ {len(steps) - 5} more")
        body = f"{title}\n{count} linked step(s)"
        if step_lines:
            body += "\n" + "\n".join(step_lines)
        color_a, color_b = "#7E6FFF", "#5CC8FF"
        x_norm, y_norm = 0.50, 0.24
        width_ratio = 0.58
    elif "motion" in kind_text:
        body = f"{title}\nMotion preview"
        color_a, color_b = "#5CC8FF", "#7E6FFF"
        x_norm, y_norm = float(payload.get("x_norm", 0.58) or 0.58), float(payload.get("y_norm", 0.38) or 0.38)
        width_ratio = 0.30
    elif "sticker" in kind_text:
        body = str(payload.get("text") or title or "STICKER")
        color_a, color_b = str(payload.get("color", "#FF7043") or "#FF7043"), "#FFB85B"
        x_norm, y_norm = float(payload.get("x_norm", 0.62) or 0.62), float(payload.get("y_norm", 0.36) or 0.36)
        width_ratio = 0.25
    elif "caption" in kind_text:
        body = str(payload.get("text") or title or "CAPTION")
        color_a, color_b = "#B56CFF", "#F052A2"
        x_norm, y_norm = float(payload.get("x_norm", 0.5) or 0.5), float(payload.get("y_norm", 0.82) or 0.82)
        width_ratio = 0.58
    elif "audio" in kind_text:
        body = f"{title}\nAudio preset"
        color_a, color_b = "#78F29B", "#60E6C5"
        x_norm, y_norm = 0.50, 0.78
        width_ratio = 0.36
    elif "color" in kind_text:
        body = f"{title}\nColor grade"
        color_a, color_b = "#FFD166", "#FF7043"
        x_norm, y_norm = 0.50, 0.22
        width_ratio = 0.34
    elif "effect" in kind_text:
        hint = _payload_hint()
        body = f"FX PREVIEW\n{title}"
        if hint:
            body += "\n" + hint
        color_a, color_b = "#FF7043", "#7E6FFF"
        x_norm, y_norm = 0.50, 0.22
        width_ratio = 0.42
    elif "transition" in kind_text:
        ttype = str(payload.get("transition_out_type") or payload.get("type") or title)
        detail = ttype.replace("_", " ").title()
        ms = payload.get("transition_out_ms") or payload.get("ms")
        body = f"TRANSITION\n{title}"
        if detail and detail.casefold() != title.casefold():
            body += "\n" + detail
        if ms:
            try:
                body += f" - {int(ms)}ms"
            except Exception:
                pass
        color_a, color_b = "#FF7A59", "#FFD166"
        x_norm, y_norm = 0.50, 0.50
        width_ratio = 0.38
    else:
        body = str(payload.get("text") or title or "TITLE")
        color_a, color_b = "#F052A2", "#7E6FFF"
        x_norm, y_norm = float(payload.get("x_norm", 0.5) or 0.5), float(payload.get("y_norm", 0.78) or 0.78)
        width_ratio = 0.48

    lbl = QLabel(canvas)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    lbl.setProperty("presetOverlayKind", kind_text)
    lbl.setProperty("presetOverlayFrameMarker", True)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    marker = "FRAME PREVIEW"
    if "effect" in kind_text:
        marker = "FX ON FRAME"
    elif "transition" in kind_text:
        marker = "CUT MARKER"
    elif "title" in kind_text or "caption" in kind_text:
        marker = "TITLE ON FRAME"
    elif "sticker" in kind_text:
        marker = "STICKER ON FRAME"
    elif "template" in kind_text:
        marker = "TEMPLATE STEPS"
    if marker and marker not in body:
        body = f"{body}\n{marker}"
    lbl.setText(body)
    font = QFont(lbl.font())
    font.setPixelSize(max(14, min(28, int(canvas.height() * 0.045))))
    font.setBold(True)
    lbl.setFont(font)
    lbl.setStyleSheet(
        "QLabel{"
        f"color:#FFFFFF;background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {color_a},stop:1 {color_b});"
        "border:1px solid rgba(255,255,255,90);border-radius:16px;"
        "padding:10px 16px;font-weight:900;"
        "}"
    )
    width = max(160, min(canvas.width() - 24, int(canvas.width() * width_ratio)))
    line_count = max(1, body.count("\n") + 1)
    height = max(48, min(160, 28 + line_count * 18))
    x = int(canvas.width() * x_norm) - width // 2
    y = int(canvas.height() * y_norm) - height // 2
    x = max(8, min(canvas.width() - width - 8, x))
    y = max(8, min(canvas.height() - height - 8, y))
    lbl.setGeometry(x, y, width, height)
    lbl.show()
    lbl.raise_()
    self._preset_preview_overlay = lbl
    self._preset_preview_overlay_payload = {
        "kind": kind_text,
        "payload": payload,
        "label": label,
    }


def _manage_preset_packs(self) -> None:
    from PySide6.QtWidgets import QListWidget, QListWidgetItem

    dlg = QDialog(self)
    dlg.setWindowTitle("Preset Pack Manager")
    dlg.resize(520, 420)
    root = QVBoxLayout(dlg)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)
    hint = QLabel("Enable, disable, repair, or remove imported JSON preset packs.")
    hint.setWordWrap(True)
    root.addWidget(hint)
    market = QLabel("")
    market.setWordWrap(True)
    market.setStyleSheet(
        "QLabel{background:rgba(126,111,255,20);border:1px solid rgba(126,111,255,70);"
        "border-radius:10px;color:#DDE2FF;padding:7px;font-size:10px;}"
    )
    root.addWidget(market)
    listing = QListWidget()
    listing.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
    listing.setIconSize(QSize(42, 30))
    root.addWidget(listing, 1)
    details = QLabel("Select a pack to inspect conflicts and repair hints.")
    details.setWordWrap(True)
    details.setStyleSheet("color:#A7ADC2;font-size:10px;")
    root.addWidget(details)

    def _reload() -> None:
        listing.clear()
        try:
            from app.preset_library import list_user_preset_packs, preset_pack_marketplace_report

            rows = list_user_preset_packs()
            report = preset_pack_marketplace_report()
        except Exception:
            rows = []
            report = {}
        kinds = dict(report.get("kind_counts", {}) or {})
        kind_text = ", ".join(f"{key}:{value}" for key, value in list(kinds.items())[:6]) or "no user pack kinds"
        actions = list(report.get("recommendations", []) or [])[:2]
        market.setText(
            f"Marketplace: {report.get('enabled_packs', 0)}/{report.get('total_packs', 0)} pack(s) enabled, "
            f"{report.get('issue_packs', 0)} issue pack(s), {report.get('enabled_presets', 0)} enabled preset(s).\n"
            f"Kinds: {kind_text}\n"
            f"Next: {' / '.join(actions) if actions else 'Ready'}"
        )
        for row in rows:
            card = next(
                (
                    item for item in list(report.get("packs", []) or [])
                    if str(item.get("path", "")) == str(row.get("path", ""))
                ),
                {},
            )
            row = {**row, "market_card": card}
            status = "ON" if row.get("enabled") else "OFF"
            primary = " / primary" if row.get("primary") else ""
            issues = list(row.get("issues", []) or [])
            issue_text = "" if not issues else f" / {len(issues)} issue(s)"
            score = int((card or {}).get("score", 0) or 0)
            coverage = str((card or {}).get("coverage", "") or "")
            text = (
                f"[{status}] {row.get('name')}  "
                f"score {score} / {row.get('count', 0)} presets{primary}{issue_text}"
            )
            if coverage:
                text += f" / {coverage}"
            item = QListWidgetItem(text)
            item.setIcon(make_pack_icon(f"{row.get('name', '')}:{coverage}:{score}"))
            item.setData(Qt.ItemDataRole.UserRole, row)
            item.setToolTip(json.dumps(row, ensure_ascii=False, indent=2, default=str))
            if issues:
                item.setForeground(QColor("#FFB85B"))
            elif row.get("enabled"):
                item.setForeground(QColor("#E8EAF4"))
            else:
                item.setForeground(QColor("#7B8299"))
            listing.addItem(item)
        if listing.count() > 0 and listing.currentRow() < 0:
            listing.setCurrentRow(0)
        _update_details()

    def _selected_row() -> dict | None:
        item = listing.currentItem()
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return dict(data or {}) if isinstance(data, dict) else None

    buttons = QHBoxLayout()
    enable_btn = QPushButton("Enable")
    disable_btn = QPushButton("Disable")
    repair_btn = QPushButton("Repair")
    resolve_btn = QPushButton("Resolve Issues")
    inspect_btn = QPushButton("Inspect")
    delete_btn = QPushButton("Delete")
    open_btn = QPushButton("Open Folder")
    refresh_btn = QPushButton("Refresh")
    for btn in (enable_btn, disable_btn, repair_btn, resolve_btn, inspect_btn, delete_btn, open_btn, refresh_btn):
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
    buttons.addWidget(enable_btn)
    buttons.addWidget(disable_btn)
    buttons.addWidget(repair_btn)
    buttons.addWidget(resolve_btn)
    buttons.addWidget(inspect_btn)
    buttons.addWidget(delete_btn)
    buttons.addStretch(1)
    buttons.addWidget(open_btn)
    buttons.addWidget(refresh_btn)
    root.addLayout(buttons)

    def _set_enabled(enabled: bool) -> None:
        row = _selected_row()
        if not row:
            return
        try:
            from app.preset_library import set_user_preset_pack_enabled

            set_user_preset_pack_enabled(row.get("path", ""), enabled)
            _reload()
            self._refresh_user_preset_panels()
        except Exception as exc:
            self._flash_status(f"Pack update failed: {exc}")

    def _delete() -> None:
        row = _selected_row()
        if not row:
            return
        if row.get("primary"):
            self._flash_status("Primary user preset pack cannot be deleted")
            return
        try:
            from app.preset_library import delete_user_preset_pack

            delete_user_preset_pack(row.get("path", ""))
            _reload()
            self._refresh_user_preset_panels()
        except Exception as exc:
            self._flash_status(f"Pack delete failed: {exc}")

    def _repair() -> None:
        row = _selected_row()
        if not row:
            return
        try:
            from app.preset_library import repair_user_preset_pack

            result = repair_user_preset_pack(row.get("path", ""))
            _reload()
            self._refresh_user_preset_panels()
            self._flash_status(
                "Repaired preset pack: "
                f"{result.get('count', 0)} kept, "
                f"{result.get('invalid_removed', 0)} invalid, "
                f"{result.get('duplicates_removed', 0)} duplicate, "
                f"{result.get('missing_refs_removed', 0)} missing ref removed"
            )
        except Exception as exc:
            self._flash_status(f"Pack repair failed: {exc}")

    def _inspect_conflicts() -> None:
        row = _selected_row()
        if not row:
            return
        lines = [
            f"Pack: {row.get('name', '')}",
            f"Path: {row.get('path', '')}",
            f"Issues: {', '.join(row.get('issues', []) or []) or 'none'}",
        ]
        for key, label in (
            ("duplicate_ids", "Duplicate ids"),
            ("builtin_conflicts", "Built-in id conflicts"),
            ("cross_pack_conflicts", "Cross-pack conflicts"),
        ):
            values = list(row.get(key, []) or [])
            if values:
                lines.append(f"{label}: {', '.join(str(v) for v in values[:12])}")
        missing = list(row.get("missing_refs", []) or [])
        if missing:
            lines.append("Missing child presets:")
            for ref in missing[:12]:
                if isinstance(ref, dict):
                    lines.append(f"- {ref.get('template_id', '')} -> {ref.get('preset_id', '')}")
        QMessageBox.information(dlg, "Preset Pack Conflicts", "\n".join(lines))

    def _resolve_issues() -> None:
        row = _selected_row()
        if not row:
            return
        issues = set(str(v) for v in row.get("issues", []) or [])
        if not issues:
            self._flash_status("Preset pack has no issues")
            return
        hard = issues & {"builtin_id_conflicts", "cross_pack_conflicts"}
        if hard:
            QMessageBox.information(
                dlg,
                "Manual preset conflict",
                "This pack has id conflicts with built-in or another enabled pack.\n"
                "Use Inspect to see the ids, then rename those preset ids in the JSON or disable one pack.\n"
                "Repair can still remove invalid rows, duplicates, and missing template references.",
            )
        if issues & {"invalid_rows", "duplicate_ids", "missing_template_refs"}:
            _repair()
        elif hard:
            _inspect_conflicts()

    def _update_details() -> None:
        row = _selected_row()
        if not row:
            details.setText("Select a pack to inspect conflicts and repair hints.")
            return
        issues = list(row.get("issues", []) or [])
        bits = [
            f"{row.get('name', '')}",
            f"{row.get('count', 0)} valid / {row.get('row_count', row.get('count', 0))} rows",
        ]
        if row.get("invalid_count"):
            bits.append(f"{row.get('invalid_count')} invalid")
        if row.get("duplicate_ids"):
            bits.append(f"duplicate: {', '.join(row.get('duplicate_ids', [])[:3])}")
        if row.get("builtin_conflicts"):
            bits.append(f"builtin conflict: {', '.join(row.get('builtin_conflicts', [])[:3])}")
        if row.get("cross_pack_conflicts"):
            bits.append(f"cross-pack conflict: {', '.join(row.get('cross_pack_conflicts', [])[:3])}")
        if row.get("missing_refs"):
            bits.append(f"{len(row.get('missing_refs') or [])} missing template ref(s)")
        card = dict(row.get("market_card", {}) or {})
        if card:
            if card.get("top_tags"):
                bits.append(
                    "tags: "
                    + ", ".join(f"{k}({v})" for k, v in list(dict(card.get("top_tags")).items())[:5])
                )
            if card.get("recommendation"):
                bits.append(f"next: {card.get('recommendation')}")
        if not issues:
            bits.append("OK")
        details.setText(" | ".join(bits))

    enable_btn.clicked.connect(lambda: _set_enabled(True))
    disable_btn.clicked.connect(lambda: _set_enabled(False))
    repair_btn.clicked.connect(_repair)
    resolve_btn.clicked.connect(_resolve_issues)
    inspect_btn.clicked.connect(_inspect_conflicts)
    delete_btn.clicked.connect(_delete)
    refresh_btn.clicked.connect(_reload)
    listing.currentItemChanged.connect(lambda *_: _update_details())

    def _open_folder() -> None:
        row = _selected_row()
        try:
            folder = Path(row.get("path", "")).parent if row else Path.home()
            os.startfile(str(folder))
        except Exception as exc:
            self._flash_status(f"Open folder failed: {exc}")

    open_btn.clicked.connect(_open_folder)
    _reload()
    close_btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_btns.rejected.connect(dlg.reject)
    root.addWidget(close_btns)
    dlg.exec()


def _open_template_composer(self) -> None:
    from PySide6.QtWidgets import QListWidget, QListWidgetItem

    try:
        from app.preset_library import EditorPreset, load_editor_presets, save_user_preset

        presets = [
            preset for preset in load_editor_presets()
            if str(getattr(preset, "kind", "")) != "template"
        ]
    except Exception as exc:
        self._flash_status(f"Template composer failed: {exc}")
        return
    dlg = QDialog(self)
    dlg.setWindowTitle("Template Composer")
    dlg.resize(760, 520)
    root = QVBoxLayout(dlg)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)

    name_edit = QLineEdit()
    name_edit.setPlaceholderText("Template name")
    root.addWidget(name_edit)

    lists = QHBoxLayout()
    available = QListWidget()
    available.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
    sequence = QListWidget()
    sequence.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
    lists.addWidget(available, 1)

    controls = QVBoxLayout()
    offset_spin = QSpinBox()
    offset_spin.setRange(0, 60 * 60 * 1000)
    offset_spin.setSingleStep(250)
    offset_spin.setSuffix(" ms")
    add_btn = QPushButton("Add >")
    remove_btn = QPushButton("< Remove")
    up_btn = QPushButton("Up")
    down_btn = QPushButton("Down")
    preview_btn = QPushButton("Preview")
    for btn in (add_btn, remove_btn, up_btn, down_btn, preview_btn):
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        controls.addWidget(btn)
    controls.addSpacing(10)
    controls.addWidget(QLabel("Offset"))
    controls.addWidget(offset_spin)
    duration_spin = QSpinBox()
    duration_spin.setRange(120, 60 * 60 * 1000)
    duration_spin.setSingleStep(250)
    duration_spin.setSuffix(" ms")
    target_combo = QComboBox()
    for label, value in (
        ("Auto target", "auto"),
        ("Selected clip", "selected_clip"),
        ("Active track", "active_track"),
        ("Audio clip", "audio"),
        ("Color grade", "color"),
    ):
        target_combo.addItem(label, value)
    condition_combo = QComboBox()
    for label, value in (
        ("Always", "always"),
        ("If video exists", "if_video"),
        ("If audio exists", "if_audio"),
        ("If vertical project", "if_vertical"),
        ("If short-form", "if_shortform"),
    ):
        condition_combo.addItem(label, value)
    update_btn = QPushButton("Update Step")
    update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    controls.addWidget(QLabel("Duration"))
    controls.addWidget(duration_spin)
    controls.addWidget(QLabel("Target"))
    controls.addWidget(target_combo)
    controls.addWidget(QLabel("Condition"))
    controls.addWidget(condition_combo)
    controls.addWidget(update_btn)
    controls.addStretch(1)
    lists.addLayout(controls)
    lists.addWidget(sequence, 1)
    root.addLayout(lists, 1)

    def _preset_duration_ms(preset) -> int:
        payload = dict(getattr(preset, "payload", {}) or {})
        for key in ("duration_ms", "transition_out_ms", "ms"):
            if payload.get(key):
                try:
                    return max(250, int(payload.get(key)))
                except Exception:
                    pass
        kind = str(getattr(preset, "kind", "") or "")
        if kind in {"title", "caption_style"}:
            return 2200
        if kind in {"transition", "sticker", "motion"}:
            return 1200
        return 1000

    for preset in presets:
        label = f"{preset.kind:14s}  {preset.name}"
        item = QListWidgetItem(label)
        item.setIcon(app_icon({
            "effect": "effects",
            "transition": "scissors",
            "title": "cursor",
            "caption_style": "list",
            "sticker": "spark",
            "motion": "zoom",
            "audio": "audio",
            "color": "palette",
        }.get(str(preset.kind), "grid")))
        item.setData(Qt.ItemDataRole.UserRole, preset)
        item.setToolTip(f"{preset.id}\n{preset.description}")
        available.addItem(item)
    if available.count() > 0:
        available.setCurrentRow(0)

    def _sequence_entry_label(entry: dict) -> str:
        target = str(entry.get("target", "auto") or "auto")
        condition = str(entry.get("condition", "always") or "always")
        return (
            f"+{int(entry.get('at_ms', 0) or 0):>5}ms  "
            f"{int(entry.get('duration_ms', 0) or 0):>5}ms  "
            f"{entry.get('kind', 'preset'):14s}  "
            f"{entry.get('name', entry.get('preset_id', 'preset'))}  "
            f"[{target}/{condition}]"
        )

    def _set_combo_data(combo: QComboBox, value: str) -> None:
        idx = combo.findData(str(value or ""))
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _add_selected() -> None:
        item = available.currentItem()
        if item is None:
            return
        preset = item.data(Qt.ItemDataRole.UserRole)
        if preset is None:
            return
        default_duration = _preset_duration_ms(preset)
        if duration_spin.value() <= duration_spin.minimum():
            duration_spin.setValue(default_duration)
        entry = {
            "kind": str(getattr(preset, "kind", "")),
            "preset_id": str(getattr(preset, "id", "")),
            "name": str(getattr(preset, "name", "")),
            "at_ms": int(offset_spin.value()),
            "duration_ms": int(duration_spin.value() or default_duration),
            "target": str(target_combo.currentData() or "auto"),
            "condition": str(condition_combo.currentData() or "always"),
        }
        seq_item = QListWidgetItem(_sequence_entry_label(entry))
        seq_item.setData(Qt.ItemDataRole.UserRole, entry)
        sequence.addItem(seq_item)
        sequence.setCurrentItem(seq_item)
        offset_spin.setValue(offset_spin.value() + max(250, entry["duration_ms"] // 2))
        duration_spin.setValue(default_duration)

    def _remove_selected() -> None:
        row = sequence.currentRow()
        if row >= 0:
            sequence.takeItem(row)

    def _move_selected(delta: int) -> None:
        row = sequence.currentRow()
        next_row = row + int(delta)
        if row < 0 or next_row < 0 or next_row >= sequence.count():
            return
        item = sequence.takeItem(row)
        sequence.insertItem(next_row, item)
        sequence.setCurrentRow(next_row)

    def _load_selected_step() -> None:
        item = sequence.currentItem()
        if item is None:
            return
        entry = dict(item.data(Qt.ItemDataRole.UserRole) or {})
        offset_spin.setValue(int(entry.get("at_ms", 0) or 0))
        duration_spin.setValue(max(duration_spin.minimum(), int(entry.get("duration_ms", 1000) or 1000)))
        _set_combo_data(target_combo, str(entry.get("target", "auto") or "auto"))
        _set_combo_data(condition_combo, str(entry.get("condition", "always") or "always"))

    def _update_selected_step() -> None:
        item = sequence.currentItem()
        if item is None:
            return
        entry = dict(item.data(Qt.ItemDataRole.UserRole) or {})
        entry["at_ms"] = int(offset_spin.value())
        entry["duration_ms"] = int(duration_spin.value())
        entry["target"] = str(target_combo.currentData() or "auto")
        entry["condition"] = str(condition_combo.currentData() or "always")
        item.setData(Qt.ItemDataRole.UserRole, entry)
        item.setText(_sequence_entry_label(entry))

    def _preview_template() -> None:
        entries = [
            dict(sequence.item(i).data(Qt.ItemDataRole.UserRole) or {})
            for i in range(sequence.count())
        ]
        self._show_preset_overlay_preview(
            "template",
            {"sequence": entries},
            name_edit.text().strip() or "Composed Template",
        )

    add_btn.clicked.connect(_add_selected)
    available.itemDoubleClicked.connect(lambda _item: _add_selected())
    remove_btn.clicked.connect(_remove_selected)
    up_btn.clicked.connect(lambda: _move_selected(-1))
    down_btn.clicked.connect(lambda: _move_selected(1))
    preview_btn.clicked.connect(_preview_template)
    update_btn.clicked.connect(_update_selected_step)
    sequence.currentItemChanged.connect(lambda *_: _load_selected_step())
    available.currentItemChanged.connect(
        lambda item, _prev=None: duration_spin.setValue(
            _preset_duration_ms(item.data(Qt.ItemDataRole.UserRole)) if item is not None else 1000
        )
    )

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save
        | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.rejected.connect(dlg.reject)

    def _save_template() -> None:
        name = name_edit.text().strip()
        if not name:
            self._flash_status("Template name is empty")
            return
        entries = [
            dict(sequence.item(i).data(Qt.ItemDataRole.UserRole) or {})
            for i in range(sequence.count())
        ]
        if not entries:
            self._flash_status("Add at least one preset to the template")
            return
        slug = "".join(ch.casefold() if ch.isalnum() else "-" for ch in name).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        slug = slug or "template"
        preset = EditorPreset(
            id=f"user-template-{slug}-{int(time.time())}",
            kind="template",
            name=name,
            description="Composed in the Template Composer.",
            tags=("user", "template", "workflow", "one-click"),
            payload={"sequence": entries},
        )
        try:
            save_user_preset(preset)
        except Exception as exc:
            self._flash_status(f"Template save failed: {exc}")
            return
        self._refresh_user_preset_panels()
        self._flash_status(f"Saved template: {name}")
        dlg.accept()

    buttons.accepted.connect(_save_template)
    root.addWidget(buttons)
    dlg.finished.connect(lambda *_: self._clear_preset_live_preview())
    dlg.exec()


def _manage_preset_preview_cache(self) -> None:
    dlg = QDialog(self)
    dlg.setWindowTitle("Preset Preview Cache")
    dlg.resize(560, 260)
    root = QVBoxLayout(dlg)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)
    cache_dir = _preset_preview_cache_root()
    summary = QLabel()
    summary.setWordWrap(True)
    root.addWidget(summary)
    progress = QProgressBar()
    progress.setRange(0, 100)
    progress.setValue(0)
    root.addWidget(progress)

    def _stats() -> tuple[int, int]:
        files = list(cache_dir.glob("*.png"))
        total = 0
        for path in files:
            try:
                total += path.stat().st_size
            except Exception:
                pass
        return len(files), total

    def _refresh() -> None:
        count, total = _stats()
        summary.setText(
            f"Cache folder: {cache_dir}\n"
            f"{count} preview image(s), {total / (1024 * 1024):.2f} MB"
        )

    def _clear() -> None:
        removed = 0
        for path in cache_dir.glob("*.png"):
            try:
                path.unlink()
                removed += 1
            except Exception:
                pass
        progress.setValue(0)
        _refresh()
        self._flash_status(f"Cleared {removed} preset preview(s)")

    def _warm() -> None:
        try:
            from app.preset_library import load_editor_presets

            presets = load_editor_presets()
        except Exception as exc:
            self._flash_status(f"Preview warm-up failed: {exc}")
            return
        total = max(1, min(250, len(presets)))
        progress.setValue(0)
        for idx, preset in enumerate(presets[:total]):
            tags = tuple(getattr(preset, "tags", ()) or ())
            kind = str(getattr(preset, "kind", "") or "preset")
            try:
                _render_static_preset_preview(
                    colors=_hash_palette(f"{kind}:{getattr(preset, 'id', idx)}"),
                    kind=kind,
                    label=str(getattr(preset, "name", "Preset")),
                    payload=dict(getattr(preset, "payload", {}) or {}),
                    tags=tags,
                    category=_preset_category_from_tags(tags, kind.title()),
                    preset_id=f"{kind}:{getattr(preset, 'id', idx)}",
                )
            except Exception:
                pass
            progress.setValue(int((idx + 1) / total * 100))
            QApplication.processEvents()
        _refresh()
        self._flash_status(f"Warmed {total} preset preview(s)")

    def _warm_contextual() -> None:
        sample = self._preset_preview_frame()
        if sample is None:
            self._flash_status("Load or select media so current-frame preset previews can be cached")
            return
        try:
            from app.preset_library import load_editor_presets

            presets = load_editor_presets()
        except Exception as exc:
            self._flash_status(f"Context preview warm-up failed: {exc}")
            return
        total = max(1, min(250, len(presets)))
        progress.setValue(0)
        for idx, preset in enumerate(presets[:total]):
            tags = tuple(getattr(preset, "tags", ()) or ())
            kind = str(getattr(preset, "kind", "") or "preset")
            try:
                _render_contextual_preset_preview(
                    colors=_hash_palette(f"{kind}:{getattr(preset, 'id', idx)}"),
                    kind=kind,
                    label=str(getattr(preset, "name", "Preset")),
                    payload=dict(getattr(preset, "payload", {}) or {}),
                    tags=tags,
                    category=_preset_category_from_tags(tags, kind.title()),
                    preset_id=f"{kind}:{getattr(preset, 'id', idx)}",
                    sample_pixmap=sample,
                )
            except Exception:
                pass
            progress.setValue(int((idx + 1) / total * 100))
            QApplication.processEvents()
        _refresh()
        self._flash_status(f"Warmed {total} current-frame preset preview(s)")

    btns = QHBoxLayout()
    warm_btn = QPushButton("Warm Up")
    context_btn = QPushButton("Warm Current Frame")
    clear_btn = QPushButton("Clear")
    open_btn = QPushButton("Open Folder")
    refresh_btn = QPushButton("Refresh")
    for btn in (warm_btn, context_btn, clear_btn, open_btn, refresh_btn):
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btns.addWidget(warm_btn)
    btns.addWidget(context_btn)
    btns.addWidget(clear_btn)
    btns.addStretch(1)
    btns.addWidget(open_btn)
    btns.addWidget(refresh_btn)
    root.addLayout(btns)

    warm_btn.clicked.connect(_warm)
    context_btn.clicked.connect(_warm_contextual)
    clear_btn.clicked.connect(_clear)
    refresh_btn.clicked.connect(_refresh)
    open_btn.clicked.connect(lambda: os.startfile(str(cache_dir)) if os.name == "nt" else None)
    close_btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_btns.rejected.connect(dlg.reject)
    root.addWidget(close_btns)
    _refresh()
    dlg.exec()


def _preset_application_plan_rows(self, preset, *, at_ms=None, depth: int = 0) -> list[dict]:
    if preset is None or depth > 8:
        return []
    kind = str(getattr(preset, "kind", "") or "")
    payload = dict(getattr(preset, "payload", {}) or {})
    name = str(getattr(preset, "name", getattr(preset, "id", "Preset")) or "Preset")
    preset_id = str(getattr(preset, "id", "") or "")
    if kind == "template":
        try:
            from app.preset_library import preset_by_id, template_sequence
        except Exception:
            return [{
                "kind": kind,
                "name": name,
                "preset_id": preset_id,
                "status": "blocked",
                "reason": "Template sequence could not be loaded.",
                "at_ms": int(at_ms or 0),
                "duration_ms": 0,
                "target": "auto",
            }]
        base_track, base_clip = self._workflow_target_video_clip()
        base_ms = self._workflow_start_ms(base_track, base_clip, at_ms)
        rows: list[dict] = [{
            "kind": "template",
            "name": name,
            "preset_id": preset_id,
            "status": "template",
            "reason": "",
            "at_ms": int(base_ms),
            "duration_ms": 0,
            "target": "auto",
        }]
        for entry in template_sequence(preset):
            entry = dict(entry or {})
            child_at = int(base_ms)
            try:
                child_at += int(entry.get("at_ms", 0) or 0)
            except Exception:
                pass
            target = str(entry.get("target", "auto") or "auto")
            condition = str(entry.get("condition", "always") or "always")
            if not self._template_entry_condition_ok(entry):
                rows.append({
                    "kind": str(entry.get("kind", "preset") or "preset"),
                    "name": str(entry.get("preset_id", "Preset") or "Preset"),
                    "preset_id": str(entry.get("preset_id", "") or ""),
                    "status": "skipped",
                    "reason": f"Condition not met: {condition}",
                    "at_ms": child_at,
                    "duration_ms": int(entry.get("duration_ms", 0) or 0),
                    "target": target,
                })
                continue
            child = preset_by_id(entry.get("preset_id", ""))
            if child is None:
                rows.append({
                    "kind": str(entry.get("kind", "preset") or "preset"),
                    "name": str(entry.get("preset_id", "Missing preset") or "Missing preset"),
                    "preset_id": str(entry.get("preset_id", "") or ""),
                    "status": "blocked",
                    "reason": "Child preset is missing.",
                    "at_ms": child_at,
                    "duration_ms": int(entry.get("duration_ms", 0) or 0),
                    "target": target,
                })
                continue
            prev_mode = getattr(self, "_workflow_target_mode", None)
            self._workflow_target_mode = target
            try:
                child_rows = self._preset_application_plan_rows(child, at_ms=child_at, depth=depth + 1)
            finally:
                if prev_mode is None:
                    try:
                        delattr(self, "_workflow_target_mode")
                    except Exception:
                        pass
                else:
                    self._workflow_target_mode = prev_mode
            rows.extend(child_rows)
        return rows
    reason = self._preset_apply_failure_reason(preset)
    duration = int(payload.get("duration_ms") or payload.get("transition_out_ms") or payload.get("ms") or 0)
    if kind == "actor":
        duration = int(payload.get("duration_ms", duration or 3600) or 3600)
    return [{
        "kind": kind or "preset",
        "name": name,
        "preset_id": preset_id,
        "status": "blocked" if reason else "will_apply",
        "reason": reason,
        "at_ms": int(at_ms or self._workflow_start_ms(*self._workflow_target_video_clip())),
        "duration_ms": duration,
        "target": str(getattr(self, "_workflow_target_mode", "auto") or "auto"),
    }]


def _open_preset_application_preview(self, preset) -> None:
    from PySide6.QtWidgets import QListWidget, QListWidgetItem

    if preset is None:
        self._flash_status("Select a preset to preview")
        return
    dlg = QDialog(self)
    dlg.setWindowTitle(f"Preset Preview - {getattr(preset, 'name', 'Preset')}")
    dlg.resize(700, 520)
    root = QVBoxLayout(dlg)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)

    top = QHBoxLayout()
    sample = self._preset_preview_frame()
    kind = str(getattr(preset, "kind", "") or "preset")
    tags = tuple(getattr(preset, "tags", ()) or ())
    preview = QLabel()
    preview.setFixedSize(360, 202)
    preview.setStyleSheet("QLabel{background:#090B13;border:1px solid #30384F;border-radius:14px;}")
    preview_phase = {"value": 0.0}

    def _refresh_preview_frame() -> None:
        try:
            pix = _render_preset_ab_application_preview(
                kind=kind,
                label=str(getattr(preset, "name", "Preset")),
                payload=dict(getattr(preset, "payload", {}) or {}),
                tags=tags,
                preset_id=f"{kind}:{getattr(preset, 'id', '')}",
                sample_pixmap=sample,
                phase=preview_phase["value"],
            )
            preview.setPixmap(pix)
        except Exception:
            preview.setText("Preview")

    _refresh_preview_frame()
    preview_timer = QTimer(dlg)
    preview_timer.setInterval(90)
    preview_timer.timeout.connect(lambda: (preview_phase.__setitem__("value", (preview_phase["value"] + 0.055) % 1.0), _refresh_preview_frame()))
    preview_timer.start()
    dlg.finished.connect(lambda *_: preview_timer.stop())
    top.addWidget(preview)
    summary = QLabel(
        f"{kind.upper()} | {getattr(preset, 'name', 'Preset')}\n"
        f"{getattr(preset, 'description', '')}\n"
        f"Tags: {', '.join(tags[:8])}\n"
        "Preview: looping A/B current-frame simulation"
    )
    summary.setWordWrap(True)
    summary.setStyleSheet("color:#DDE2FF;font-size:11px;")
    top.addWidget(summary, 1)
    root.addLayout(top)

    rows = self._preset_application_plan_rows(preset)
    timeline_preview = QLabel()
    timeline_preview.setFixedHeight(86)
    timeline_preview.setPixmap(_render_template_timeline_preview(rows))
    timeline_preview.setVisible(kind == "template")
    root.addWidget(timeline_preview)

    listw = QListWidget()
    for row in rows:
        status = str(row.get("status", ""))
        prefix = {
            "template": "TEMPLATE",
            "will_apply": "APPLY",
            "blocked": "BLOCKED",
            "skipped": "SKIP",
        }.get(status, status.upper())
        timing = f"+{int(row.get('at_ms', 0) or 0)}ms"
        dur = int(row.get("duration_ms", 0) or 0)
        dur_text = f" / {dur}ms" if dur else ""
        text = (
            f"[{prefix}] {timing}{dur_text}  {row.get('kind', 'preset')}: "
            f"{row.get('name', row.get('preset_id', 'Preset'))}"
        )
        reason = str(row.get("reason", "") or "")
        if reason:
            text += f"\n  {reason}"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, row)
        if status == "blocked":
            item.setForeground(QColor("#FFB85B"))
        elif status == "skipped":
            item.setForeground(QColor("#7B8299"))
        elif status == "will_apply":
            item.setForeground(QColor("#78F29B"))
        listw.addItem(item)
    root.addWidget(listw, 1)

    button_row = QHBoxLayout()
    apply_btn = QPushButton("Apply")
    fix_btn = QPushButton("Fix Target")
    close_btn = QPushButton("Close")
    for btn in (apply_btn, fix_btn, close_btn):
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
    blocked = any(str(row.get("status")) == "blocked" for row in rows)
    apply_btn.setEnabled(not blocked)
    fix_btn.setEnabled(blocked)
    button_row.addWidget(fix_btn)
    button_row.addStretch(1)
    button_row.addWidget(apply_btn)
    button_row.addWidget(close_btn)
    root.addLayout(button_row)

    def _apply() -> None:
        dlg.accept()
        self._apply_workflow_preset(preset)

    def _fix() -> None:
        self._run_preset_fix_action(preset)
        next_rows = self._preset_application_plan_rows(preset)
        listw.clear()
        for row in next_rows:
            status = str(row.get("status", ""))
            text = f"[{status.upper()}] +{int(row.get('at_ms', 0) or 0)}ms  {row.get('kind')}: {row.get('name')}"
            reason = str(row.get("reason", "") or "")
            if reason:
                text += f"\n  {reason}"
            listw.addItem(QListWidgetItem(text))
        timeline_preview.setPixmap(_render_template_timeline_preview(next_rows))
        apply_btn.setEnabled(not any(str(row.get("status")) == "blocked" for row in next_rows))

    apply_btn.clicked.connect(_apply)
    fix_btn.clicked.connect(_fix)
    close_btn.clicked.connect(dlg.reject)
    dlg.exec()


def _run_preset_fix_action(self, preset) -> None:
    reason = self._preset_apply_failure_reason(preset)
    kind = str(getattr(preset, "kind", "") or "")
    if kind == "template":
        try:
            from app.preset_library import preset_by_id, template_sequence

            for entry in template_sequence(preset):
                if not self._template_entry_condition_ok(entry):
                    continue
                child = preset_by_id(entry.get("preset_id", ""))
                if child is None:
                    continue
                prev_mode = getattr(self, "_workflow_target_mode", None)
                self._workflow_target_mode = str(entry.get("target", "auto") or "auto")
                try:
                    child_reason = self._preset_apply_failure_reason(child)
                finally:
                    if prev_mode is None:
                        try:
                            delattr(self, "_workflow_target_mode")
                        except Exception:
                            pass
                    else:
                        self._workflow_target_mode = prev_mode
                if child_reason:
                    self._run_preset_fix_action(child)
                    return
        except Exception:
            pass
    if kind == "actor":
        payload = dict(getattr(preset, "payload", {}) or {})
        actor_kind = str(payload.get("actor_kind", "") or "")
        if actor_kind == "live2d" and not getattr(self, "_live2d_actor_tracks", []):
            self._add_live2d_actor_track()
            model = self._actor_model_candidate("live2d")
            self._flash_status("Created a Live2D actor lane" + (f" | candidate: {Path(model).name}" if model else ""))
            if model:
                return
            return
        if actor_kind == "spine" and not getattr(self, "_spine_actor_tracks", []):
            self._add_spine_actor_track()
            model = self._actor_model_candidate("spine")
            self._flash_status("Created a Spine actor lane" + (f" | candidate: {Path(model).name}" if model else ""))
            return
        model = self._actor_model_candidate(actor_kind)
        if model:
            self._flash_status(f"{actor_kind or 'actor'} model candidate ready: {Path(model).name}")
            return
    if "audio" in reason.casefold() and not getattr(self, "_audio_tracks", []):
        self._add_empty_audio_track()
        self._flash_status("Created an audio track. Add or select an audio clip to finish applying this preset.")
        return
    if "audio" in reason.casefold():
        media_path = self._first_media_pool_path(lambda path: path.suffix.casefold() in AUDIO_EXTS)
        if media_path is not None and not self._audio_workspace_candidate():
            self._add_audio_track_with_source(media_path)
            self._flash_status(f"Added audio target from Media Pool: {media_path.name}")
            return
    if "video" in reason.casefold() and not getattr(self, "_tracks", []):
        media_path = self._first_media_pool_path(lambda path: path.suffix.casefold() in VIDEO_EXTS)
        if media_path is not None:
            self._add_track_with_source(media_path)
            track, clip = self._first_video_clip_candidate()
            self._select_workflow_video_clip(track, clip)
            self._flash_status(f"Added video target from Media Pool: {media_path.name}")
        else:
            self._add_empty_track()
            self._flash_status("Created a video track. Add or select a video clip to finish applying this preset.")
        return
    if "video" in reason.casefold():
        track, clip = self._first_video_clip_candidate()
        if self._select_workflow_video_clip(track, clip):
            self._flash_status("Selected the first available video clip as preset target")
            return
    if "color" in reason.casefold() or "grade" in reason.casefold():
        if self._active_track() is not None:
            self._active_color_grade()
            self._flash_status("Prepared color grade target on the active track")
            return
        track, clip = self._first_video_clip_candidate()
        if self._select_workflow_video_clip(track, clip):
            self._active_color_grade()
            self._flash_status("Selected a video clip and prepared a color grade target")
            return
    self._flash_status(reason or "Select a compatible timeline target first")


def _finish_workflow_preset_application(
    self,
    preset,
    *,
    undo_context: str = "workflow",
    status_prefix: str = "Applied",
) -> None:
    name = getattr(preset, "name", "Workflow preset")
    undo_label = f"{undo_context}: {name}"
    label_fn = getattr(self, "_preset_undo_label", None)
    if callable(label_fn):
        try:
            undo_label = label_fn(preset, undo_context)
        except Exception:
            pass
    register = getattr(self, "_register_change", None)
    if callable(register):
        register(undo_label)
    refresh_player = getattr(self, "_refresh_player_tracks", None)
    if callable(refresh_player):
        refresh_player()
    refresh_workbench = getattr(self, "_refresh_workbench", None)
    if callable(refresh_workbench):
        refresh_workbench()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    btn = getattr(self, "command_palette_btn", None)
    pulse = getattr(self, "_pulse_icon_button", None)
    if btn is not None and callable(pulse):
        pulse(btn, base=18, peak=25, duration=210)
    rows = getattr(self, "_pending_workflow_apply_summary_rows", None)
    if rows is not None:
        try:
            delattr(self, "_pending_workflow_apply_summary_rows")
        except Exception:
            pass
    kind = str(getattr(preset, "kind", "") or "")
    if rows is None:
        rows = self._workflow_apply_summary_rows(preset)
    toast = getattr(self, "_show_workflow_apply_summary_toast", None)
    if callable(toast):
        toast(preset, rows)
    focus_ms = getattr(self, "_last_workflow_focus_ms", None)
    focus_tid = getattr(self, "_last_workflow_focus_track_id", None)
    feedback_model = {}
    try:
        from app.preset_feedback import preset_application_feedback_model

        track_label = f"Track {int(focus_tid)}" if focus_tid is not None else ""
        feedback_model = preset_application_feedback_model(
            preset,
            rows,
            focus_ms=int(focus_ms) if focus_ms is not None else None,
            track_label=track_label,
        )
    except Exception:
        feedback_model = {}
    if focus_ms is not None and focus_tid is not None:
        row = getattr(self, "_track_rows", {}).get(int(focus_tid))
        if row is not None:
            try:
                row.flash_timeline_burst(kind or "preset", int(focus_ms))
            except Exception:
                pass
    flash = getattr(self, "_flash_status", None)
    if callable(flash):
        where = ""
        if focus_ms is not None:
            where = f" @ {TrackRow._format_drag_time(focus_ms)}"
        flash(f"{status_prefix}: {name}{where}")
    try:
        from app.video_editor_window import _append_ux_event as append_ux_event

        append_ux_event(
            "preset.apply.success",
            preset_id=str(getattr(preset, "id", "") or ""),
            preset_name=str(name),
            preset_kind=str(kind),
            focus_ms=focus_ms,
            focus_track_id=focus_tid,
            feedback=feedback_model,
        )
    except Exception:
        pass


def _on_workflow_preset_dropped(self, track_id: int, preset_data: object, project_ms: int) -> None:
    try:
        from app.preset_library import EditorPreset, preset_by_id

        data = dict(preset_data or {})
        preset = preset_by_id(str(data.get("id", "") or ""))
        if preset is None:
            preset = EditorPreset.from_dict(data)
    except Exception:
        self._flash_status("Invalid workflow preset")
        return
    self._active_track_id = int(track_id)
    prev_forced_track = getattr(self, "_workflow_forced_track_id", None)
    prev_forced_ms = getattr(self, "_workflow_forced_ms", None)
    self._workflow_forced_track_id = int(track_id)
    self._workflow_forced_ms = int(project_ms)
    try:
        changed = self._apply_editor_preset_object(preset, depth=0, at_ms=int(project_ms))
    finally:
        if prev_forced_track is None:
            try:
                delattr(self, "_workflow_forced_track_id")
            except Exception:
                pass
        else:
            self._workflow_forced_track_id = prev_forced_track
        if prev_forced_ms is None:
            try:
                delattr(self, "_workflow_forced_ms")
            except Exception:
                pass
        else:
            self._workflow_forced_ms = prev_forced_ms
    if changed:
        self._register_change(f"workflow preset drop {getattr(preset, 'kind', '')}: {preset.name}")
        self._refresh_player_tracks()
        self._refresh_workbench()
        try:
            self._player.refresh_current_frame()
        except Exception:
            pass
        row = getattr(self, "_track_rows", {}).get(int(track_id))
        if row is not None:
            try:
                row.flash_timeline_burst("drop", int(project_ms))
                row.update()
            except Exception:
                pass
        self._flash_status(f"Applied: {preset.name}")
    else:
        message = self._preset_apply_failure_message(preset, "Drop blocked")
        try:
            from app.preset_feedback import preset_drop_feedback_model

            model = preset_drop_feedback_model(
                preset,
                can_drop=False,
                reason=message,
                project_ms=int(project_ms),
                track_label=f"Track {int(track_id)}",
            )
            message = f"{model['chip']} 夷?{model['detail']}"
            message = f"{model['chip']} | {model['detail']}"
        except Exception:
            pass
        self._flash_status(message)
        try:
            from app.video_editor_window import _append_ux_event as append_ux_event

            append_ux_event(
                "preset.drop.failed",
                preset_id=str(getattr(preset, "id", "") or ""),
                preset_name=str(getattr(preset, "name", "") or ""),
                track_id=int(track_id),
                project_ms=int(project_ms),
                reason=message,
            )
        except Exception:
            pass


def _begin_preset_live_preview(self, kind: str, payload: dict, label: str = "") -> None:
        self._clear_preset_live_preview()
        kind_text = str(kind or "").casefold()
        self._show_preset_overlay_preview(kind_text, payload, label)
        if any(
            token in kind_text
            for token in ("title", "caption", "sticker", "motion", "template", "audio", "color")
        ):
            return
        track, clip = self._workflow_target_video_clip()
        if track is None or clip is None:
            return
        if "effect" in kind_text:
            old_vf = getattr(clip, "video_filters", None)
            old_chroma = getattr(clip, "chroma_key", None)
            try:
                from app.preset_library import apply_effect_preset_to_clip

                changed = apply_effect_preset_to_clip(clip, payload)
            except Exception:
                changed = False
            if not changed:
                return

            def _restore_effect(c=clip, vf=old_vf, chroma=old_chroma, tr=track) -> None:
                setattr(c, "video_filters", vf)
                setattr(c, "chroma_key", chroma)
                row = getattr(self, "_track_rows", {}).get(getattr(tr, "id", None))
                if row is not None:
                    row.update()

            self._preset_live_preview_restore = _restore_effect
            self._refresh_preview_soft(track)
            return
        if "transition" in kind_text:
            old_type = getattr(clip, "transition_out_type", "")
            old_ms = getattr(clip, "transition_out_ms", 0)
            old_meta = dict(getattr(clip, "transition_preset_meta", {}) or {})
            ttype = str(payload.get("transition_out_type") or payload.get("type") or "")
            if not ttype:
                return
            try:
                clip.transition_out_type = ttype
                clip.transition_out_ms = max(50, int(payload.get("transition_out_ms") or payload.get("ms") or 500))
                clip.transition_preset_meta = {
                    "id": str(payload.get("preset_id") or payload.get("id") or ttype),
                    "name": str(payload.get("name") or payload.get("preset_name") or ttype),
                    "kind": "transition",
                }
            except Exception:
                return

            def _restore_transition(c=clip, old_t=old_type, old_d=old_ms, old_m=old_meta, tr=track) -> None:
                c.transition_out_type = old_t
                c.transition_out_ms = old_d
                c.transition_preset_meta = dict(old_m)
                row = getattr(self, "_track_rows", {}).get(getattr(tr, "id", None))
                if row is not None:
                    row.update()

            self._preset_live_preview_restore = _restore_transition
            self._refresh_preview_soft(track)


def _apply_editor_preset_object(self, preset, *, depth: int = 0, at_ms=None) -> bool:
        if preset is None or depth > 8:
            return False
        if depth == 0:
            self._last_workflow_focus_ms = None
            self._last_workflow_focus_track_id = None
        kind = str(getattr(preset, "kind", "") or "")
        payload = dict(getattr(preset, "payload", {}) or {})

        if kind == "template":
            from app.preset_library import preset_by_id, template_sequence
            base_ms = at_ms
            if base_ms is None:
                base_track, base_clip = self._workflow_target_video_clip()
                base_ms = self._workflow_start_ms(base_track, base_clip)
            changed = False
            for entry in template_sequence(preset):
                condition_ok = getattr(self, "_template_entry_condition_ok", None)
                if callable(condition_ok):
                    ok = condition_ok(entry)
                else:
                    ok = _preset_context._template_entry_condition_ok(self, entry)
                if not ok:
                    continue
                child = preset_by_id(entry.get("preset_id", ""))
                if child is None:
                    continue
                child_at_ms = base_ms
                if entry.get("at_ms") is not None:
                    try:
                        child_at_ms = int(base_ms) + int(entry.get("at_ms", 0) or 0)
                    except Exception:
                        child_at_ms = base_ms
                prev_mode = getattr(self, "_workflow_target_mode", None)
                self._workflow_target_mode = str(entry.get("target", "auto") or "auto")
                try:
                    changed = self._apply_editor_preset_object(
                        child,
                        depth=depth + 1,
                        at_ms=child_at_ms,
                    ) or changed
                finally:
                    if prev_mode is None:
                        try:
                            delattr(self, "_workflow_target_mode")
                        except Exception:
                            pass
                    else:
                        self._workflow_target_mode = prev_mode
            return changed

        if kind == "effect":
            return self._apply_effect_workflow_preset(preset)
        if kind == "transition":
            return self._apply_transition_workflow_preset(preset)
        if kind == "title":
            from app.preset_library import title_drag_payload
            return self._add_title_workflow_actor(title_drag_payload(preset), at_ms=at_ms)
        if kind == "caption_style":
            return self._add_caption_style_workflow_actor(payload, at_ms=at_ms)
        if kind == "sticker":
            return self._add_sticker_workflow_actor(payload, at_ms=at_ms)
        if kind == "motion":
            return self._add_motion_workflow_actor(payload, at_ms=at_ms)
        if kind == "audio":
            return self._apply_audio_workflow_preset(preset)
        if kind == "color":
            return self._apply_color_workflow_preset(preset)
        if kind == "actor":
            return self._add_actor_workflow_preset(payload, at_ms=at_ms)
        return False

# Workflow application helpers moved out of VideoEditorWindow.
def _open_template_browser(self) -> None:
    dlg = QDialog(self)
    dlg.setObjectName("TemplateBrowserDialog")
    dlg.setWindowTitle("Templates")
    dlg.resize(620, 620)
    root = QVBoxLayout(dlg)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)

    header = QWidget()
    header_row = QHBoxLayout(header)
    header_row.setContentsMargins(0, 0, 0, 0)
    header_row.setSpacing(8)
    title = QLabel("Templates")
    title.setObjectName("TemplateBrowserTitle")
    title.setStyleSheet("color:#F8F4EA;font-size:15px;font-weight:900;")
    subtitle = QLabel("Click to apply to the current target, or drag from the left workflow panel for exact timeline placement.")
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet("color:#9EA6C7;font-size:10px;font-weight:700;")
    title_col = QVBoxLayout()
    title_col.setContentsMargins(0, 0, 0, 0)
    title_col.setSpacing(2)
    title_col.addWidget(title)
    title_col.addWidget(subtitle)
    header_row.addLayout(title_col, 1)
    composer_btn = QPushButton("Compose")
    composer_btn.setObjectName("ToolButton")
    composer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    composer_btn.clicked.connect(self._open_template_composer)
    header_row.addWidget(composer_btn)
    root.addWidget(header)

    panel = WorkflowPresetPanel(
        preview_provider=self._preset_preview_frame,
        live_preview_callback=self._begin_preset_live_preview,
        live_preview_clear_callback=self._clear_preset_live_preview,
        kinds={"template"},
        max_height=430,
        placeholder="Search templates",
    )
    panel.setObjectName("TemplateBrowserPanel")

    def _apply_and_close(preset) -> None:
        self._apply_workflow_preset(preset)
        dlg.accept()

    panel.preset_activated.connect(_apply_and_close)
    root.addWidget(panel, 1)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dlg.reject)
    root.addWidget(buttons)
    dlg.exec()


def _apply_auto_preset_plan(self) -> None:
    self._clear_preset_live_preview()
    try:
        from app.preset_library import one_click_preset_plan

        plan = one_click_preset_plan(self._project_summary_for_presets())
    except Exception as exc:
        self._flash_status(f"Auto preset plan failed: {exc}")
        return
    changed = False
    applied: list[str] = []
    for preset in plan[:10]:
        try:
            if self._apply_editor_preset_object(preset):
                changed = True
                applied.append(str(getattr(preset, "name", getattr(preset, "id", "preset"))))
        except Exception:
            continue
    if changed:
        names = ", ".join(applied[:3])
        suffix = f": {names}" if names else ""
        self._register_change(f"auto preset plan{suffix}")
        self._refresh_player_tracks()
        self._refresh_preview_soft()
        self._flash_status(f"Applied auto plan: {len(applied)} preset(s)")
    else:
        first = plan[0] if plan else None
        self._flash_status(self._preset_apply_failure_message(first, "Auto plan blocked"))


def _workflow_apply_summary_text(preset, rows: list[dict] | None = None) -> str:
    kind = str(getattr(preset, "kind", "") or "").replace("_", " ").title()
    name = str(getattr(preset, "name", "Preset") or "Preset")
    rows = list(rows or [])
    usable = [
        row for row in rows
        if str(row.get("status", "") or "") not in {"template", "skipped", "blocked"}
    ]
    if not usable:
        headline = f"{kind or 'Preset'} applied"
        return f"{headline}\n{name}"
    labels = {
        "effect": "FX",
        "transition": "TR",
        "title": "Title",
        "caption_style": "Caption",
        "sticker": "Sticker",
        "motion": "Motion",
        "audio": "Audio",
        "color": "Color",
        "actor": "Actor",
    }
    counts: dict[str, int] = {}
    ordered: list[str] = []
    for row in usable:
        key = str(row.get("kind", "preset") or "preset")
        label = labels.get(key, key.replace("_", " ").title())
        if label not in counts:
            ordered.append(label)
        counts[label] = counts.get(label, 0) + 1
    detail = " 夷?".join(
        f"{label} {counts[label]}" if counts[label] > 1 else label
        for label in ordered[:6]
    )
    more = len(ordered) - 6
    if more > 0:
        detail += f" 夷?+{more}"
    detail = " | ".join(
        f"{label} {counts[label]}" if counts[label] > 1 else label
        for label in ordered[:6]
    )
    if more > 0:
        detail += f" | +{more}"
    headline = "Template applied" if str(getattr(preset, "kind", "") or "") == "template" else "Preset applied"
    return f"{headline}\n{name}\n{len(usable)} step(s): {detail}"


def _show_workflow_apply_summary_toast(
    self,
    preset,
    rows: list[dict] | None = None,
    *,
    duration_ms: int = 3400,
) -> None:
    host = getattr(self, "_preview_host", None)
    if host is None or host.width() <= 0 or host.height() <= 0:
        return
    old = getattr(self, "_workflow_apply_toast", None)
    if old is not None:
        try:
            old.hide()
            old.deleteLater()
        except Exception:
            pass
    text = self._workflow_apply_summary_text(preset, rows)
    toast = QLabel(host)
    toast.setObjectName("WorkflowApplyToast")
    toast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    toast.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    toast.setWordWrap(True)
    toast.setText(text)
    toast.setStyleSheet(
        "QLabel#WorkflowApplyToast{"
        "color:#FFFFFF;"
        "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(255,112,67,232),stop:0.55 rgba(138,124,255,228),stop:1 rgba(99,215,255,220));"
        "border:1px solid rgba(255,255,255,92);"
        "border-radius:18px;"
        "padding:12px 16px;"
        "font-size:13px;"
        "font-weight:900;"
        "}"
    )
    width = max(260, min(520, host.width() - 36))
    height = 86 if "\n" in text else 58
    toast.setGeometry(18, 18, width, height)
    toast.show()
    toast.raise_()
    self._workflow_apply_toast = toast

    def _clear_toast(label=toast) -> None:
        if getattr(self, "_workflow_apply_toast", None) is label:
            self._workflow_apply_toast = None
        try:
            label.hide()
            label.deleteLater()
        except Exception:
            pass

    QTimer.singleShot(max(800, int(duration_ms)), _clear_toast)


def _apply_effect_preset_from_left_panel(self, preset) -> None:
    """Click action for the left Effect Presets browser.

    Drag/drop is still available for precise targeting.  A click applies to
    the selected clip, or the clip under the playhead on the active track.
    """
    if preset is None:
        self._flash_status(tr("veditor.effect_preset.missing"))
        return
    changed = self._apply_editor_preset_object(preset, depth=0)
    if changed:
        self._finish_workflow_preset_application(
            preset,
            undo_context="effect panel",
            status_prefix=tr("veditor.effect_preset.applied"),
        )
        return
    reason = self._preset_apply_failure_reason(preset)
    if reason:
        message = tr("veditor.effect_preset.needs_video_reason", reason=reason)
    else:
        message = tr("veditor.effect_preset.needs_video")
    self._flash_status(message)
    _append_ux_event(
        "preset.effect_panel.failed",
        preset_id=str(getattr(preset, "id", "") or ""),
        preset_name=str(getattr(preset, "name", "") or ""),
        reason=message,
    )


def _apply_effect_workflow_preset(self, preset) -> bool:
    track, clip = self._workflow_target_video_clip()
    if track is None or clip is None:
        return False
    try:
        from app.preset_library import apply_effect_preset_to_clip
        changed = apply_effect_preset_to_clip(clip, preset)
    except Exception:
        changed = False
    if changed:
        self._select_workflow_video_clip(track, clip)
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()
        self._focus_preview_at_workflow_ms(getattr(clip, "timeline_in_ms", 0), track=track)
        self._show_preset_overlay_preview(
            "effect",
            dict(getattr(preset, "payload", {}) or {}),
            str(getattr(preset, "name", "") or "Effect"),
        )
        refresh_wb = getattr(self, "_refresh_workbench", None)
        if callable(refresh_wb):
            refresh_wb()
    return bool(changed)


def _apply_transition_workflow_preset(self, preset) -> bool:
    from app.preset_library import transition_drag_payload

    payload = transition_drag_payload(preset)
    ttype = str(payload.get("type", "dissolve"))
    ms = max(50, int(payload.get("ms", 500)))
    meta = {
        "id": str(payload.get("preset_id") or payload.get("id") or ttype),
        "name": str(payload.get("name") or payload.get("preset_name") or getattr(preset, "name", "") or ttype),
        "kind": "transition",
    }
    targets = []
    if getattr(self, "_selected_clips", None):
        for tid, cid in self._selected_clips:
            track = self._find_track(tid)
            if track is None:
                continue
            clip = next((c for c in getattr(track, "clips", []) if int(c.id) == int(cid)), None)
            if clip is not None:
                targets.append((track, clip))
    if not targets:
        track, clip = self._workflow_target_video_clip()
        if track is not None and clip is not None:
            targets.append((track, clip))
    for track, clip in targets:
        clip.transition_out_type = ttype
        clip.transition_out_ms = ms
        clip.transition_preset_meta = dict(meta)
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()
    if targets:
        focus_track, focus_clip = targets[0]
        self._select_workflow_video_clip(focus_track, focus_clip)
        clip_start = int(getattr(focus_clip, "timeline_in_ms", 0) or 0)
        clip_end = int(getattr(focus_clip, "timeline_out_ms", clip_start) or clip_start)
        focus_ms = max(
            clip_start,
            min(max(clip_start, clip_end - 1), clip_end - max(1, ms // 2)),
        )
        self._focus_preview_at_workflow_ms(focus_ms, track=focus_track)
        self._show_preset_overlay_preview(
            "transition",
            payload,
            str(getattr(preset, "name", "") or ttype),
        )
        refresh_wb = getattr(self, "_refresh_workbench", None)
        if callable(refresh_wb):
            refresh_wb()
    return bool(targets)


def _add_title_workflow_actor(self, payload: dict, *, at_ms=None) -> bool:
    track, clip = self._workflow_target_video_clip()
    if track is None:
        track = self._active_track()
    if track is None:
        return False
    duration_ms = max(TrackRow.TYPO_MIN_DURATION_MS, int(payload.get("duration_ms", 2200) or 2200))
    start = self._workflow_start_ms(track, clip, at_ms)
    end = start + duration_ms
    track_dur = int(getattr(track, "duration_ms", 0) or 0)
    if track_dur > 0:
        end = min(track_dur, end)
        if end - start < TrackRow.TYPO_MIN_DURATION_MS:
            start = max(0, end - TrackRow.TYPO_MIN_DURATION_MS)
    if end <= start:
        return False
    actor = TextClip(start_ms=start, end_ms=end)
    actor.text = str(payload.get("text", "") or payload.get("name", "") or "TITLE")
    actor.style.font_size = int(payload.get("font_size", 48) or 48)
    actor.style.color = str(payload.get("color", "#ffffff") or "#ffffff")
    actor.style.position_x = float(payload.get("x_norm", 0.5))
    actor.style.position_y = float(payload.get("y_norm", 0.78))
    bg = payload.get("bg_color", "")
    if bg:
        actor.style.background_color = str(bg)
    actor.animation.in_animation = str(payload.get("preset_id_in", "fade-in") or "fade-in")
    actor.animation.out_animation = str(payload.get("preset_id_out", "fade-out") or "fade-out")
    typo_preset_id = str(payload.get("typography_preset_id", "") or "")
    if typo_preset_id:
        try:
            from app.typo_presets import apply_preset, get_preset
            typo_preset = get_preset(typo_preset_id)
            if typo_preset is not None:
                apply_preset(actor, typo_preset)
        except Exception:
            pass
    track.typography_actors.append(actor)
    track.typography_actors.sort(key=lambda c: c.start_ms)
    row = self._track_rows.get(track.id)
    if row is not None:
        row.update()
    self._on_typography_changed(track.id)
    self._last_workflow_text_actor = actor
    self._focus_preview_at_workflow_ms(start, track=track)
    self._show_preset_overlay_preview("title", payload, actor.text)
    refresh_wb = getattr(self, "_refresh_workbench", None)
    if callable(refresh_wb):
        refresh_wb()
    return True


def _add_caption_style_workflow_actor(self, payload: dict, *, at_ms=None) -> bool:
    data = {
        "text": "CAPTION",
        "duration_ms": int(payload.get("duration_ms", 1800) or 1800),
        "font_size": int(payload.get("font_size", 42) or 42),
        "color": str(payload.get("fill", payload.get("color", "#ffffff")) or "#ffffff"),
        "x_norm": float(payload.get("x_norm", 0.5)),
        "y_norm": float(payload.get("y_norm", 0.82)),
        "preset_id_in": str(payload.get("animation", "fade-in") or "fade-in"),
        "preset_id_out": "fade-out",
    }
    changed = self._add_title_workflow_actor(data, at_ms=at_ms)
    if changed:
        actor = getattr(self, "_last_workflow_text_actor", None)
        if actor is not None:
            stroke = payload.get("stroke")
            if stroke:
                actor.style.outline_color = str(stroke)
            if "stroke_width" in payload:
                actor.style.outline_width = int(payload.get("stroke_width", 0) or 0)
        self._show_preset_overlay_preview("caption", data, data.get("text", "CAPTION"))
    return changed


def _add_sticker_workflow_actor(self, payload: dict, *, at_ms=None) -> bool:
    shape = str(payload.get("shape", "") or "").lower()
    text = str(payload.get("text", "") or {
        "crosshair": "HIT",
        "arrow": "->",
        "bubble": "REACTION",
        "subscribe": "SUB",
        "circle": "O",
        "censor": "HIDE",
        "badge": "NEW",
        "step": "1",
        "burst": "LIKE",
    }.get(shape, "STICKER"))
    data = {
        "text": text,
        "duration_ms": int(payload.get("duration_ms", 1200) or 1200),
        "font_size": int(44 * float(payload.get("scale", 1.0) or 1.0)),
        "color": str(payload.get("color", "#ff6a35") or "#ff6a35"),
        "x_norm": float(payload.get("x_norm", 0.62)),
        "y_norm": float(payload.get("y_norm", 0.36)),
        "preset_id_in": str(payload.get("animation", "pop-in") or "pop-in"),
        "preset_id_out": "pop-out",
    }
    changed = self._add_title_workflow_actor(data, at_ms=at_ms)
    if changed:
        self._show_preset_overlay_preview("sticker", data, text)
    return changed


def _add_motion_workflow_actor(self, payload: dict, *, at_ms=None) -> bool:
    track, clip = self._workflow_target_video_clip()
    if track is None:
        return False
    start = self._workflow_start_ms(track, clip, at_ms)
    duration = int(payload.get("duration_ms", 1200) or 1200)
    if "keyframes" in payload and clip is not None:
        duration = max(
            300,
            int(getattr(clip, "timeline_out_ms", start + duration) or start + duration)
            - int(getattr(clip, "timeline_in_ms", start) or start),
        )
    end = max(start + 300, start + duration)
    z_id = max((z.id for z in getattr(track, "zoom_actors", [])), default=0) + 1
    actor = ZoomActor(
        id=z_id,
        start_ms=start,
        end_ms=end,
        zoom_in_ms=max(80, min(500, duration // 4)),
        zoom_out_ms=max(80, min(500, duration // 4)),
    )
    track.zoom_actors.append(actor)
    track.zoom_actors.sort(key=lambda z: z.start_ms)
    row = self._track_rows.get(track.id)
    if row is not None:
        row.update()
    self._focus_preview_at_workflow_ms(start, track=track)
    self._show_preset_overlay_preview("motion", payload, str(payload.get("name", "") or "Motion"))
    refresh_wb = getattr(self, "_refresh_workbench", None)
    if callable(refresh_wb):
        refresh_wb()
    return True


def _add_actor_workflow_preset(self, payload: dict, *, at_ms=None) -> bool:
    actor_kind = str(payload.get("actor_kind", "") or "").casefold()
    try:
        start_ms = int(at_ms if at_ms is not None else self._player.position())
    except Exception:
        start_ms = 0
    if actor_kind == "live2d":
        if not getattr(self, "_live2d_actor_tracks", []):
            self._add_live2d_actor_track()
        rows = getattr(self, "_live2d_lane_rows", [])
        if not rows:
            return False
        model_path = self._actor_model_candidate("live2d")
        before = len(getattr(getattr(rows[0], "_track", None), "clips", []) or [])
        rows[0]._create_clip(model_path, max(0, start_ms))
        self._on_live2d_clip_changed()
        after = len(getattr(getattr(rows[0], "_track", None), "clips", []) or [])
        return after > before
    if actor_kind == "spine":
        if not getattr(self, "_spine_actor_tracks", []):
            self._add_spine_actor_track()
        rows = getattr(self, "_actor_lane_rows", [])
        if not rows:
            return False
        model_path = self._actor_model_candidate("spine")
        before = len(getattr(getattr(rows[0], "_track", None), "clips", []) or [])
        rows[0]._create_clip(model_path, max(0, start_ms))
        self._on_actor_clip_changed()
        after = len(getattr(getattr(rows[0], "_track", None), "clips", []) or [])
        return after > before
    return False


def _preset_preview_frame(self):
    pix = getattr(self, "_preview_pixmap", None)
    if pix is None or pix.isNull():
        return None
    return pix.scaled(
        QSize(360, 180),
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )


def _refresh_user_preset_panels(self) -> None:
    for attr in (
        "_effects_preset_panel",
        "_title_presets_panel",
        "_workflow_presets_panel",
    ):
        panel = getattr(self, attr, None)
        refresh = getattr(panel, "refresh_library", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass


def _clear_preset_overlay_preview(self) -> None:
    label = getattr(self, "_preset_preview_overlay", None)
    self._preset_preview_overlay = None
    self._preset_preview_overlay_payload = None
    if label is not None:
        try:
            label.hide()
            label.deleteLater()
        except Exception:
            pass


def _clear_preset_live_preview(self) -> None:
    self._clear_preset_overlay_preview()
    restore = getattr(self, "_preset_live_preview_restore", None)
    if not restore:
        return
    self._preset_live_preview_restore = None
    try:
        restore()
    except Exception:
        pass
    self._refresh_preview_soft()


def _save_selected_effect_preset(self) -> None:
    _track, clip = self._selected_video_clip()
    if clip is None:
        self._flash_status("Select a clip before saving an effect preset")
        return
    payload = self._effect_payload_from_clip(clip)
    if not payload:
        self._flash_status("Selected clip has no effect settings to save")
        return
    name, ok = QInputDialog.getText(self, "Save Effect Preset", "Preset name:")
    if not ok:
        return
    name = str(name or "").strip()
    if not name:
        self._flash_status("Preset name is empty")
        return
    slug = "".join(ch.casefold() if ch.isalnum() else "-" for ch in name).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug or "effect"
    try:
        from app.preset_library import EditorPreset, save_user_preset

        preset = EditorPreset(
            id=f"user-effect-{slug}-{int(time.time())}",
            kind="effect",
            name=name,
            description="Saved from the selected clip.",
            tags=("user", "custom", "effect"),
            payload=payload,
        )
        save_user_preset(preset)
    except Exception as exc:
        self._flash_status(f"Preset save failed: {exc}")
        return
    self._refresh_user_preset_panels()
    self._flash_status(f"Saved preset: {name}")


def _import_preset_pack(self) -> None:
    path, _ = QFileDialog.getOpenFileName(
        self,
        "Import Preset Pack",
        str(Path.home()),
        "Preset packs (*.json);;All files (*.*)",
    )
    if not path:
        return
    try:
        from app.preset_library import import_preset_pack

        count = import_preset_pack(path)
    except Exception as exc:
        self._flash_status(f"Preset import failed: {exc}")
        return
    if count <= 0:
        self._flash_status("Preset import failed: no valid presets")
        return
    self._refresh_user_preset_panels()
    self._flash_status(f"Imported {count} preset(s)")


def _export_user_preset_pack(self) -> None:
    path, _ = QFileDialog.getSaveFileName(
        self,
        "Export User Preset Pack",
        str(Path.home() / "tigercapture-user-presets.json"),
        "Preset packs (*.json);;All files (*.*)",
    )
    if not path:
        return
    try:
        from app.preset_library import export_user_presets

        export_user_presets(path)
    except Exception as exc:
        self._flash_status(f"Preset export failed: {exc}")
        return
    self._flash_status(f"Exported presets: {Path(path).name}")


def _preset_undo_label(self, preset, source: str) -> str:
    kind = str(getattr(preset, "kind", "") or "preset")
    name = str(getattr(preset, "name", getattr(preset, "id", "preset")) or "preset")
    return f"{source} preset {kind}: {name}"


def _workflow_apply_summary_rows(self, preset) -> list[dict]:
    rows_fn = getattr(self, "_preset_application_plan_rows", None)
    if not callable(rows_fn):
        return []
    try:
        rows = rows_fn(preset)
    except Exception:
        return []
    return [dict(row or {}) for row in (rows or []) if isinstance(row, dict)]


def _apply_workflow_preset(self, preset) -> None:
    changed = self._apply_editor_preset_object(preset, depth=0)
    if changed:
        self._finish_workflow_preset_application(preset)
    else:
        message = self._preset_apply_failure_message(preset, "Preset blocked")
        self._flash_status(message)
        _append_ux_event(
            "preset.apply.failed",
            preset_id=str(getattr(preset, "id", "") or ""),
            preset_name=str(getattr(preset, "name", "") or ""),
            reason=message,
        )


def _apply_audio_workflow_preset(self, preset) -> bool:
    candidate = self._audio_workspace_candidate()
    if candidate is None:
        return False
    track, clip = candidate
    try:
        from app.audio_workflow import apply_track_mix_preset
        from app.preset_library import apply_audio_preset_to_clip

        changed = apply_audio_preset_to_clip(clip, preset)
        tags = {str(tag).lower() for tag in getattr(preset, "tags", ())}
        if "dialogue" in tags or "voice" in tags or "podcast" in tags:
            apply_track_mix_preset(
                track,
                {"bus_id": "dialogue", "label": getattr(track, "label", "") or "Dialogue"},
            )
        elif "music" in tags:
            apply_track_mix_preset(
                track,
                {"bus_id": "music", "label": getattr(track, "label", "") or "Music"},
            )
    except Exception:
        changed = False
    row = self._audio_rows.get(track.id)
    if row is not None:
        row.update()
    self._refresh_audio_workspace_panel()
    return bool(changed)


def _apply_color_workflow_preset(self, preset) -> bool:
    grade = self._active_color_grade()
    if grade is None:
        return False
    try:
        self._on_professional_color_preset_picked(preset)
        return True
    except Exception:
        return False

