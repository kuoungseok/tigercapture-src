"""Right-dock Workbench panel — TigerCapture's contextual properties.

Populated by the editor when the user selects a track / clip on the
timeline. Replaces the old "Inspector" name (Phase 3 of the Media
Editor Pro plan): "Workbench" is TigerCapture's signature term —
the place where you put your selected piece down to mess with its
fades, speed, volume, and (Phase 2) the per-clip node graph.

Phase B1 was read-only; Phase B2 added editable sliders for fade in /
fade out / volume. Phase 1.5+ will expand this to per-clip transform,
opacity, and node-graph routing as the multi-clip data model lights
up the renderer.
"""
from __future__ import annotations

import json
from os.path import basename
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.sound_editor_panel import SoundEditorPanel
from app.studio_slider import StudioSlider
from app.style import FONT_FAMILY, editor_scrollbar_qss
from app.video_editor_actor_evidence import ArPbrEvidenceCard, Live2DActorEvidenceCard


def _format_ms(ms: int) -> str:
    if ms is None or ms < 0:
        ms = 0
    s = int(ms) // 1000
    return f"{s // 60}:{s % 60:02d}.{(int(ms) % 1000) // 100}"


def _compact_source_label(path: Any, *, max_chars: int = 34) -> str:
    """Short right-dock source label; keep the full path in the tooltip."""
    if not path:
        return "--"
    try:
        from pathlib import Path

        p = Path(str(path))
        parent = p.parent.name
        name = p.name
        label = f"{parent}/{name}" if parent else name
    except Exception:
        label = str(path)
    if len(label) <= max_chars:
        return label
    keep_tail = max(12, min(22, max_chars - 10))
    return f"{label[:8]}...{label[-keep_tail:]}"


def vfx_node_graphs_from_track(track: Any) -> list[dict[str, Any]]:
    """Collect mini VFX graph payloads attached to track/node objects."""
    graphs: list[dict[str, Any]] = []

    def _append_payload(payload: Any) -> None:
        if callable(payload):
            try:
                payload = payload()
            except Exception:
                return
        if isinstance(payload, dict) and payload.get("nodes"):
            graphs.append(payload)

    _append_payload(getattr(track, "vfx_node_graph", None))
    for raw in list(getattr(track, "vfx_node_graphs", []) or []):
        _append_payload(raw)
    for entry in list(getattr(track, "node_item_chain", []) or []):
        node = entry[0] if isinstance(entry, (tuple, list)) and entry else entry
        if isinstance(node, dict):
            _append_payload(node.get("vfx_node_graph"))
            _append_payload(node.get("vfx_node_graph_payload"))
            continue
        _append_payload(getattr(node, "vfx_node_graph", None))
        _append_payload(getattr(node, "vfx_node_graph_payload", None))
    return graphs


def vfx_node_graph_status_for_track(track: Any) -> dict[str, Any]:
    """Return a compact Workbench-ready VFX graph QA payload."""
    graphs = vfx_node_graphs_from_track(track)
    if not graphs:
        return {
            "ok": False,
            "graph_count": 0,
            "node_count": 0,
            "summary": "VFX graph: none",
            "warnings": [],
        }
    from app.post_pipeline_workflow import vfx_node_graph_qa_report

    report = vfx_node_graph_qa_report(graphs)
    kinds = ", ".join(sorted(str(k) for k in report.get("kind_counts", {}).keys())[:5])
    state = "OK" if report.get("ok") else "Review"
    warnings = [str(v) for v in report.get("warnings", []) or [] if str(v)]
    detail = f"{int(report.get('graph_count', 0) or 0)} graph(s), {int(report.get('node_count', 0) or 0)} node(s)"
    if kinds:
        detail = f"{detail} | {kinds}"
    if warnings:
        detail = f"{detail} | {warnings[0]}"
    payload = dict(report)
    payload["summary"] = f"VFX graph: {state} | {detail}"
    return payload


def vfx_node_graph_overview_for_track(track: Any, *, limit: int = 7) -> list[dict[str, str]]:
    """Return ordered mini-node labels for the Workbench VFX graph strip."""
    graphs = vfx_node_graphs_from_track(track)
    if not graphs:
        return []
    graph = graphs[0]
    nodes = list(graph.get("nodes", []) or []) if isinstance(graph, dict) else []
    warnings = set(str(v) for v in (graph.get("validation_warnings", []) or []) if str(v))
    if not warnings and isinstance(graph, dict):
        try:
            from app.post_pipeline_workflow import VFXNodeGraph

            warnings = set(VFXNodeGraph.from_dict(graph).validation_warnings())
        except Exception:
            warnings = set()
    label_map = {
        "media_in": "Media",
        "chroma_key": "Keyer",
        "b_spline_roto": "Roto",
        "clean_plate": "Clean",
        "planar_tracker": "Track",
        "merge": "Merge",
        "title": "Title",
        "output": "Out",
    }
    rows: list[dict[str, str]] = []
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or raw.get("type") or "")
        node_id = str(raw.get("id") or kind or "node")
        label = label_map.get(kind, kind.replace("_", " ").title() or node_id)
        state = "ok"
        if any(node_id in warning for warning in warnings):
            state = "review"
        rows.append({
            "id": node_id,
            "kind": kind or "node",
            "label": label,
            "state": state,
        })
        if len(rows) >= max(1, int(limit)):
            break
    if len(nodes) > len(rows):
        rows.append({
            "id": "more",
            "kind": "more",
            "label": f"+{len(nodes) - len(rows)}",
            "state": "info",
        })
    return rows


def vfx_node_graph_detail_text_for_track(track: Any) -> str:
    """Return a readable VFX graph QA/details report for Workbench dialogs."""
    graphs = vfx_node_graphs_from_track(track)
    if not graphs:
        return "VFX Graph\n\nNo VFX graph payload is attached to this track."
    status = vfx_node_graph_status_for_track(track)
    lines = [
        "VFX Graph",
        "",
        str(status.get("summary") or "VFX graph: Review"),
        f"Graphs: {int(status.get('graph_count', 0) or 0)}",
        f"Nodes: {int(status.get('node_count', 0) or 0)}",
    ]
    qa_gates = [str(v) for v in status.get("qa_gates", []) or [] if str(v)]
    if qa_gates:
        lines.extend(["", "QA Gates:"])
        lines.extend(f"- {gate}" for gate in qa_gates)
    warnings = [str(v) for v in status.get("warnings", []) or [] if str(v)]
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)
    for graph_idx, graph in enumerate(graphs, start=1):
        if not isinstance(graph, dict):
            continue
        lines.extend([
            "",
            f"Graph {graph_idx}",
            f"Output: {graph.get('output_node', 'out')}",
            f"Cache: {graph.get('cache_policy', 'preview_export_locked')}",
            "Nodes:",
        ])
        for node in list(graph.get("nodes", []) or []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id") or "")
            kind = str(node.get("kind") or node.get("type") or "")
            inputs = ", ".join(str(v) for v in (node.get("inputs", []) or [])) or "-"
            params = node.get("params", {}) or {}
            compact_params = ""
            if isinstance(params, dict) and params:
                compact_params = " | " + json.dumps(params, ensure_ascii=False, sort_keys=True)[:140]
            lines.append(f"- {node_id}: {kind} <- {inputs}{compact_params}")
    return "\n".join(lines)


class _Row(QWidget):
    """Two-column key/value row used throughout the workbench."""

    def __init__(self, label: str, value: str = "—", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorValueRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(25)
        self.setMaximumHeight(30)
        h = QHBoxLayout(self)
        h.setContentsMargins(9, 3, 9, 3)
        h.setSpacing(8)
        self._key_text = label
        self._key = QLabel(label, self)
        self._key.setObjectName("InspectorRowKey")
        # Explicit hex colours — ``palette(text)`` was resolving to
        # default-palette black on this Qt build, which made the
        # value text invisible on the dark dock background.
        self._key.setStyleSheet(
            "color: #9A9FA8; font-size: 9px; font-weight: 620; "
            "letter-spacing: 0px; border: none; background: transparent;"
        )
        self._key.setFixedWidth(50)
        self._val = QLabel(value, self)
        self._val.setObjectName("InspectorRowValue")
        self._val.setStyleSheet(
            "color: #E8EAEE; font-size: 10px; font-weight: 620; "
            "border: none; background: transparent;"
        )
        self._val.setWordWrap(False)
        self._val.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )
        self.setStyleSheet(
            "QWidget#InspectorValueRow {"
            "background: transparent;"
            "border: none;"
            "border-bottom: 1px solid rgba(178, 186, 202, 24);"
            "border-radius: 0px;"
            "}"
            "QWidget#InspectorValueRow:hover {"
            "background: rgba(255, 255, 255, 7);"
            "border-bottom: 1px solid rgba(210, 218, 235, 48);"
            "}"
        )
        h.addWidget(self._key, alignment=Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(self._val, stretch=1)

    def set_label(self, text: str) -> None:
        self._key_text = text
        self._key.setText(text)

    def set_value(self, v: str, tooltip: str | None = None) -> None:
        text = str(v or "--")
        self._val.setText(text)
        self.setToolTip(tooltip or text)
        self._val.setToolTip(tooltip or text)


class _SliderRow(QWidget):
    """Editable label + slider + readout. Emits ``value_changed(int)``
    on every drag tick (used to drive the live preview) and
    ``value_committed(int)`` once on slider release (used to push a
    history entry — registering on every tick would flood the stack
    with one snapshot per pixel of slider travel)."""

    value_changed = Signal(int)
    value_committed = Signal(int)

    def __init__(
        self,
        label: str,
        minimum: int,
        maximum: int,
        formatter=None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorSliderRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(36)
        self.setMaximumHeight(42)
        self._formatter = formatter or (lambda v: str(int(v)))
        self._suppress = False
        v = QVBoxLayout(self)
        v.setContentsMargins(9, 4, 9, 5)
        v.setSpacing(3)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        self._key = QLabel(label, self)
        self._key.setObjectName("InspectorSliderKey")
        self._key.setStyleSheet(
            "color: #9A9FA8; font-size: 9px; font-weight: 620; "
            "letter-spacing: 0px; border: none; background: transparent;"
        )
        self._key.setFixedWidth(62)
        self._readout = QLabel(self._formatter(0), self)
        self._readout.setObjectName("InspectorSliderValue")
        self._readout.setStyleSheet(
            "color: #E8EAEE; font-size: 10px; font-weight: 620; "
            "border: none; background: transparent;"
        )
        self._readout.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        head.addWidget(self._key)
        head.addWidget(self._readout, stretch=1)

        self._slider = StudioSlider("accent", self)
        self._slider.setRange(int(minimum), int(maximum))
        self._slider.setValue(0)
        self._slider.valueChanged.connect(self._on_slider)
        self._slider.sliderReleased.connect(self._on_release)
        self.setStyleSheet(
            "QWidget#InspectorSliderRow {"
            "background: transparent;"
            "border: none;"
            "border-bottom: 1px solid rgba(178, 186, 202, 24);"
            "border-radius: 0px;"
            "}"
            "QWidget#InspectorSliderRow:hover {"
            "background: rgba(255, 255, 255, 7);"
            "border-bottom: 1px solid rgba(210, 218, 235, 48);"
            "}"
        )

        v.addLayout(head)
        v.addWidget(self._slider)

    def set_label(self, text: str) -> None:
        self._key.setText(text)

    def set_value(self, v: int) -> None:
        """Push value without re-emitting."""
        self._suppress = True
        try:
            self._slider.setValue(int(v))
            self._readout.setText(self._formatter(int(v)))
        finally:
            self._suppress = False

    def set_enabled(self, enabled: bool) -> None:
        self._slider.setEnabled(bool(enabled))

    def _on_slider(self, value: int) -> None:
        self._readout.setText(self._formatter(int(value)))
        if self._suppress:
            return
        self.value_changed.emit(int(value))

    def _on_release(self) -> None:
        # Slider released — drive the history-savepoint signal. The
        # editor wires this to ``_register_change`` while ignoring
        # the per-tick ``value_changed`` so the undo stack only sees
        # one entry per gesture.
        if self._suppress:
            return
        self.value_committed.emit(int(self._slider.value()))


class _AudioEvidenceCard(QWidget):
    """Compact real-state audio workspace rendered from the selected clip."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._track = None
        self._clip = None
        self.setObjectName("AudioEvidenceCard")
        self.setMinimumHeight(178)
        self.setMaximumHeight(230)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_clip(self, track: Any, clip: Any) -> None:
        self._track = track
        self._clip = clip
        self.update()

    @staticmethod
    def _fmt_level(value: float) -> str:
        try:
            return f"{float(value):+.1f} dB"
        except Exception:
            return "+0.0 dB"

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = self.rect().adjusted(1, 1, -1, -1)
        bg = QColor("#101010")
        card = QColor("#151515")
        line = QColor("#292929")
        text = QColor("#D9DDE2")
        muted = QColor("#8C929B")
        signal = QColor("#B8C5B4")
        signal_dim = QColor("#78857C")
        accent = QColor("#9BA6B6")

        p.fillRect(self.rect(), bg)
        p.setPen(QPen(line, 1))
        p.setBrush(card)
        p.drawRoundedRect(root, 7, 7)

        clip = self._clip
        track = self._track
        duration_ms = int(getattr(clip, "duration_ms", 0) or 0) if clip is not None else 0
        speed = float(getattr(clip, "speed", 1.0) or 1.0) if clip is not None else 1.0
        volume_db = float(getattr(track, "master_volume", 0.0) or 0.0) if track is not None else 0.0
        fade_in = int(getattr(clip, "fade_in_ms", 0) or 0) if clip is not None else 0
        fade_out = int(getattr(clip, "fade_out_ms", 0) or 0) if clip is not None else 0

        font = p.font()
        font.setPixelSize(10)
        font.setBold(True)
        p.setFont(font)
        p.setPen(text)
        p.drawText(root.adjusted(10, 8, -10, -root.height() + 28), Qt.AlignmentFlag.AlignLeft, "Extracted Audio Workspace")

        font.setPixelSize(8)
        font.setBold(False)
        p.setFont(font)
        p.setPen(muted)
        meta = f"{_format_ms(duration_ms)}  |  {self._fmt_level(volume_db)}  |  {speed:.2f}x"
        p.drawText(root.adjusted(10, 25, -10, -root.height() + 45), Qt.AlignmentFlag.AlignLeft, meta)

        chip_x = root.right() - 156
        for idx, label in enumerate(("linked", "stereo", "export")):
            chip = QRectF(chip_x + idx * 50, root.top() + 8, 44, 16)
            p.setPen(QPen(QColor("#34383D"), 1))
            p.setBrush(QColor(255, 255, 255, 7))
            p.drawRoundedRect(chip, 5, 5)
            p.setPen(QColor("#AEB5BE"))
            p.drawText(chip, Qt.AlignmentFlag.AlignCenter, label)

        wave_rect = QRectF(root.left() + 10, root.top() + 50, max(20, root.width() - 84), max(48, root.height() - 124))
        spec_rect = QRectF(root.left() + 10, root.bottom() - 58, max(20, root.width() - 84), 46)
        meter_rect = QRectF(root.right() - 54, root.top() + 50, 34, max(60, root.height() - 72))

        for rect, label in ((wave_rect, "waveform"), (spec_rect, "spectrum")):
            p.setPen(QPen(QColor("#24272B"), 1))
            p.setBrush(QColor("#111111"))
            p.drawRoundedRect(rect, 5, 5)
            p.setPen(QColor("#5F6670"))
            p.drawText(rect.adjusted(6, 4, -6, -4), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, label)

        wf = getattr(clip, "waveform", None) if clip is not None else None
        if wf is not None and getattr(wf, "size", 0):
            try:
                import numpy as np

                data = np.asarray(wf, dtype=np.float32)
                mono = (data[0] + data[1]) * 0.5 if data.ndim == 2 and data.shape[0] == 2 else data.ravel()
                if mono.size:
                    samples = np.linspace(0, mono.size - 1, max(2, int(wave_rect.width())), dtype=np.int32)
                    vals = mono[samples]
                    peak = max(float(np.max(np.abs(vals))), 0.005)
                    mid = wave_rect.center().y() + 5
                    amp = max(8.0, wave_rect.height() * 0.35)
                    path = QPainterPath()
                    path.moveTo(QPointF(wave_rect.left() + 3, mid))
                    for i, val in enumerate(vals):
                        x = wave_rect.left() + 3 + i / max(len(vals) - 1, 1) * (wave_rect.width() - 6)
                        y = mid - float(val) / peak * amp
                        path.lineTo(QPointF(x, y))
                    p.setPen(QPen(signal, 1.0))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawPath(path)
                    p.setPen(QPen(QColor(255, 255, 255, 24), 0.75))
                    p.drawLine(int(wave_rect.left() + 4), int(mid), int(wave_rect.right() - 4), int(mid))
            except Exception:
                pass
        else:
            p.setPen(muted)
            p.drawText(wave_rect, Qt.AlignmentFlag.AlignCenter, "waveform pending")

        bins = getattr(clip, "spectrum_bins", None) if clip is not None else None
        try:
            import numpy as np

            if bins is None or not getattr(bins, "size", 0):
                if wf is not None and getattr(wf, "size", 0):
                    data = np.asarray(wf, dtype=np.float32)
                    mono = (data[0] + data[1]) * 0.5 if data.ndim == 2 and data.shape[0] == 2 else data.ravel()
                    chunks = np.array_split(np.abs(mono), 32)
                    vals = np.asarray([float(c.mean()) if c.size else 0.0 for c in chunks], dtype=np.float32)
                    peak = max(float(vals.max()), 0.005)
                    vals = vals / peak
                else:
                    vals = np.zeros(32, dtype=np.float32)
            else:
                vals = np.asarray(bins, dtype=np.float32).ravel()[:32]
                peak = max(float(vals.max()), 0.005)
                vals = vals / peak
            bar_w = max(1.0, (spec_rect.width() - 12) / max(len(vals), 1))
            for i, val in enumerate(vals):
                h = float(val) * (spec_rect.height() - 18)
                x = spec_rect.left() + 6 + i * bar_w
                y = spec_rect.bottom() - 5 - h
                t = i / max(len(vals) - 1, 1)
                col = QColor(int(120 + 26 * t), int(137 + 21 * t), int(128 + 30 * t), 172)
                p.fillRect(QRectF(x, y, max(1.0, bar_w - 1), h), col)
        except Exception:
            pass

        p.setPen(QPen(QColor("#24272B"), 1))
        p.setBrush(QColor("#111111"))
        p.drawRoundedRect(meter_rect, 5, 5)
        p.setPen(QColor("#6B727B"))
        p.drawText(meter_rect.adjusted(0, 5, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "mix")
        meter_top = meter_rect.top() + 26
        meter_h = meter_rect.height() - 42
        level = 0.35
        if wf is not None and getattr(wf, "size", 0):
            try:
                import numpy as np

                data = np.asarray(wf, dtype=np.float32)
                level = min(1.0, max(0.08, float(np.sqrt(np.mean(data * data))) * 2.6))
            except Exception:
                pass
        for idx, label in enumerate(("L", "R")):
            x = meter_rect.left() + 8 + idx * 10
            p.fillRect(QRectF(x, meter_top, 5, meter_h), QColor("#1D1F20"))
            fill_h = meter_h * level * (1.0 if idx == 0 else 0.92)
            grad = QLinearGradient(x, meter_top + meter_h, x, meter_top)
            grad.setColorAt(0.0, signal_dim)
            grad.setColorAt(1.0, signal)
            p.fillRect(QRectF(x, meter_top + meter_h - fill_h, 5, fill_h), grad)
            p.setPen(QColor("#7A818A"))
            p.drawText(QRectF(x - 2, meter_rect.bottom() - 17, 10, 10), Qt.AlignmentFlag.AlignCenter, label)

        if duration_ms > 0 and (fade_in > 0 or fade_out > 0):
            p.setPen(QPen(accent, 1))
            if fade_in > 0:
                fx = wave_rect.left() + min(1.0, fade_in / duration_ms) * wave_rect.width()
                p.drawLine(int(fx), int(wave_rect.top() + 18), int(fx), int(wave_rect.bottom() - 4))
            if fade_out > 0:
                fx = wave_rect.right() - min(1.0, fade_out / duration_ms) * wave_rect.width()
                p.drawLine(int(fx), int(wave_rect.top() + 18), int(fx), int(wave_rect.bottom() - 4))

        p.end()


class _TypographyEvidenceCard(QWidget):
    """Compact real-state card for text actors attached to the selected clip."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._actors: list[Any] = []
        self.setObjectName("TypographyEvidenceCard")
        self.setMinimumHeight(132)
        self.setMaximumHeight(170)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_actors(self, actors: list[Any]) -> None:
        self._actors = list(actors or [])
        self.update()

    @staticmethod
    def _key_series(actor: Any, channel: str) -> list[dict[str, Any]]:
        raw_keys = getattr(actor, "keyframes", None)
        if not isinstance(raw_keys, dict):
            animation = getattr(actor, "animation", None)
            custom = getattr(animation, "custom_params", {}) if animation is not None else {}
            raw_keys = custom.get("action_keyframes") if isinstance(custom, dict) else {}
        series = raw_keys.get(channel, []) if isinstance(raw_keys, dict) else []
        if isinstance(series, dict):
            series = series.get("keyframes") or series.get("keys") or []
        return [row for row in series if isinstance(row, dict)] if isinstance(series, (list, tuple)) else []

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtCore import QPoint, QRectF
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPolygon

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = self.rect().adjusted(1, 1, -1, -1)
        p.fillRect(self.rect(), QColor("#101010"))
        p.setPen(QPen(QColor("#292929"), 1))
        p.setBrush(QColor("#151515"))
        p.drawRoundedRect(root, 7, 7)

        actor = self._actors[0] if self._actors else None
        title = str(getattr(actor, "text", "") or "Typography") if actor is not None else "Typography"
        key_count = WorkbenchPanel._text_keyframe_count(actor) if actor is not None else 0
        duration = (
            int(getattr(actor, "end_ms", 0) or 0) - int(getattr(actor, "start_ms", 0) or 0)
            if actor is not None
            else 0
        )
        style = getattr(actor, "style", None)

        font = p.font()
        font.setPixelSize(10)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#F2F0EA"))
        p.drawText(root.adjusted(10, 8, -10, -root.height() + 28), Qt.AlignmentFlag.AlignLeft, "Typography Workspace")

        font.setPixelSize(8)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor("#8F95A0"))
        meta = f"{_format_ms(duration)}  |  {key_count} keys"
        if style is not None:
            meta = f"{meta}  |  {int(getattr(style, 'font_size', 0) or 0)} px"
        p.drawText(root.adjusted(10, 25, -10, -root.height() + 45), Qt.AlignmentFlag.AlignLeft, meta)

        chip = QRectF(root.right() - 118, root.top() + 8, 98, 17)
        grad = QLinearGradient(chip.left(), chip.top(), chip.right(), chip.bottom())
        grad.setColorAt(0.0, QColor(86, 80, 94, 190))
        grad.setColorAt(1.0, QColor(65, 72, 86, 175))
        p.setPen(QPen(QColor("#807B88"), 1))
        p.setBrush(grad)
        p.drawRoundedRect(chip, 5, 5)
        p.setPen(QColor("#F4F0EA"))
        p.drawText(chip.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title[:16])

        text_rect = QRectF(root.left() + 10, root.top() + 48, root.width() - 20, 26)
        p.setPen(QPen(QColor("#24272B"), 1))
        p.setBrush(QColor("#111111"))
        p.drawRoundedRect(text_rect, 5, 5)
        font.setPixelSize(13)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#F8FAFC"))
        p.drawText(text_rect.adjusted(9, 0, -9, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)

        lane_top = int(root.top() + 84)
        channels = (("opacity", "#D8C89E"), ("scale", "#9EA7B7"), ("position_y", "#A9B8AD"))
        span = max(1, int(duration))
        start_ms = int(getattr(actor, "start_ms", 0) or 0) if actor is not None else 0
        for idx, (channel, color) in enumerate(channels):
            y = lane_top + idx * 18
            label_rect = QRectF(root.left() + 10, y - 5, 58, 13)
            rail = QRectF(root.left() + 72, y, root.width() - 94, 2)
            font.setPixelSize(8)
            font.setBold(False)
            p.setFont(font)
            p.setPen(QColor("#8F95A0"))
            p.drawText(label_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, channel.replace("_", " "))
            p.setPen(QPen(QColor("#303236"), 1))
            p.drawLine(int(rail.left()), int(rail.center().y()), int(rail.right()), int(rail.center().y()))
            p.setPen(QPen(QColor(20, 20, 24, 150), 1))
            p.setBrush(QColor(color))
            for key in self._key_series(actor, channel):
                try:
                    raw_time = int(round(float(key.get("time_ms", key.get("ms", 0)))))
                except Exception:
                    continue
                rel = raw_time - start_ms if start_ms <= raw_time <= start_ms + span else raw_time
                rel = max(0, min(span, rel))
                x = int(rail.left() + (rel / span) * max(1, rail.width()))
                p.drawPolygon(QPolygon([
                    QPoint(x, y - 4),
                    QPoint(x + 4, y),
                    QPoint(x, y + 4),
                    QPoint(x - 4, y),
                ]))
        p.end()


class _EditPointEvidenceCard(QWidget):
    """Compact real-state card for timeline cuts and adjacent edit points."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._track = None
        self._clip = None
        self._previous_clip = None
        self._next_clip = None
        self.setObjectName("EditPointEvidenceCard")
        self.setMinimumHeight(138)
        self.setMaximumHeight(164)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_context(self, track: Any, clip: Any) -> None:
        self._track = track
        self._clip = clip
        self._previous_clip = None
        self._next_clip = None
        clips = sorted(
            list(getattr(track, "clips", []) or []),
            key=lambda row: int(getattr(row, "timeline_in_ms", 0) or 0),
        )
        try:
            selected_id = int(getattr(clip, "id", -1) or -1)
        except Exception:
            selected_id = -1
        for index, candidate in enumerate(clips):
            if int(getattr(candidate, "id", -2) or -2) != selected_id:
                continue
            if index > 0:
                self._previous_clip = clips[index - 1]
            if index + 1 < len(clips):
                self._next_clip = clips[index + 1]
            break
        self.update()

    @staticmethod
    def has_edit_point(track: Any, clip: Any) -> bool:
        if track is None or clip is None:
            return False
        clips = sorted(
            list(getattr(track, "clips", []) or []),
            key=lambda row: int(getattr(row, "timeline_in_ms", 0) or 0),
        )
        if len(clips) < 2:
            return False
        selected_id = int(getattr(clip, "id", -1) or -1)
        for index, candidate in enumerate(clips):
            if int(getattr(candidate, "id", -2) or -2) != selected_id:
                continue
            if index > 0:
                prev = clips[index - 1]
                if abs(int(getattr(prev, "timeline_out_ms", 0) or 0) - int(getattr(candidate, "timeline_in_ms", 0) or 0)) <= 1:
                    return True
            if index + 1 < len(clips):
                nxt = clips[index + 1]
                if abs(int(getattr(candidate, "timeline_out_ms", 0) or 0) - int(getattr(nxt, "timeline_in_ms", 0) or 0)) <= 1:
                    return True
        return False

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtCore import QPoint, QRectF
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPolygon

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = self.rect().adjusted(1, 1, -1, -1)
        p.fillRect(self.rect(), QColor("#101010"))
        p.setPen(QPen(QColor("#2A2A2A"), 1))
        p.setBrush(QColor("#151515"))
        p.drawRoundedRect(root, 7, 7)

        clip = self._clip
        prev_clip = self._previous_clip
        next_clip = self._next_clip
        cut_ms = int(getattr(clip, "timeline_in_ms", 0) or 0)
        if prev_clip is not None:
            cut_ms = int(getattr(prev_clip, "timeline_out_ms", cut_ms) or cut_ms)
        transition_source = prev_clip if prev_clip is not None else clip
        ttype = str(getattr(transition_source, "transition_out_type", "") or "")
        tms = int(getattr(transition_source, "transition_out_ms", 0) or 0) if ttype else 0

        font = p.font()
        font.setPixelSize(10)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#F0EEE8"))
        p.drawText(root.adjusted(10, 7, -10, -root.height() + 25), Qt.AlignmentFlag.AlignLeft, "Edit Point Workspace")

        font.setPixelSize(8)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor("#8F95A0"))
        meta = f"cut {_format_ms(cut_ms)}"
        if ttype:
            meta = f"{meta}  |  {ttype} {_format_ms(tms)}"
        p.drawText(root.adjusted(10, 24, -10, -root.height() + 41), Qt.AlignmentFlag.AlignLeft, meta)

        rail = QRectF(root.left() + 10, root.top() + 50, root.width() - 20, 43)
        p.setPen(QPen(QColor("#2A2D31"), 1))
        p.setBrush(QColor("#111111"))
        p.drawRoundedRect(rail, 5, 5)
        half = rail.width() * 0.5
        left_rect = QRectF(rail.left() + 5, rail.top() + 7, max(12.0, half - 9), 18)
        right_rect = QRectF(rail.left() + half + 4, rail.top() + 7, max(12.0, half - 9), 18)
        for rect, selected, label, source_clip in (
            (left_rect, prev_clip is None and clip is not None, "A", prev_clip or clip),
            (right_rect, prev_clip is not None and clip is not None, "B", clip if prev_clip is not None else next_clip),
        ):
            grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
            if selected:
                grad.setColorAt(0.0, QColor(86, 90, 96, 128))
                grad.setColorAt(1.0, QColor(56, 61, 66, 126))
                border = QColor("#B8BEC7")
            else:
                grad.setColorAt(0.0, QColor(54, 58, 63, 94))
                grad.setColorAt(1.0, QColor(38, 42, 47, 92))
                border = QColor("#555A62")
            p.setPen(QPen(border, 1))
            p.setBrush(grad)
            p.drawRoundedRect(rect, 3, 3)
            p.setPen(QColor("#DCE1E8"))
            p.drawText(rect.adjusted(5, 0, -5, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            if source_clip is not None:
                dur = max(
                    0,
                    int(getattr(source_clip, "timeline_out_ms", 0) or 0)
                    - int(getattr(source_clip, "timeline_in_ms", 0) or 0),
                )
                font.setPixelSize(7)
                font.setBold(False)
                p.setFont(font)
                p.setPen(QColor("#8F95A0"))
                p.drawText(rect.adjusted(20, 0, -6, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, _format_ms(dur))
                font.setPixelSize(8)
                font.setBold(False)
                p.setFont(font)

        x = int(rail.left() + half)
        p.setPen(QPen(QColor("#D8C89E"), 1))
        p.drawLine(x, int(rail.top() + 2), x, int(rail.bottom() - 2))
        p.setBrush(QColor("#D8C89E"))
        p.setPen(QPen(QColor(18, 18, 18, 150), 1))
        p.drawPolygon(QPolygon([
            QPoint(x - 4, int(rail.top() + 4)),
            QPoint(x + 4, int(rail.top() + 4)),
            QPoint(x, int(rail.top() + 10)),
        ]))
        p.drawPolygon(QPolygon([
            QPoint(x - 4, int(rail.bottom() - 4)),
            QPoint(x + 4, int(rail.bottom() - 4)),
            QPoint(x, int(rail.bottom() - 10)),
        ]))
        if ttype:
            t_rect = QRectF(x - 26, rail.top() + 7, 52, rail.height() - 14)
            p.setPen(QPen(QColor("#7A725F"), 1))
            p.setBrush(QColor(216, 200, 158, 38))
            p.drawRoundedRect(t_rect, 3, 3)
            font.setPixelSize(7)
            font.setBold(True)
            p.setFont(font)
            p.setPen(QColor("#E5D8B8"))
            p.drawText(t_rect, Qt.AlignmentFlag.AlignCenter, "TR")

        trim_y = rail.top() + 29
        label_font = p.font()
        label_font.setPixelSize(7)
        label_font.setBold(False)
        p.setFont(label_font)
        for rect, label, active in (
            (QRectF(rail.left() + 7, trim_y, half - 15, 8), "trim out", prev_clip is not None),
            (QRectF(rail.left() + half + 8, trim_y, half - 15, 8), "trim in", clip is not None),
        ):
            p.setPen(QPen(QColor("#35383D"), 1))
            p.drawLine(int(rect.left()), int(rect.center().y()), int(rect.right()), int(rect.center().y()))
            p.setBrush(QColor("#D8C89E") if active else QColor("#555A62"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(rect.center().x() - 2, rect.center().y() - 2, 4, 4))
            p.setPen(QColor("#8F95A0"))
            p.drawText(rect.adjusted(0, -9, 0, 0), Qt.AlignmentFlag.AlignCenter, label)

        footer = QRectF(root.left() + 10, root.bottom() - 28, root.width() - 20, 17)
        p.setPen(QPen(QColor("#292929"), 1))
        p.setBrush(QColor("#111111"))
        p.drawRoundedRect(footer, 4, 4)
        font.setPixelSize(8)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor("#AAB1C1"))
        footer_text = "selected side B" if prev_clip is not None else "selected side A"
        if ttype:
            footer_text += "   |   transition handle active"
        p.drawText(footer.adjusted(7, 0, -7, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, footer_text)

        p.end()


class _FxStackRail(QWidget):
    """Small real-state rail for the selected clip's FX/transition stack."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._state: dict[str, Any] = {}
        self.setObjectName("FxStackRail")
        self.setFixedHeight(32)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_state(self, **state: Any) -> None:
        self._state = dict(state)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(1, 0, -1, -1)

        state = self._state
        nodes = [
            ("SRC", True, "#717982"),
            ("FX", bool(state.get("has_clip_fx")), "#7C776B"),
            ("TR", bool(state.get("has_transition")), "#847B68"),
            ("GRAPH", bool(state.get("has_vfx_graph")), "#707782"),
            ("OUT", True, "#717982"),
        ]
        count = len(nodes)
        left = root.left() + 2
        top = root.top() + 4
        width = max(27.0, min(64.0, (root.width() - 4 - (count - 1) * 6) / count))
        center_y = top + 8
        p.setPen(QPen(QColor(132, 138, 148, 40), 1))
        p.drawLine(int(left + width * 0.5), int(center_y), int(left + (width + 6) * (count - 1) + width * 0.5), int(center_y))
        rects: list[QRectF] = []
        for index, (_label, active, color) in enumerate(nodes):
            r = QRectF(left + index * (width + 6), top, width, 16)
            rects.append(r)
            grad = QLinearGradient(r.left(), r.top(), r.right(), r.bottom())
            if active:
                base = QColor(color)
                grad.setColorAt(0.0, QColor(base.red(), base.green(), base.blue(), 82))
                grad.setColorAt(1.0, QColor(34, 36, 39, 118))
                border = QColor(176, 183, 193, 68)
                text = QColor("#E7EAF0")
            else:
                grad.setColorAt(0.0, QColor(38, 41, 45, 62))
                grad.setColorAt(1.0, QColor(25, 27, 30, 68))
                border = QColor(76, 81, 88, 36)
                text = QColor("#747A83")
            p.setPen(QPen(border, 1))
            p.setBrush(grad)
            p.drawRoundedRect(r, 4, 4)
            if active:
                p.setPen(QPen(QColor(220, 225, 236, 44), 1))
                p.drawLine(int(r.left() + 5), int(r.top() + 2), int(r.right() - 5), int(r.top() + 2))
            font = p.font()
            font.setPixelSize(8)
            font.setBold(True)
            p.setFont(font)
            p.setPen(text)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, _label)

        footer = str(state.get("footer") or "")
        if footer:
            font = p.font()
            font.setPixelSize(7)
            font.setBold(False)
            p.setFont(font)
            p.setPen(QColor("#8F95A0"))
            p.drawText(
                QRectF(root.left() + 4, root.bottom() - 9, root.width() - 8, 8),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                footer,
            )
        p.end()


class _NodeRow(QWidget):
    """Single clickable row in the workbench's NodeGraph section.

    Phase 2 of the Media Editor Pro plan introduced ``track.node_graph``
    as a per-track effects DAG; today there's only a Color node, but
    LUT / Blur / TrackMatte will land in later phases. The row shows
    an icon + name + status badge and emits ``clicked(kind)`` so the
    editor can route focus to the matching panel."""

    clicked = Signal(str)

    def __init__(self, kind: str, label: str, parent=None) -> None:
        super().__init__(parent)
        self._kind = kind
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)
        self.setStyleSheet(
            "QWidget { background-color: #171A25; border:1px solid #2A2E3C; border-radius: 8px; }"
            "QWidget:hover { background-color: #222635; border-color:#555A70; }"
        )
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 0, 8, 0)
        h.setSpacing(8)
        self._icon = QLabel("", self)
        self._icon.setFixedSize(18, 18)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setPixmap(app_icon({"color": "color"}.get(kind, "target"), size=15).pixmap(icon_size(15)))
        h.addWidget(self._icon)
        self._label = QLabel(label, self)
        self._label.setStyleSheet(
            "color: #F2F0EA; font-size: 11px; font-weight: 700;"
        )
        h.addWidget(self._label)
        h.addStretch(1)
        self._status = QLabel("", self)
        self._status.setStyleSheet("color: #8F95A8; font-size: 10px;")
        h.addWidget(self._status)

    def set_status(self, text: str, accent: bool = False) -> None:
        self._status.setText(text)
        if accent:
            self._status.setStyleSheet(
                "color: #E85D35; font-size: 10px; font-weight: 700;"
            )
        else:
            self._status.setStyleSheet("color: #8F95A8; font-size: 10px;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._kind)
            return
        super().mousePressEvent(event)


class WorkbenchPanel(QWidget):
    """Right-dock contextual workbench. Call ``set_video_track``,
    ``set_audio_clip``, or ``clear()`` to update the displayed
    contents. Editable sliders for fade in / fade out (both video
    tracks and audio clips) and volume (audio clips). The panel emits
    signals; the editor decides what to mutate."""

    # Editable slider signals — value units in parentheses.
    fade_in_changed = Signal(int)         # ms — live during slider drag
    fade_out_changed = Signal(int)        # ms — live during slider drag
    volume_changed = Signal(float)        # dB — live during slider drag
    # Slider-release pulses for the history stack. Editor connects
    # these to ``_register_change`` so undo gets one entry per
    # gesture instead of one per tick.
    fade_in_committed = Signal(int)
    fade_out_committed = Signal(int)
    volume_committed = Signal(float)
    mmd_physics_rotation_hint_scale_changed = Signal(float)
    mmd_physics_spring_response_changed = Signal(float)
    mmd_physics_rotation_hint_scale_committed = Signal(float)
    mmd_physics_spring_response_committed = Signal(float)
    open_clip_fx_requested = Signal()
    toggle_clip_fx_requested = Signal()
    clear_clip_fx_requested = Signal()
    clear_clip_transition_requested = Signal()
    open_live2d_editor_requested = Signal()
    apply_live2d_performance_source_requested = Signal()
    open_vtuber_studio_requested = Signal()
    open_mmd_editor_requested = Signal()
    sound_editor_changed = Signal()
    advanced_sound_lab_requested = Signal(object, object)
    # Phase 2 NodeGraph integration: emitted when the user clicks one
    # of the node rows. Editor wires this to scroll/expand the
    # corresponding panel (currently only "color" → Color section).
    node_focused = Signal(str)

    # Slider ranges — picked to cover practical use without ceding
    # screen real-estate to extreme values.
    FADE_MAX_MS = 5000
    VOLUME_MIN_DB = -60.0
    VOLUME_MAX_DB = 12.0
    MMD_ROTATION_HINT_MIN = 0
    MMD_ROTATION_HINT_MAX = 30
    MMD_SPRING_RESPONSE_MIN = 15
    MMD_SPRING_RESPONSE_MAX = 150

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorPanel")
        self.setStyleSheet(
            f"QWidget#InspectorPanel {{"
            f"background:#101112; border:none; border-radius:0px; font-family:{FONT_FAMILY};"
            f"}}"
            "QWidget#InspectorRows {"
            "background:rgba(255,255,255,4);"
            "border:1px solid rgba(178,186,202,18);"
            "border-radius:6px;"
            "}"
            "QStackedWidget#InspectorStack {"
            "background:#101112; border:none;"
            "}"
            "QWidget#InspectorPage {"
            "background:#101112; border:none;"
            "}"
            "QLabel#InspectorEmpty {"
            "color:#9AA1AE; font-size:10px; padding:8px;"
            "background:rgba(255,255,255,5);"
            "border:1px solid rgba(178,186,202,18); border-radius:6px;"
            "}"
            "QWidget#InspectorTabs {"
            "background:transparent; border:none; border-radius:0px;"
            "}"
            "QWidget#InspectorTabs[fxMode='true'] {"
            "background:#101112; border:none; border-bottom:1px solid #202225;"
            "}"
            "QWidget#InspectorPaletteStrip {"
            "background:transparent; border:none; border-radius:0px;"
            "}"
            "QPushButton#InspectorTab {"
            "background:#15181C; color:#9EA4AD; border:1px solid rgba(178,186,202,20);"
            "border-radius:5px; padding:0px; font-size:1px; font-weight:600;"
            "min-width:21px; min-height:17px;"
            "}"
            "QPushButton#InspectorTab:hover { background:#20252B; color:#FFFFFF; border-color:rgba(220,225,238,74); }"
            "QPushButton#InspectorTab:checked {"
            "background:#252A31;"
            "color:#FFFFFF; border-color:rgba(238,242,250,92);"
            "}"
            "QPushButton#InspectorTab[fxMode='true'] {"
            "background:transparent; color:#8E949C; border:1px solid transparent;"
            "border-radius:3px; min-width:16px; min-height:14px;"
            "}"
            "QPushButton#InspectorTab[fxMode='true']:hover {"
            "background:#20252B; color:#ECEFF4; border-color:rgba(220,225,238,54);"
            "}"
            "QPushButton#InspectorTab[fxMode='true']:checked {"
            "background:#1B1E23; color:#FFFFFF; border-color:rgba(238,242,250,78);"
            "}"
            "QFrame#InspectorSwatch {"
            "border:1px solid rgba(255,255,255,42); border-radius:9px;"
            "}"
            "QWidget#FxSummary {"
            "background:#101112; border:none; border-top:1px solid rgba(178,186,202,20); border-radius:0px;"
            "}"
            "QLabel#FxSummaryTitle {"
            "color:#DDE2EA; font-size:9px; font-weight:650; background:transparent; border:none; padding:0px;"
            "}"
            "QLabel#FxSummaryBody {"
            "color:#D1D6DF; font-size:10px; background:transparent; border:none; padding:0px;"
            "}"
            "QPushButton#FxSummaryButton {"
            "background:rgba(255,255,255,6); color:#DCE1EA;"
            "border:1px solid rgba(178,186,202,24); border-radius:5px; padding:0px;"
            "min-width:23px; min-height:20px;"
            "}"
            "QPushButton#FxSummaryButton:hover {"
            "background:rgba(255,255,255,12); border-color:rgba(220,225,238,68); color:#FFFFFF;"
            "}"
            "QPushButton#FxSummaryButton:disabled {"
            "color:#5C626B; background:rgba(255,255,255,3); border-color:rgba(178,186,202,10);"
            "}"
            "QWidget#EffectNodeControls {"
            "background:#101112; border:none; border-top:1px solid rgba(178,186,202,20); border-radius:0px;"
            "}"
            "QLabel#EffectNodeTitle {"
            "color:#DDE2EA; font-size:10px; font-weight:650; background:transparent; border:none; padding:0px;"
            "}"
            "QLabel#EffectFieldLabel {"
            "color:#949BA6; font-size:9px; font-weight:560; background:transparent; border:none;"
            "}"
            "QLabel#EffectFieldValue {"
            "color:#DDE2EA; font-size:9px; font-weight:560; background:transparent; border:none;"
            "}"
            "QCheckBox#EffectCheck {"
            "color:#B9C0CB; font-size:9px; background:transparent; border:none; spacing:6px;"
            "}"
            "QCheckBox#EffectCheck::indicator {"
            "width:11px; height:11px; border-radius:5px; border:1px solid #565C65; background:#181A1D;"
            "}"
            "QCheckBox#EffectCheck::indicator:checked {"
            "background:#A5ABB5; border-color:#D7DBE2;"
            "}"
            "QLineEdit#EffectPath {"
            "background:rgba(255,255,255,5); color:#D6DAE2; border:1px solid rgba(178,186,202,22);"
            "border-radius:5px; padding:3px 6px; font-size:9px;"
            "}"
            "QPushButton#EffectIconButton, QPushButton#EffectActionButton {"
            "background:rgba(255,255,255,6); color:#DCE1EA;"
            "border:1px solid rgba(178,186,202,24); border-radius:5px; padding:0px;"
            "}"
            "QPushButton#EffectIconButton:hover, QPushButton#EffectActionButton:hover {"
            "background:rgba(255,255,255,12); border-color:rgba(220,225,238,68); color:#FFFFFF;"
            "}"
            "QLabel#EffectNote {"
            "color:#AEB6C2; font-size:9px; background:rgba(255,255,255,5);"
            "border:1px solid rgba(178,186,202,16); border-radius:5px; padding:5px;"
            "}"
            "QWidget#Live2DMappingCard {"
            "background:transparent; border:none; border-top:1px solid rgba(178,186,202,18); border-radius:0px;"
            "}"
            "QLabel#Live2DMappingTitle {"
            "color:#D9DDE5; font-size:9px; font-weight:620; letter-spacing:0px;"
            "background:transparent; border:none; padding:0px;"
            "}"
            "QLabel#Live2DMappingBody {"
            "color:#929AA6; font-size:9px;"
            "background:transparent; border:none; padding:0px;"
            "}"
            "QLabel#Live2DMappingMeta {"
            "color:#C5CBD4; font-size:9px; font-weight:560;"
            "background:transparent; border:none; border-bottom:1px solid rgba(178,186,202,14);"
            "border-radius:0px; padding:2px 0px 4px 0px;"
            "}"
            "QWidget#VfxGraphStrip {"
            "background:transparent; border:none; border-top:1px solid rgba(178,186,202,14); border-radius:0px;"
            "}"
            "QPushButton[VfxGraphNode='true'] {"
            "background:rgba(255,255,255,5); color:#DCE1EA; border:1px solid rgba(178,186,202,22);"
            "border-radius:4px; padding:2px 6px; font-size:8px; font-weight:590;"
            "}"
            "QPushButton[VfxGraphNode='true']:hover {"
            "border-color:rgba(220,225,238,76); background:rgba(255,255,255,10);"
            "}"
            "QPushButton[VfxGraphNodeState='ok'] {"
            "border-color:rgba(125,154,142,58); background:rgba(116,148,137,12);"
            "}"
            "QPushButton[VfxGraphNodeState='review'] {"
            "border-color:rgba(146,126,108,60); background:rgba(152,126,102,12);"
            "}"
            "QLabel[VfxGraphArrow='true'] {"
            "color:#6F7896; font-size:10px; font-weight:900;"
            "}"
            "QSlider::groove:horizontal {"
            "background:#292D31; height:2px; border-radius:1px; border:none;"
            "}"
            "QSlider::sub-page:horizontal {"
            "background:#7A8797; border-radius:1px;"
            "}"
            "QSlider::add-page:horizontal {"
            "background:#292D31; border-radius:1px; border:none;"
            "}"
            "QSlider::handle:horizontal {"
            "background:#A1A9B3; border:1px solid #D5D9DF; width:10px;"
            "height:10px; margin:-4px 0; border-radius:5px;"
            "}"
            "QSlider::handle:horizontal:hover {"
            "background:#A6B7CD; border-color:#FFFFFF;"
            "}"
            + editor_scrollbar_qss("QWidget#InspectorPanel")
        )
        # Minimum-height floor — without it, when the right dock is
        # short the subtitle panel's min-height pushes the workbench
        # to zero and the rows seem to disappear.
        self.setMinimumHeight(260)
        # ``_target`` remembers what the sliders are currently
        # editing. ``("video", track)`` or ``("audio", track, clip)``
        # — the editor reads this when it gets a slider signal so it
        # can route the mutation to the right object.
        self._target: tuple | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        self._title = QLabel(tr("workbench.empty.title"), self)
        self._title.setStyleSheet(
            "color: #F2F0EA; font-weight: 680; font-size: 11px;"
        )

        self._subtitle = QLabel(tr("workbench.empty.subtitle"), self)
        self._subtitle.setStyleSheet(
            "color: #8F95A8; font-size: 10px;"
        )
        self._subtitle.setWordWrap(True)

        self._palette_strip = QWidget(self)
        self._palette_strip.setObjectName("InspectorPaletteStrip")
        self._palette_strip.setFixedHeight(12)
        palette_layout = QHBoxLayout(self._palette_strip)
        palette_layout.setContentsMargins(8, 3, 8, 3)
        palette_layout.setSpacing(2)
        for colors in (
            ("#8A6258", "#80626A"),
            ("#6B6488", "#79718E"),
            ("#5F838B", "#638C82"),
            ("#8B7355", "#8A6659"),
            ("#20242C", "#3A4250"),
            ("#66866E", "#637E91"),
        ):
            swatch = QFrame(self._palette_strip)
            swatch.setObjectName("InspectorSwatch")
            swatch.setFixedSize(34, 4)
            swatch.setStyleSheet(
                "QFrame#InspectorSwatch{"
                f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {colors[0]},stop:1 {colors[1]});"
                "border:none;border-radius:2px;}"
            )
            palette_layout.addWidget(swatch)

        self._title_row = QWidget(self)
        self._title_row.setObjectName("InspectorTitleRow")
        self._title_row.setFixedHeight(17)
        title_row_layout = QHBoxLayout(self._title_row)
        title_row_layout.setContentsMargins(5, 0, 8, 0)
        title_row_layout.setSpacing(8)
        title_row_layout.addWidget(self._title, 0)
        title_row_layout.addWidget(self._palette_strip, 0)
        title_row_layout.addStretch(1)
        root.addWidget(self._title_row)
        root.addWidget(self._subtitle)

        self._inspector_tab = "clip"
        self._inspector_tabs = QWidget(self)
        self._inspector_tabs.setObjectName("InspectorTabs")
        tabs_layout = QHBoxLayout(self._inspector_tabs)
        tabs_layout.setContentsMargins(5, 1, 5, 0)
        tabs_layout.setSpacing(2)
        tabs_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._inspector_tab_group = QButtonGroup(self)
        self._inspector_tab_group.setExclusive(True)
        self._inspector_tab_buttons: dict[str, QPushButton] = {}
        for tab_id, label in (
            ("clip", "Clip"),
            ("fx", "FX"),
            ("mask", "Mask"),
            ("audio", "Audio"),
            ("meta", "Meta"),
        ):
            btn = QPushButton("", self._inspector_tabs)
            btn.setObjectName("InspectorTab")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(label)
            btn.setAccessibleName(label)
            btn.setFixedSize(24, 18)
            btn.setIcon(app_icon({
                "clip": "video",
                "fx": "sliders",
                "mask": "scope",
                "audio": "audio",
                "meta": "list",
            }.get(tab_id, "list"), size=15))
            btn.setIconSize(icon_size(13))
            btn.clicked.connect(lambda _checked=False, t=tab_id: self._set_inspector_tab(t))
            if tab_id == "clip":
                btn.setChecked(True)
            self._inspector_tab_group.addButton(btn)
            self._inspector_tab_buttons[tab_id] = btn
            tabs_layout.addWidget(btn)
        tabs_layout.addStretch(1)
        root.addWidget(self._inspector_tabs)

        self._tab_stack = QStackedWidget(self)
        self._tab_stack.setObjectName("InspectorStack")
        self._tab_pages: dict[str, QWidget] = {}
        self._tab_layouts: dict[str, QVBoxLayout] = {}
        for tab_id, empty_text in (
            ("clip", "Select a clip or track to edit clip properties."),
            ("fx", "Select a video track to edit its effect graph."),
            ("mask", "Select a mask-capable node to edit tracking and masks."),
            ("audio", "Select an audio clip to edit audio properties."),
            ("meta", "Selection metadata appears here."),
        ):
            page = QWidget(self._tab_stack)
            page.setObjectName("InspectorPage")
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            empty = QLabel(empty_text, page)
            empty.setObjectName("InspectorEmpty")
            empty.setWordWrap(True)
            layout.addWidget(empty)
            setattr(self, f"_{tab_id}_empty_label", empty)
            layout.addStretch(1)
            self._tab_pages[tab_id] = page
            self._tab_layouts[tab_id] = layout
            self._tab_stack.addWidget(page)
        root.addWidget(self._tab_stack, stretch=1)

        # Property rows always live in the layout; they switch their
        # text contents between "selection placeholder" and concrete
        # values rather than hide/show. Always-visible avoids the
        # earlier issue where ``hide()`` during init left the rows
        # invisible even after ``set_video_track`` ran.
        self._rows_host = QWidget(self._tab_pages["clip"])
        self._rows_host.setObjectName("InspectorRows")
        self._rows_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._rows_host.setMaximumWidth(480)
        rows = QVBoxLayout(self._rows_host)
        rows.setContentsMargins(6, 4, 6, 5)
        rows.setSpacing(0)

        self._row_name = _Row(tr("workbench.row.name"), parent=self._rows_host)
        self._row_source = _Row(tr("workbench.row.source"), parent=self._rows_host)
        self._row_duration = _Row(tr("workbench.row.duration"), parent=self._rows_host)
        self._row_position = _Row(tr("workbench.row.position"), parent=self._rows_host)
        self._row_fade_in = _SliderRow(
            tr("workbench.row.fade_in"),
            0, self.FADE_MAX_MS,
            formatter=_format_ms,
            parent=self._rows_host,
        )
        self._row_fade_out = _SliderRow(
            tr("workbench.row.fade_out"),
            0, self.FADE_MAX_MS,
            formatter=_format_ms,
            parent=self._rows_host,
        )
        # Volume slider stores int 10ths of dB (so -600..120 maps to
        # -60.0..+12.0 dB). Forward to listeners as float dB.
        self._row_volume = _SliderRow(
            tr("workbench.row.volume"),
            int(self.VOLUME_MIN_DB * 10),
            int(self.VOLUME_MAX_DB * 10),
            formatter=lambda raw: f"{raw / 10.0:+.1f} dB",
            parent=self._rows_host,
        )
        self._row_mmd_cloth_hair = _SliderRow(
            "Cloth/Hair",
            self.MMD_ROTATION_HINT_MIN,
            self.MMD_ROTATION_HINT_MAX,
            formatter=lambda raw: f"{raw / 100.0:.2f}",
            parent=self._rows_host,
        )
        self._row_mmd_follow = _SliderRow(
            "Follow",
            self.MMD_SPRING_RESPONSE_MIN,
            self.MMD_SPRING_RESPONSE_MAX,
            formatter=lambda raw: f"{raw / 100.0:.2f}",
            parent=self._rows_host,
        )
        self._row_speed = _Row(tr("workbench.row.speed"), parent=self._rows_host)

        self._row_fade_in.value_changed.connect(self.fade_in_changed.emit)
        self._row_fade_out.value_changed.connect(self.fade_out_changed.emit)
        self._row_volume.value_changed.connect(
            lambda raw: self.volume_changed.emit(raw / 10.0),
        )
        self._row_mmd_cloth_hair.value_changed.connect(
            lambda raw: self.mmd_physics_rotation_hint_scale_changed.emit(raw / 100.0),
        )
        self._row_mmd_follow.value_changed.connect(
            lambda raw: self.mmd_physics_spring_response_changed.emit(raw / 100.0),
        )
        self._row_fade_in.value_committed.connect(self.fade_in_committed.emit)
        self._row_fade_out.value_committed.connect(self.fade_out_committed.emit)
        self._row_volume.value_committed.connect(
            lambda raw: self.volume_committed.emit(raw / 10.0),
        )
        self._row_mmd_cloth_hair.value_committed.connect(
            lambda raw: self.mmd_physics_rotation_hint_scale_committed.emit(raw / 100.0),
        )
        self._row_mmd_follow.value_committed.connect(
            lambda raw: self.mmd_physics_spring_response_committed.emit(raw / 100.0),
        )

        for row in (
            self._row_name, self._row_source, self._row_duration,
            self._row_position, self._row_fade_in, self._row_fade_out,
            self._row_volume, self._row_mmd_cloth_hair, self._row_mmd_follow,
            self._row_speed,
        ):
            rows.addWidget(row)
        self._edit_point_evidence_card = _EditPointEvidenceCard(self._rows_host)
        rows.addWidget(self._edit_point_evidence_card)
        self._edit_point_evidence_card.hide()
        self._live2d_mapping_host = QWidget(self._rows_host)
        self._live2d_mapping_host.setObjectName("Live2DMappingCard")
        self._live2d_mapping_host.setMaximumHeight(74)
        live2d_layout = QVBoxLayout(self._live2d_mapping_host)
        live2d_layout.setContentsMargins(6, 4, 6, 5)
        live2d_layout.setSpacing(3)
        live2d_header = QHBoxLayout()
        live2d_header.setContentsMargins(0, 0, 0, 0)
        live2d_header.setSpacing(5)
        self._live2d_mapping_title = QLabel("Performance Source", self._live2d_mapping_host)
        self._live2d_mapping_title.setObjectName("Live2DMappingTitle")
        live2d_header.addWidget(self._live2d_mapping_title, 1)
        live2d_actions = QHBoxLayout()
        live2d_actions.setContentsMargins(0, 0, 0, 0)
        live2d_actions.setSpacing(3)

        def _setup_live2d_action_button(button: QPushButton, icon_name: str, tooltip: str) -> None:
            button.setObjectName("FxSummaryButton")
            button.setText("")
            button.setIcon(app_icon(icon_name, size=13, color="#D7DAE7"))
            button.setIconSize(icon_size(12))
            button.setFixedSize(24, 21)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)

        self._live2d_open_editor_btn = QPushButton("Live2D Viewer", self._live2d_mapping_host)
        _setup_live2d_action_button(
            self._live2d_open_editor_btn,
            "live2d",
            "Open the model and motion editor for this Live2D actor clip",
        )
        self._live2d_open_editor_btn.clicked.connect(self.open_live2d_editor_requested.emit)
        self._live2d_apply_perf_btn = QPushButton("Map Source", self._live2d_mapping_host)
        _setup_live2d_action_button(
            self._live2d_apply_perf_btn,
            "link",
            "Apply the active Performance Source to this Live2D actor clip",
        )
        self._live2d_apply_perf_btn.clicked.connect(self.apply_live2d_performance_source_requested.emit)
        self._live2d_studio_btn = QPushButton("VTuber Studio", self._live2d_mapping_host)
        _setup_live2d_action_button(
            self._live2d_studio_btn,
            "video",
            "Open Program Output, Source Tracking, and Avatar Mapping monitors",
        )
        self._live2d_studio_btn.clicked.connect(self.open_vtuber_studio_requested.emit)
        live2d_actions.addWidget(self._live2d_open_editor_btn)
        live2d_actions.addWidget(self._live2d_apply_perf_btn)
        live2d_actions.addWidget(self._live2d_studio_btn)
        live2d_header.addLayout(live2d_actions)
        live2d_layout.addLayout(live2d_header)
        self._live2d_mapping_meta = QLabel("Viewer / mapping / studio ready", self._live2d_mapping_host)
        self._live2d_mapping_meta.setObjectName("Live2DMappingMeta")
        self._live2d_mapping_meta.setWordWrap(False)
        live2d_layout.addWidget(self._live2d_mapping_meta)
        self._live2d_mapping_body = QLabel(
            "No mapped source yet | subject: not mapped",
            self._live2d_mapping_host,
        )
        self._live2d_mapping_body.setObjectName("Live2DMappingBody")
        self._live2d_mapping_body.setWordWrap(False)
        live2d_layout.addWidget(self._live2d_mapping_body)
        rows.addWidget(self._live2d_mapping_host)
        self._live2d_mapping_host.hide()
        self._live2d_evidence_card = Live2DActorEvidenceCard(self._rows_host)
        rows.addWidget(self._live2d_evidence_card)
        self._live2d_evidence_card.hide()
        self._mmd_editor_host = QWidget(self._rows_host)
        self._mmd_editor_host.setObjectName("Live2DMappingCard")
        mmd_editor_layout = QHBoxLayout(self._mmd_editor_host)
        mmd_editor_layout.setContentsMargins(6, 4, 6, 5)
        mmd_editor_layout.setSpacing(5)
        mmd_editor_label = QLabel("Actor settings", self._mmd_editor_host)
        mmd_editor_label.setObjectName("Live2DMappingTitle")
        self._mmd_editor_btn = QPushButton("MMD Editor", self._mmd_editor_host)
        self._mmd_editor_btn.setObjectName("FxSummaryButton")
        self._mmd_editor_btn.setIcon(app_icon("sliders", size=13, color="#D7DAE7"))
        self._mmd_editor_btn.setIconSize(icon_size(12))
        self._mmd_editor_btn.setToolTip("Open MMD motion, physics, light, and material settings")
        self._mmd_editor_btn.clicked.connect(self.open_mmd_editor_requested.emit)
        mmd_editor_layout.addWidget(mmd_editor_label, 1)
        mmd_editor_layout.addWidget(self._mmd_editor_btn)
        rows.addWidget(self._mmd_editor_host)
        self._mmd_editor_host.hide()
        self._ar_pbr_evidence_card = ArPbrEvidenceCard(self._rows_host)
        rows.addWidget(self._ar_pbr_evidence_card)
        self._ar_pbr_evidence_card.hide()
        # No internal stretch — rows hug the top so the NodeGraph
        # area below gets the lion's share of vertical space.
        # ``stretch=0`` on the root keeps the rows compact.
        self._tab_layouts["clip"].insertWidget(0, self._rows_host)

        self._audio_evidence_card = _AudioEvidenceCard(self._tab_pages["audio"])
        self._audio_evidence_card.hide()
        self._tab_layouts["audio"].insertWidget(1, self._audio_evidence_card)
        self._sound_editor_panel = SoundEditorPanel(self._tab_pages["audio"])
        self._sound_editor_panel.changed.connect(self._on_sound_editor_changed)
        self._sound_editor_panel.advanced_lab_requested.connect(
            self.advanced_sound_lab_requested.emit
        )
        self._sound_editor_panel.hide()
        self._tab_layouts["audio"].insertWidget(2, self._sound_editor_panel, stretch=1)

        self._typography_evidence_card = _TypographyEvidenceCard(self._tab_pages["fx"])
        self._typography_evidence_card.hide()
        self._tab_layouts["fx"].insertWidget(1, self._typography_evidence_card)

        self._fx_summary_host = QWidget(self._tab_pages["fx"])
        self._fx_summary_host.setObjectName("FxSummary")
        self._fx_summary_host.setMinimumHeight(74)
        self._fx_summary_host.setMaximumHeight(108)
        fx_sum = QVBoxLayout(self._fx_summary_host)
        fx_sum.setContentsMargins(7, 4, 7, 5)
        fx_sum.setSpacing(2)
        self._fx_summary_title = QLabel("Applied stack", self._fx_summary_host)
        self._fx_summary_title.setObjectName("FxSummaryTitle")
        fx_sum.addWidget(self._fx_summary_title)
        self._fx_summary_body = QLabel(
            "Select a clip to inspect effect, title, and transition presets.",
            self._fx_summary_host,
        )
        self._fx_summary_body.setObjectName("FxSummaryBody")
        self._fx_summary_body.setWordWrap(False)
        fx_sum.addWidget(self._fx_summary_body)
        self._fx_stack_rail = _FxStackRail(self._fx_summary_host)
        fx_sum.addWidget(self._fx_stack_rail)
        self._vfx_graph_strip_host = QWidget(self._fx_summary_host)
        self._vfx_graph_strip_host.setObjectName("VfxGraphStrip")
        self._vfx_graph_strip = QHBoxLayout(self._vfx_graph_strip_host)
        self._vfx_graph_strip.setContentsMargins(0, 3, 0, 1)
        self._vfx_graph_strip.setSpacing(4)
        self._vfx_graph_strip_host.hide()
        fx_sum.addWidget(self._vfx_graph_strip_host)
        fx_actions = QHBoxLayout()
        fx_actions.setContentsMargins(0, 0, 0, 0)
        fx_actions.setSpacing(3)

        def _setup_fx_action_button(button: QPushButton, icon_name: str, tooltip: str) -> None:
            button.setObjectName("FxSummaryButton")
            button.setText("")
            button.setIcon(app_icon(icon_name, size=13, color="#D7DAE7"))
            button.setIconSize(icon_size(12))
            button.setFixedSize(24, 21)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)

        self._fx_edit_clip_btn = QPushButton("Edit Clip FX", self._fx_summary_host)
        _setup_fx_action_button(self._fx_edit_clip_btn, "sliders", "Edit clip FX")
        self._fx_edit_clip_btn.clicked.connect(self.open_clip_fx_requested.emit)
        self._fx_toggle_clip_btn = QPushButton("Disable Clip FX", self._fx_summary_host)
        _setup_fx_action_button(self._fx_toggle_clip_btn, "effects", "Disable clip FX")
        self._fx_toggle_clip_btn.clicked.connect(self.toggle_clip_fx_requested.emit)
        self._fx_clear_clip_btn = QPushButton("Clear Clip FX", self._fx_summary_host)
        _setup_fx_action_button(self._fx_clear_clip_btn, "clear", "Clear clip FX")
        self._fx_clear_clip_btn.clicked.connect(self.clear_clip_fx_requested.emit)
        self._fx_clear_transition_btn = QPushButton("Clear Transition", self._fx_summary_host)
        _setup_fx_action_button(self._fx_clear_transition_btn, "transition", "Clear transition")
        self._fx_clear_transition_btn.clicked.connect(self.clear_clip_transition_requested.emit)
        self._fx_vfx_graph_btn = QPushButton("Inspect VFX", self._fx_summary_host)
        _setup_fx_action_button(self._fx_vfx_graph_btn, "list", "Open VFX graph QA and node details")
        self._fx_vfx_graph_btn.clicked.connect(self._show_vfx_graph_details)
        self._fx_vfx_graph_btn.hide()
        fx_actions.addWidget(self._fx_edit_clip_btn)
        fx_actions.addWidget(self._fx_toggle_clip_btn)
        fx_actions.addWidget(self._fx_clear_clip_btn)
        fx_actions.addWidget(self._fx_clear_transition_btn)
        fx_actions.addWidget(self._fx_vfx_graph_btn)
        fx_actions.addStretch(1)
        fx_sum.addLayout(fx_actions)
        self._tab_layouts["fx"].insertWidget(2, self._fx_summary_host)
        self._fx_summary_host.hide()

        # ---- NodeGraph section (Phase 2A) ----
        # The DaVinci-style node graph editor lives here as the
        # workbench's *primary* content. Properties rows above act as
        # the "metadata header"; the node graph gets the bulk of the
        # vertical real estate (``stretch=1``). Section header + pop-out
        # popout button live INSIDE the NodeGraphWidget so the panel
        # stays self-contained when reparented to the popout window.
        from app.workbench.node_graph.widget import NodeGraphWidget
        self._node_graph_widget = NodeGraphWidget(self._tab_pages["fx"])
        self._node_graph_widget.popout_requested.connect(
            self._toggle_node_graph_popout,
        )
        self._node_graph_widget.node_selection_changed.connect(
            self._on_node_graph_selection_changed,
        )
        # Hidden until the user selects a video track — audio clips
        # don't carry a node graph yet (Phase 2D+).
        self._node_graph_widget.hide()
        fx_layout = self._tab_layouts["fx"]
        fx_layout.insertWidget(1, self._node_graph_widget, stretch=1)
        for idx in range(fx_layout.count() - 1, -1, -1):
            item = fx_layout.itemAt(idx)
            if item is not None and item.spacerItem() is not None:
                fx_layout.takeAt(idx)
                break
        # Popout state. Same pattern as Media Pool / Effects Library
        # popouts — ``_node_graph_root_layout`` is the layout we
        # reparent the widget out of and back into.
        self._node_graph_root_layout = fx_layout
        self._node_graph_popout = None
        self._node_graph_placeholder = None

    # ---- public API ----

    def set_blur_node(self, blur_node, on_change=None) -> None:
        """Show the blur controls section for the given BlurNodeItem.
        Called by the editor when a blur node is selected.
        ``on_change`` is called after any param change (triggers
        _rebuild_active_chain + preview refresh)."""
        self._set_inspector_tab("mask" if blur_node is not None else "fx")
        if not hasattr(self, "_blur_section"):
            self._build_blur_section()
        if blur_node is None:
            self._blur_section.hide()
            if hasattr(self, "_mask_empty_label"):
                self._mask_empty_label.show()
            return
        self._blur_node_ref = blur_node
        self._blur_on_change = on_change
        self._sync_blur_controls()
        self._blur_section.show()
        if hasattr(self, "_mask_empty_label"):
            self._mask_empty_label.hide()

    def _build_blur_section(self) -> None:
        """Lazily build the blur parameter controls and insert them
        just below the NodeGraph widget in the workbench layout."""
        from PySide6.QtWidgets import (
            QCheckBox, QComboBox, QHBoxLayout, QLabel,
            QSlider, QVBoxLayout, QWidget,
        )
        from PySide6.QtCore import Qt
        self._blur_section = QWidget(self._tab_pages["mask"])
        self._blur_section.setObjectName("MaskControls")
        self._blur_section.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._blur_section.setMaximumWidth(480)
        self._blur_section.setStyleSheet(
            "QWidget#MaskControls {"
            "background:rgba(255,255,255,6);"
            "border:1px solid rgba(178,186,202,25);"
            "border-radius:7px;"
            "}"
            "QLabel#MaskSectionTitle { color:#F2F0EA; font-size:11px; font-weight:700; border:none; background:transparent; }"
            "QLabel#MaskFieldLabel { color:#9A9FA8; font-size:9px; font-weight:620; border:none; background:transparent; }"
            "QComboBox#MaskCombo { background:rgba(255,255,255,7); color:#E8EAEE; border:1px solid rgba(178,186,202,30); border-radius:6px; padding:4px 8px; font-size:10px; }"
            "QComboBox#MaskCombo:hover { background:rgba(255,255,255,12); border-color:rgba(210,218,235,62); }"
            "QCheckBox#MaskCheck { color:#C8CCD4; font-size:10px; spacing:6px; border:none; background:transparent; }"
            "QCheckBox#MaskCheck::indicator { width:13px; height:13px; border-radius:6px; border:1px solid #5B626D; background:#1B1E22; }"
            "QCheckBox#MaskCheck::indicator:checked { background:#A1A9B3; border-color:#D5D9DF; }"
            "QPushButton#MaskActionButton { background:rgba(255,255,255,8); color:#DCE1EA; border:1px solid rgba(178,186,202,32); border-radius:6px; padding:5px 8px; font-size:10px; font-weight:620; }"
            "QPushButton#MaskActionButton:hover { background:rgba(255,255,255,14); border-color:rgba(210,218,235,68); color:#FFFFFF; }"
        )
        lay = QVBoxLayout(self._blur_section)
        lay.setContentsMargins(8, 7, 8, 8)
        lay.setSpacing(6)
        title = QLabel("🔵 Blur — Out-of-Focus", self._blur_section)
        title.setText("Blur mask")
        title.setObjectName("MaskSectionTitle")
        lay.addWidget(title)

        # Shape selector
        shape_row = QHBoxLayout()
        shape_row.setContentsMargins(0, 0, 0, 0)
        shape_row.setSpacing(8)
        shape_label = QLabel("Shape", self._blur_section)
        shape_label.setObjectName("MaskFieldLabel")
        shape_label.setFixedWidth(72)
        shape_row.addWidget(shape_label)
        self._blur_shape_cb = QComboBox(self._blur_section)
        self._blur_shape_cb.addItems(["Circle (Bokeh)", "Hexagon (Aperture)", "Gaussian (Soft)"])
        self._blur_shape_cb.setObjectName("MaskCombo")
        shape_row.addWidget(self._blur_shape_cb, stretch=1)
        lay.addLayout(shape_row)

        # Radius slider
        r_row = QHBoxLayout()
        r_row.setContentsMargins(0, 0, 0, 0)
        r_row.setSpacing(8)
        radius_label = QLabel("Radius", self._blur_section)
        radius_label.setObjectName("MaskFieldLabel")
        radius_label.setFixedWidth(72)
        r_row.addWidget(radius_label)
        self._blur_radius_sld = StudioSlider("accent", self._blur_section)
        self._blur_radius_sld.setRange(1, 50)
        self._blur_radius_sld.setValue(15)
        r_row.addWidget(self._blur_radius_sld, stretch=1)
        self._blur_radius_lbl = QLabel("15", self._blur_section)
        self._blur_radius_lbl.setFixedWidth(28)
        self._blur_radius_lbl.setStyleSheet("color:#EEF0F3; font-size:10px; font-weight:600; border:none; background:transparent;")
        r_row.addWidget(self._blur_radius_lbl)
        lay.addLayout(r_row)

        # Strength slider
        s_row = QHBoxLayout()
        s_row.setContentsMargins(0, 0, 0, 0)
        s_row.setSpacing(8)
        strength_label = QLabel("Strength", self._blur_section)
        strength_label.setObjectName("MaskFieldLabel")
        strength_label.setFixedWidth(72)
        s_row.addWidget(strength_label)
        self._blur_strength_sld = StudioSlider("accent", self._blur_section)
        self._blur_strength_sld.setRange(0, 100)
        self._blur_strength_sld.setValue(100)
        s_row.addWidget(self._blur_strength_sld, stretch=1)
        self._blur_strength_lbl = QLabel("100%", self._blur_section)
        self._blur_strength_lbl.setFixedWidth(36)
        self._blur_strength_lbl.setStyleSheet("color:#EEF0F3; font-size:10px; font-weight:600; border:none; background:transparent;")
        s_row.addWidget(self._blur_strength_lbl)
        lay.addLayout(s_row)

        # Mask inversion toggle
        self._blur_invert_chk = QCheckBox("Invert mask (background blur)", self._blur_section)
        self._blur_invert_chk.setObjectName("MaskCheck")
        self._blur_invert_chk.setChecked(True)
        lay.addWidget(self._blur_invert_chk)

        # Main area-selection button (opens large canvas)
        from PySide6.QtWidgets import QPushButton
        select_btn = QPushButton("영역 선택... (큰 화면)", self._blur_section)
        select_btn.setText("Select area...")
        select_btn.setObjectName("MaskActionButton")
        select_btn.setIcon(app_icon("target", size=16, color="#D7DAE7"))
        select_btn.setIconSize(icon_size(14))
        select_btn.setFixedHeight(28)
        select_btn.setMinimumWidth(150)
        select_btn.setMaximumWidth(230)
        select_btn.setToolTip("큰 캔버스에서 폴리곤/사각형/클릭으로 선택 → 추적")
        select_btn.setToolTip("Open the mask canvas and draw or click the target region")
        select_btn.clicked.connect(self._on_blur_select_area)
        lay.addWidget(select_btn, 0, Qt.AlignmentFlag.AlignLeft)

        # Track checkbox
        self._blur_track_chk = QCheckBox("추적 (Track object through clip)", self._blur_section)
        self._blur_track_chk.setChecked(True)
        self._blur_track_chk.setText("Track object through clip")
        self._blur_track_chk.setObjectName("MaskCheck")
        lay.addWidget(self._blur_track_chk)

        # Person-Follow shortcut
        person_btn = QPushButton("인물 자동 선택 + 배경 블러", self._blur_section)
        person_btn.setText("Person mask + background blur")
        person_btn.setObjectName("MaskActionButton")
        person_btn.setIcon(app_icon("person", size=16, color="#D7DAE7"))
        person_btn.setIconSize(icon_size(14))
        person_btn.setFixedHeight(28)
        person_btn.setMinimumWidth(210)
        person_btn.setMaximumWidth(280)
        person_btn.clicked.connect(self._on_blur_person_follow)
        lay.addWidget(person_btn, 0, Qt.AlignmentFlag.AlignLeft)

        # Wire signals
        self._blur_shape_cb.currentIndexChanged.connect(self._on_blur_changed)
        self._blur_radius_sld.valueChanged.connect(self._on_blur_changed)
        self._blur_strength_sld.valueChanged.connect(self._on_blur_changed)
        self._blur_invert_chk.toggled.connect(self._on_blur_changed)

        self._tab_layouts["mask"].insertWidget(1, self._blur_section)
        self._blur_section.hide()
        self._blur_node_ref = None
        self._blur_on_change = None

    def _sync_blur_controls(self) -> None:
        node = getattr(self, "_blur_node_ref", None)
        if node is None:
            return
        from app.blur_params import BLUR_SHAPE_CIRCLE, BLUR_SHAPE_HEXAGON
        bp = node.blur_params
        shape_idx = {BLUR_SHAPE_CIRCLE: 0, BLUR_SHAPE_HEXAGON: 1}.get(bp.shape, 2)
        self._blur_shape_cb.blockSignals(True)
        self._blur_shape_cb.setCurrentIndex(shape_idx)
        self._blur_shape_cb.blockSignals(False)
        self._blur_radius_sld.blockSignals(True)
        self._blur_radius_sld.setValue(int(bp.radius))
        self._blur_radius_sld.blockSignals(False)
        self._blur_radius_lbl.setText(str(int(bp.radius)))
        self._blur_strength_sld.blockSignals(True)
        self._blur_strength_sld.setValue(int(bp.strength * 100))
        self._blur_strength_sld.blockSignals(False)
        self._blur_strength_lbl.setText(f"{int(bp.strength*100)}%")
        self._blur_invert_chk.blockSignals(True)
        self._blur_invert_chk.setChecked(bool(node.blur_invert_mask))
        self._blur_invert_chk.blockSignals(False)

    def _on_blur_changed(self, *_args) -> None:
        node = getattr(self, "_blur_node_ref", None)
        if node is None:
            return
        from app.blur_params import (
            BLUR_SHAPE_CIRCLE, BLUR_SHAPE_HEXAGON, BLUR_SHAPE_GAUSSIAN,
        )
        shapes = [BLUR_SHAPE_CIRCLE, BLUR_SHAPE_HEXAGON, BLUR_SHAPE_GAUSSIAN]
        bp = node.blur_params
        bp.shape = shapes[self._blur_shape_cb.currentIndex()]
        bp.radius = int(self._blur_radius_sld.value())
        self._blur_radius_lbl.setText(str(bp.radius))
        bp.strength = self._blur_strength_sld.value() / 100.0
        self._blur_strength_lbl.setText(f"{int(bp.strength*100)}%")
        node.blur_invert_mask = bool(self._blur_invert_chk.isChecked())
        node.update()
        if self._blur_on_change:
            try:
                self._blur_on_change()
            except Exception:
                pass

    # ── Effect node panel ─────────────────────────────────────────────────────

    def set_effect_node(self, effect_node, on_change=None) -> None:
        """Show inline controls for the selected EffectNodeItem.
        Called by the editor when an effect node is selected.
        Pass effect_node=None to hide."""
        self._set_inspector_tab("fx")
        if not hasattr(self, "_effect_section"):
            self._effect_section = QWidget(self._tab_pages["fx"])
            self._effect_section.setObjectName("EffectNodeControls")
            self._effect_section.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self._effect_section.hide()
            self._tab_layouts["fx"].insertWidget(2, self._effect_section)
        if effect_node is None:
            self._effect_section.hide()
            self._effect_node_ref = None
            if hasattr(self, "_fx_empty_label") and not self._node_graph_widget.isVisible():
                self._fx_empty_label.show()
            return
        self._effect_node_ref = effect_node
        self._effect_on_change = on_change
        self._rebuild_effect_section()
        self._effect_section.show()
        if hasattr(self, "_fx_empty_label"):
            self._fx_empty_label.hide()

    def _rebuild_effect_section(self) -> None:
        from PySide6.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QLabel, QSlider,
            QCheckBox, QComboBox, QLineEdit, QPushButton,
            QFileDialog, QWidget,
        )
        from PySide6.QtCore import Qt

        node = getattr(self, "_effect_node_ref", None)
        if node is None:
            return
        ep = getattr(node, "effect_params", None)
        kind = getattr(node, "NODE_KIND", "")
        if ep is None:
            return

        from app.effect_node_params import _KIND_META
        meta = _KIND_META.get(kind, (node.label, "#607D8B", None))
        hdr_color = meta[1]

        # Rebuild from scratch
        old_lay = self._effect_section.layout()
        if old_lay:
            while old_lay.count():
                item = old_lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            old_lay.deleteLater()

        lay = QVBoxLayout(self._effect_section)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(4)
        self._effect_section.setStyleSheet("")

        # Header
        title = QLabel(f"{node.label} parameters", self._effect_section)
        title.setObjectName("EffectNodeTitle")
        title.setToolTip(f"Node kind: {kind or 'effect'}")
        lay.addWidget(title)

        emit = self._emit_effect_change
        display_labels = {
            "levels": [
                "Input Black", "Input White", "Gamma",
                "Output Black", "Output White",
            ],
            "curves": ["Midtone"],
            "glow": [
                "Threshold", "Radius", "Intensity",
                "Red Tint", "Green Tint", "Blue Tint",
            ],
            "filmgrain": ["Amount", "Grain Size"],
            "vignette": ["Amount", "Size", "Feather", "Roundness"],
            "lut": ["Blend"],
            "whitebalance": ["Temperature", "Tint"],
            "unsharpmask": ["Amount", "Radius", "Threshold"],
            "pixelate": ["Block Size"],
            "channelmixer": [
                "Input R", "Input G", "Input B",
                "Input R", "Input G", "Input B",
                "Input R", "Input G", "Input B",
            ],
            "sdr_hdr_upmap": [
                "Peak Nits", "Exposure", "Highlight", "Saturation", "Max Frames",
            ],
        }.get(kind, [])
        display_checks = {
            "filmgrain": ["Monochrome"],
        }.get(kind, [])
        row_index = 0
        check_index = 0

        def _srow(label, lo, hi, val, setter, scale=1.0, fmt="{:.0f}"):
            from PySide6.QtWidgets import QHBoxLayout as _HL
            nonlocal row_index
            if row_index < len(display_labels):
                label = display_labels[row_index]
            row_index += 1
            row = _HL()
            lbl = QLabel(label, self._effect_section)
            lbl.setObjectName("EffectFieldLabel")
            lbl.setFixedWidth(90)
            sl = StudioSlider("accent", self._effect_section)
            sl.setRange(lo, hi); sl.setValue(val)
            val_lbl = QLabel(fmt.format(val * scale), self._effect_section)
            val_lbl.setObjectName("EffectFieldValue")
            val_lbl.setFixedWidth(40)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            def _upd(v, vl=val_lbl, s=scale, f=fmt, fn=setter):
                vl.setText(f.format(v * s))
                fn(v)
                emit()
            sl.valueChanged.connect(_upd)
            row.addWidget(lbl); row.addWidget(sl, 1); row.addWidget(val_lbl)
            w = QWidget(self._effect_section); w.setStyleSheet("background:transparent;")
            w.setLayout(row)
            lay.addWidget(w)
            return sl

        def _chk(label, checked, setter):
            nonlocal check_index
            if check_index < len(display_checks):
                label = display_checks[check_index]
            check_index += 1
            cb = QCheckBox(label, self._effect_section)
            cb.setObjectName("EffectCheck")
            cb.setChecked(checked)
            cb.toggled.connect(lambda v, fn=setter: (fn(v), emit()))
            lay.addWidget(cb)

        if kind == "levels":
            _srow("블랙 포인트", 0, 254, int(ep.in_black*255), lambda v: setattr(ep,"in_black",v/255))
            _srow("화이트 포인트", 1, 255, int(ep.in_white*255), lambda v: setattr(ep,"in_white",v/255))
            _srow("감마", 10, 300, int(ep.gamma*100), lambda v: setattr(ep,"gamma",v/100), 0.01, "{:.2f}")
            _srow("아웃 블랙", 0, 254, int(ep.out_black*255), lambda v: setattr(ep,"out_black",v/255))
            _srow("아웃 화이트", 1, 255, int(ep.out_white*255), lambda v: setattr(ep,"out_white",v/255))

        elif kind == "curves":
            _srow("밝기 (중간)", 0, 100, int(getattr(ep,"master",[[0,0],[1,1]])[1][1]*100 if len(getattr(ep,"master",[[0,0],[0,0]]))>1 else 50),
                  lambda v: setattr(ep, "master", [[0,0],[0.5,v/100],[1,1]]),
                  fmt="{:.0f}%")

        elif kind == "glow":
            _srow("임계값", 10, 100, int(ep.threshold*100), lambda v: setattr(ep,"threshold",v/100), fmt="{:.0f}%")
            _srow("반경", 2, 80, ep.radius, lambda v: setattr(ep,"radius",int(v)), fmt="{:.0f}px")
            _srow("강도", 0, 200, int(ep.intensity*100), lambda v: setattr(ep,"intensity",v/100), fmt="{:.0f}%")
            _srow("R 틴트", 50, 150, int(ep.tint_r*100), lambda v: setattr(ep,"tint_r",v/100), fmt="{:.0f}%")
            _srow("G 틴트", 50, 150, int(ep.tint_g*100), lambda v: setattr(ep,"tint_g",v/100), fmt="{:.0f}%")
            _srow("B 틴트", 50, 150, int(ep.tint_b*100), lambda v: setattr(ep,"tint_b",v/100), fmt="{:.0f}%")

        elif kind == "filmgrain":
            _srow("강도", 0, 300, int(ep.amount*1000), lambda v: setattr(ep,"amount",v/1000), 0.1, "{:.1f}%")
            _srow("입자 크기", 5, 50, int(ep.size*10), lambda v: setattr(ep,"size",v/10), 0.1, "{:.1f}×")
            _chk("모노크롬", ep.monochrome, lambda v: setattr(ep,"monochrome",bool(v)))

        elif kind == "vignette":
            _srow("강도", 0, 100, int(ep.amount*100), lambda v: setattr(ep,"amount",v/100), fmt="{:.0f}%")
            _srow("크기", 10, 100, int(ep.size*100), lambda v: setattr(ep,"size",v/100), fmt="{:.0f}%")
            _srow("부드러움", 0, 100, int(ep.feather*100), lambda v: setattr(ep,"feather",v/100), fmt="{:.0f}%")
            _srow("원형도", 0, 100, int(ep.round*100), lambda v: setattr(ep,"round",v/100), fmt="{:.0f}%")

        elif kind == "lut":
            from PySide6.QtWidgets import QHBoxLayout as _HL
            path_row = _HL()
            path_edit = QLineEdit(ep.path or "", self._effect_section)
            path_edit.setPlaceholderText("파일 경로 (.cube)…")
            path_edit.setReadOnly(True)
            path_edit.setPlaceholderText(".cube / .3dl")
            path_edit.setObjectName("EffectPath")
            btn = QPushButton("", self._effect_section)
            btn.setObjectName("EffectIconButton")
            btn.setFixedSize(28, 22)
            btn.setIcon(app_icon("project", size=15, color="#D7DAE7"))
            btn.setIconSize(icon_size(15))
            def _browse():
                p, _ = QFileDialog.getOpenFileName(self, "Choose LUT", "", "LUT Files (*.cube *.3dl);;All (*.*)")
                if p:
                    ep.path = p; path_edit.setText(p); emit()
            btn.clicked.connect(_browse)
            path_row.addWidget(path_edit, 1); path_row.addWidget(btn)
            pw = QWidget(self._effect_section); pw.setStyleSheet("background:transparent;"); pw.setLayout(path_row)
            lay.addWidget(pw)
            _srow("블렌드", 0, 100, int(ep.strength*100), lambda v: setattr(ep,"strength",v/100), fmt="{:.0f}%")

        elif kind == "whitebalance":
            _srow("온도 (K)", 2000, 12000, ep.temperature, lambda v: setattr(ep,"temperature",int(v)), fmt="{:.0f}K")
            _srow("틴트", -100, 100, ep.tint, lambda v: setattr(ep,"tint",int(v)), fmt="{:+.0f}")

        elif kind == "unsharpmask":
            _srow("강도", 0, 300, int(ep.amount*100), lambda v: setattr(ep,"amount",v/100), fmt="{:.0f}%")
            _srow("반경", 1, 30, ep.radius, lambda v: setattr(ep,"radius",int(v)), fmt="{:.0f}px")
            _srow("임계값", 0, 50, ep.threshold, lambda v: setattr(ep,"threshold",int(v)), fmt="{:.0f}")

        elif kind == "pixelate":
            _srow("블록 크기", 2, 200, ep.block_size, lambda v: setattr(ep,"block_size",int(v)), fmt="{:.0f}px")

        elif kind == "channelmixer":
            for out_ch, out_label in [("r","출력 R"),("g","출력 G"),("b","출력 B")]:
                sep = QLabel(f"  {out_label}", self._effect_section)
                sep.setText({"r": "Output R", "g": "Output G", "b": "Output B"}.get(out_ch, out_label))
                sep.setObjectName("EffectFieldLabel")
                lay.addWidget(sep)
                for in_ch, in_label in [("r","← R"),("g","← G"),("b","← B")]:
                    k = f"{out_ch}{in_ch}"
                    cur = int(getattr(ep, k, 1.0 if out_ch==in_ch else 0.0) * 100)
                    def _mk(key):
                        def _s(v): setattr(ep, key, v/100.0)
                        return _s
                    _srow(f"  {in_label}", -100, 200, cur, _mk(k), fmt="{:.0f}%")

        elif kind == "sdr_hdr_upmap":
            note = QLabel("Job node: creates HDR-capable float EXR frames. Preview stays realtime.", self._effect_section)
            note.setWordWrap(True)
            note.setObjectName("EffectNote")
            lay.addWidget(note)
            _srow("Peak nits", 100, 4000, int(ep.peak_nits), lambda v: setattr(ep, "peak_nits", int(v)), fmt="{:.0f}")
            _srow("Exposure", -300, 300, int(ep.exposure_stops * 100), lambda v: setattr(ep, "exposure_stops", v / 100.0), 0.01, "{:+.2f}")
            _srow("Highlight", 25, 800, int(ep.highlight_boost * 100), lambda v: setattr(ep, "highlight_boost", v / 100.0), 0.01, "{:.2f}x")
            _srow("Saturation", 0, 300, int(ep.saturation_boost * 100), lambda v: setattr(ep, "saturation_boost", v / 100.0), 0.01, "{:.2f}x")
            _srow("Max frames", 0, 600, int(ep.max_frames), lambda v: setattr(ep, "max_frames", int(v)), fmt="{:.0f}")
            run_btn = QPushButton("Create EXR Frames...", self._effect_section)
            run_btn.setObjectName("EffectActionButton")
            run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            run_btn.setFixedHeight(26)
            run_btn.clicked.connect(lambda checked=False, params=ep: self._run_sdr_hdr_upmap_node(params))
            lay.addWidget(run_btn)

    def _run_sdr_hdr_upmap_node(self, params) -> None:
        target = self._target or ()
        if not target or target[0] != "video":
            QMessageBox.information(self, "SDR -> HDR EXR", "Select a video track first.")
            return
        track = target[1]
        source = getattr(track, "source_path", None)
        if not source:
            QMessageBox.information(self, "SDR -> HDR EXR", "This track has no source video path.")
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Choose EXR output folder")
        if not out_dir:
            return
        try:
            from app.sdr_hdr_upmap import SDRHDRUpmapProfile, sdr_to_hdr_upmap_report

            profile = SDRHDRUpmapProfile.from_dict(params.to_profile_dict())
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                report = sdr_to_hdr_upmap_report(source, out_dir, profile, run=True)
            finally:
                QApplication.restoreOverrideCursor()
        except Exception as exc:
            QMessageBox.warning(self, "SDR -> HDR EXR", f"EXR conversion failed:\n{exc}")
            return
        generated = int(report.get("generated_frames", 0) or 0)
        if report.get("ok"):
            QMessageBox.information(
                self,
                "SDR -> HDR EXR",
                f"EXR conversion complete.\nFrames: {generated}\nFolder: {out_dir}",
            )
        else:
            tail = str(report.get("stderr_tail") or report.get("error") or "Unknown error")
            QMessageBox.warning(
                self,
                "SDR -> HDR EXR",
                f"EXR conversion failed.\nFrames: {generated}\n\n{tail[-1200:]}",
            )

    def _emit_effect_change(self) -> None:
        node = getattr(self, "_effect_node_ref", None)
        if node is not None:
            node.update()
        fn = getattr(self, "_effect_on_change", None)
        if fn:
            try:
                fn()
            except Exception:
                pass

    def _on_blur_select_area(self) -> None:
        """Open MaskEditorWindow (large canvas) so the user can
        draw a polygon, rect or click-to-select the subject.
        On OK, attach the resulting mask + optional tracker to the
        active blur node.  Invert setting determines whether the
        SELECTED area stays sharp (invert=True) or gets blurred."""
        node = getattr(self, "_blur_node_ref", None)
        if node is None:
            return
        # Get the current preview frame from the editor.
        editor = self.window()
        rgb = None
        if editor is not None:
            try:
                rgb = editor._current_preview_rgb()
            except Exception:
                pass
        frame_idx = 0
        if editor is not None:
            try:
                frame_idx = int(editor._current_preview_frame_idx())
            except Exception:
                frame_idx = 0
        if rgb is None:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "영역 선택",
                "프리뷰 프레임이 없습니다.\n영상을 드롭하고 플레이헤드를 영상 위에 놓아주세요.",
            )
            return
        from app.mask_editor_window import MaskEditorWindow
        dlg = MaskEditorWindow.open_for_node(
            rgb, node,
            on_commit=self._blur_on_change,
            parent=self,
            frame_idx=frame_idx,
        )
        if getattr(self, "_blur_track_chk", None) is not None:
            dlg._track_chk.setChecked(bool(self._blur_track_chk.isChecked()))
        # Override the commit logic to use BitmapMask + optional
        # MaskTracker instead of attaching to node.color_grade.
        def _on_accept():
            mask_arr = dlg._canvas.current_mask()
            if mask_arr is None and len(dlg._canvas.current_polygon_points()) >= 3:
                mask_arr = dlg._canvas._eval_polygon_mask()
            if mask_arr is None:
                return
            from app.node_mask import BitmapMask, PowerWindow
            tool = dlg._canvas._tool
            softness = dlg._softness_sld.value() / 1000.0
            invert = dlg._invert_chk.isChecked()
            track_final = bool(dlg._track_chk.isChecked())
            if tool == "polygon":
                pts = dlg._canvas.current_polygon_points()
                m = PowerWindow(points=pts, softness_norm=softness,
                                invert=invert)
                if track_final:
                    # Wrap in a tracker: use BitmapMask with track_object
                    bm = BitmapMask(softness_norm=softness, invert=invert,
                                    track_object=True, init_frame=frame_idx)
                    bm.set_from_array(mask_arr)
                    node.masks = [bm]
                else:
                    node.masks = [m]
            else:
                bm = BitmapMask(softness_norm=softness, invert=invert,
                                track_object=track_final, init_frame=frame_idx)
                bm.set_from_array(mask_arr)
                node.masks = [bm]
            # Invert mask = selected area stays sharp, rest blurs.
            node.blur_invert_mask = invert
            self._blur_invert_chk.setChecked(invert)
            node.update()
            if self._blur_on_change:
                try:
                    self._blur_on_change()
                except Exception:
                    pass

        dlg.accepted.connect(_on_accept)
        dlg.exec()

    def _on_blur_person_follow(self) -> None:
        """One-click: add MagicMask(person) + MaskTracker to the
        active blur node so it automatically tracks the person through
        the clip and blurs the background."""
        node = getattr(self, "_blur_node_ref", None)
        if node is None:
            return
        from app.node_mask import MagicMask, MaskTracker
        node.masks = [MagicMask(feature="person")]
        node.blur_invert_mask = True  # background blur
        self._blur_invert_chk.setChecked(True)
        node.update()
        if self._blur_on_change:
            try:
                self._blur_on_change()
            except Exception:
                pass

    def set_node_thumbnail(self, pix) -> None:
        """Forward the editor's current preview frame to the
        NodeGraph so every node renders a DaVinci-style live
        thumbnail. Throttling lives in the editor — this call is
        just a scale + setattr per node."""
        if hasattr(self, "_node_graph_widget"):
            self._node_graph_widget.set_source_pixmap(pix)

    def selected_node(self):
        """Return the currently-selected NodeItem (or None) so the
        editor can route the Color panel to that node's grade."""
        if not hasattr(self, "_node_graph_widget"):
            return None
        items = self._node_graph_widget.scene.selectedItems()
        from app.workbench.node_graph.items.node_item import NodeItem
        for it in items:
            if isinstance(it, NodeItem):
                return it
        return None

    def primary_node(self):
        """Return the first Serial node (the default Node 1) so the
        editor has a sensible grade target before the user clicks
        anything. None when the graph is empty."""
        if not hasattr(self, "_node_graph_widget"):
            return None
        nodes = self._node_graph_widget.scene._serial_nodes
        from app.workbench.node_graph.items.node_item import NodeItem
        for n in nodes:
            if isinstance(n, NodeItem):
                return n
        return None

    def expose_node_graph_widget(self):
        """Allow the editor to wire signals (selected_node_changed)
        without importing NodeGraphWidget. Returns the widget or None."""
        return getattr(self, "_node_graph_widget", None)

    def _set_inspector_tab(self, tab: str) -> None:
        self._inspector_tab = tab or "clip"
        btn = self._inspector_tab_buttons.get(self._inspector_tab)
        if btn is not None:
            btn.setChecked(True)
        page = self._tab_pages.get(self._inspector_tab)
        if page is not None:
            self._tab_stack.setCurrentWidget(page)
        self._sync_inspector_chrome()

    def _sync_inspector_chrome(self) -> None:
        """Keep the FX graph visually close to the reference layout.

        The clip/audio/meta tabs need the title and palette context.
        The FX tab is different: the node graph is the content, so the
        workbench chrome folds away and leaves vertical room for nodes.
        """
        is_fx = self._inspector_tab == "fx"
        target_kind = self._target[0] if self._target else ""
        is_audio_editor = target_kind in {"audio", "audio_source"}
        if hasattr(self, "_title_row"):
            self._title_row.setVisible(not is_fx)
        if hasattr(self, "_title"):
            self._title.setVisible(not is_fx)
        if hasattr(self, "_subtitle"):
            self._subtitle.setVisible((not is_fx) and (not is_audio_editor) and bool(self._subtitle.text()))
        if hasattr(self, "_palette_strip"):
            self._palette_strip.setVisible(not is_fx)
        if not hasattr(self, "_inspector_tab_buttons"):
            return
        if hasattr(self, "_inspector_tabs"):
            self._inspector_tabs.setProperty("fxMode", bool(is_fx))
            self._inspector_tabs.setVisible(not is_fx)
            self._inspector_tabs.setFixedHeight(0 if is_fx else 22)
            self._inspector_tabs.style().unpolish(self._inspector_tabs)
            self._inspector_tabs.style().polish(self._inspector_tabs)
        for button in self._inspector_tab_buttons.values():
            button.setProperty("fxMode", bool(is_fx))
            button.setFixedSize(17 if is_fx else 24, 14 if is_fx else 18)
            button.setIconSize(icon_size(10 if is_fx else 12))
            button.style().unpolish(button)
            button.style().polish(button)

    def _move_rows_to_tab(self, tab: str) -> None:
        target = self._tab_layouts.get(tab)
        if target is None:
            return
        for layout in self._tab_layouts.values():
            idx = layout.indexOf(self._rows_host)
            if idx >= 0:
                layout.takeAt(idx)
                break
        target.insertWidget(0, self._rows_host)

    def _set_tab_empty_visible(self, tab: str, visible: bool, text: str | None = None) -> None:
        label = getattr(self, f"_{tab}_empty_label", None)
        if label is None:
            return
        if text is not None:
            label.setText(text)
        label.setVisible(bool(visible))

    @staticmethod
    def _param_active(value) -> bool:
        if value is None:
            return False
        is_identity = getattr(value, "is_identity", None)
        if callable(is_identity):
            try:
                return not bool(is_identity())
            except Exception:
                return True
        if isinstance(value, dict):
            if bool(value.get("enabled", False)):
                return True
            return any(
                item not in (None, False, 0, 0.0, "")
                for key, item in value.items()
                if str(key) not in {"enabled", "name", "label"}
            )
        return True

    @staticmethod
    def _overlaps(a0: int, a1: int, b0: int, b1: int) -> bool:
        return int(a0) < int(b1) and int(b0) < int(a1)

    @staticmethod
    def _text_keyframe_count(actor: Any) -> int:
        raw_keys = getattr(actor, "keyframes", None)
        if not isinstance(raw_keys, dict):
            animation = getattr(actor, "animation", None)
            custom = getattr(animation, "custom_params", {}) if animation is not None else {}
            raw_keys = custom.get("action_keyframes") if isinstance(custom, dict) else {}
        if not isinstance(raw_keys, dict):
            return 0
        count = 0
        for series in raw_keys.values():
            if isinstance(series, dict):
                series = series.get("keyframes") or series.get("keys") or []
            if isinstance(series, (list, tuple)):
                count += len(series)
        return int(count)

    def _set_vfx_graph_strip(self, track) -> None:
        if not hasattr(self, "_vfx_graph_strip_host"):
            return
        while self._vfx_graph_strip.count():
            item = self._vfx_graph_strip.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        rows = vfx_node_graph_overview_for_track(track)
        if not rows:
            self._vfx_graph_strip_host.hide()
            return
        for idx, row in enumerate(rows):
            if idx:
                arrow = QLabel(">", self._vfx_graph_strip_host)
                arrow.setProperty("VfxGraphArrow", "true")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._vfx_graph_strip.addWidget(arrow)
            node_label = QPushButton(str(row.get("label") or "Node"), self._vfx_graph_strip_host)
            node_label.setProperty("VfxGraphNode", "true")
            node_label.setProperty("VfxGraphNodeState", row.get("state", "info"))
            node_label.setCursor(Qt.CursorShape.PointingHandCursor)
            node_label.setMinimumHeight(28)
            node_label.setToolTip(
                f"{row.get('id', '')} | {row.get('kind', '')}\nClick to inspect VFX graph.".strip(" |")
            )
            node_label.clicked.connect(self._show_vfx_graph_details)
            self._vfx_graph_strip.addWidget(node_label)
        self._vfx_graph_strip.addStretch(1)
        self._vfx_graph_strip_host.show()

    def _show_vfx_graph_details(self) -> None:
        target = self._target or ()
        if not target or target[0] != "video":
            return
        track = target[1]
        text = vfx_node_graph_detail_text_for_track(track)
        dlg = QDialog(self)
        dlg.setWindowTitle("VFX Graph")
        dlg.resize(640, 500)
        root = QVBoxLayout(dlg)
        root.setContentsMargins(12, 12, 12, 12)
        title = QLabel(self.vfx_node_graph_summary_text(track), dlg)
        title.setWordWrap(True)
        title.setStyleSheet("color:#F2F4FF;font-weight:900;font-size:12px;")
        root.addWidget(title)
        detail = QPlainTextEdit(dlg)
        detail.setReadOnly(True)
        detail.setPlainText(text)
        root.addWidget(detail, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dlg)
        copy_btn = QPushButton("Copy", dlg)
        buttons.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(detail.toPlainText()))
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)
        dlg.exec()

    def _set_fx_summary(self, track, selected_clip=None) -> None:
        if not hasattr(self, "_fx_summary_host"):
            return
        if track is None:
            self._fx_summary_host.hide()
            self._set_vfx_graph_strip(None)
            self._fx_vfx_graph_btn.hide()
            return

        lines: list[str] = []
        has_clip_fx = False
        has_disabled_fx = False
        has_transition = False
        title_count = 0
        motion_count = 0
        target_start = 0
        target_end = int(getattr(track, "duration_ms", 0) or 0)
        if selected_clip is not None:
            target_start = int(getattr(selected_clip, "timeline_in_ms", 0) or 0)
            target_end = int(getattr(selected_clip, "timeline_out_ms", target_start) or target_start)
            self._fx_summary_title.setText("SELECTED CLIP STACK")
            if self._param_active(getattr(selected_clip, "video_filters", None)):
                has_clip_fx = True
                lines.append("FX: video filter preset")
            if self._param_active(getattr(selected_clip, "chroma_key", None)):
                has_clip_fx = True
                lines.append("Key: chroma/alpha preset")
            if self._param_active(getattr(selected_clip, "bg_removal", None)):
                has_clip_fx = True
                lines.append("AI: background removal")
            disabled_labels = []
            if self._param_active(getattr(selected_clip, "disabled_video_filters", None)):
                disabled_labels.append("FX")
            if self._param_active(getattr(selected_clip, "disabled_chroma_key", None)):
                disabled_labels.append("Key")
            if self._param_active(getattr(selected_clip, "disabled_bg_removal", None)):
                disabled_labels.append("AI")
            if disabled_labels:
                has_disabled_fx = True
                lines.append(f"Disabled: {', '.join(disabled_labels)} stored")
            ttype = str(getattr(selected_clip, "transition_out_type", "") or "")
            if ttype:
                has_transition = True
                tms = int(getattr(selected_clip, "transition_out_ms", 0) or 0)
                lines.append(f"TR: {ttype.replace('_', ' ').title()} {tms}ms")
        else:
            self._fx_summary_title.setText("TRACK STACK")

        title_names: list[str] = []
        title_keyframes = 0
        for actor in getattr(track, "typography_actors", []) or []:
            if selected_clip is None or self._overlaps(
                target_start,
                target_end,
                int(getattr(actor, "start_ms", 0) or 0),
                int(getattr(actor, "end_ms", 0) or 0),
            ):
                title_count += 1
                title = str(getattr(actor, "text", "") or "Title").strip()
                if title and len(title_names) < 2:
                    title_names.append(title[:24])
                title_keyframes += self._text_keyframe_count(actor)
        if title_count:
            label = ", ".join(title_names) if title_names else f"{title_count} title actor(s)"
            suffix = f" | {title_keyframes} keys" if title_keyframes else ""
            lines.append(f"TXT: {label}{suffix}")

        for actor in getattr(track, "zoom_actors", []) or []:
            if selected_clip is None or self._overlaps(
                target_start,
                target_end,
                int(getattr(actor, "start_ms", 0) or 0),
                int(getattr(actor, "end_ms", 0) or 0),
            ):
                motion_count += 1
        if motion_count:
            lines.append(f"Mot: {motion_count} motion/zoom actor(s)")

        vfx_status = vfx_node_graph_status_for_track(track)
        view_graph = getattr(track, "node_graph_view_data", None)
        view_graph_count = 0
        if isinstance(view_graph, dict):
            view_graph_count = len([row for row in list(view_graph.get("nodes") or []) if isinstance(row, dict)])
        has_vfx_graph = int(vfx_status.get("graph_count", 0) or 0) > 0 or view_graph_count > 0
        if int(vfx_status.get("graph_count", 0) or 0) > 0:
            lines.append(str(vfx_status.get("summary") or "VFX graph: Review"))
        elif view_graph_count > 0:
            lines.append(f"Graph: {view_graph_count} node chain")
        self._set_vfx_graph_strip(track)

        if not lines:
            lines.append("No active preset at the current selection.")

        detail_text = "\n".join(lines)
        self._fx_summary_body.setText("   /   ".join(lines))
        self._fx_summary_body.setToolTip(detail_text)
        if hasattr(self, "_fx_stack_rail"):
            footer_bits: list[str] = []
            if has_clip_fx:
                footer_bits.append("clip fx")
            if has_transition:
                footer_bits.append("transition")
            if title_count:
                footer_bits.append(f"title {title_count}")
            if motion_count:
                footer_bits.append(f"motion {motion_count}")
            self._fx_stack_rail.set_state(
                has_clip_fx=has_clip_fx or has_disabled_fx,
                has_transition=has_transition,
                has_vfx_graph=has_vfx_graph,
                footer=" / ".join(footer_bits[:3]) if footer_bits else "clean stack",
            )
        can_edit = bool(selected_clip is not None)
        self._fx_edit_clip_btn.setEnabled(can_edit)
        self._fx_toggle_clip_btn.setEnabled(bool(selected_clip is not None and (has_clip_fx or has_disabled_fx)))
        toggle_label = "Enable clip FX" if has_disabled_fx and not has_clip_fx else "Disable clip FX"
        self._fx_toggle_clip_btn.setToolTip(toggle_label)
        self._fx_toggle_clip_btn.setAccessibleName(toggle_label)
        self._fx_clear_clip_btn.setEnabled(bool(selected_clip is not None and (has_clip_fx or has_disabled_fx)))
        self._fx_clear_transition_btn.setEnabled(bool(selected_clip is not None and has_transition))
        self._fx_vfx_graph_btn.setVisible(has_vfx_graph)
        self._fx_vfx_graph_btn.setEnabled(has_vfx_graph)
        self._fx_summary_host.show()

    def _hide_mmd_physics_rows(self) -> None:
        for srow in (self._row_mmd_cloth_hair, self._row_mmd_follow):
            srow.set_enabled(False)
            srow.hide()

    def _mmd_playback_values(self, track: dict[str, Any]) -> dict[str, Any]:
        playback = track.get("playback") if isinstance(track, dict) else {}
        try:
            from app.mmd.schema import normalize_playback

            return normalize_playback(playback)
        except Exception:
            data = playback if isinstance(playback, dict) else {}
            try:
                rotation_hint = float(data.get("physics_rotation_hint_scale", 0.12))
            except Exception:
                rotation_hint = 0.12
            try:
                spring_response = float(data.get("physics_spring_response", 0.60))
            except Exception:
                spring_response = 0.60
            return {
                "enable_physics": bool(data.get("enable_physics", True)),
                "gpu_skinning": bool(data.get("gpu_skinning", True)),
                "physics_rotation_hint_scale": max(0.0, min(0.30, rotation_hint)),
                "physics_spring_response": max(0.15, min(1.50, spring_response)),
            }

    def clear(self) -> None:
        self._target = None
        self._move_rows_to_tab("clip")
        self._set_inspector_tab("clip")
        self._title.setText(tr("workbench.empty.title"))
        self._subtitle.setText(tr("workbench.empty.subtitle"))
        self._subtitle.show()
        for row in (
            self._row_name, self._row_source, self._row_duration,
            self._row_position, self._row_speed,
        ):
            row.set_value("—")
            row.show()
        # Slider rows: zero them out and disable to make "no target"
        # state explicit.
        for srow in (self._row_fade_in, self._row_fade_out, self._row_volume):
            srow.set_value(0)
            srow.set_enabled(False)
            srow.show()
        self._row_mmd_cloth_hair.set_value(0)
        self._row_mmd_follow.set_value(self.MMD_SPRING_RESPONSE_MIN)
        self._hide_mmd_physics_rows()
        self._rows_host.hide()
        if hasattr(self, "_audio_evidence_card"):
            self._audio_evidence_card.hide()
        if hasattr(self, "_sound_editor_panel"):
            self._sound_editor_panel.set_clip(None)
            self._sound_editor_panel.hide()
        if hasattr(self, "_typography_evidence_card"):
            self._typography_evidence_card.hide()
        if hasattr(self, "_edit_point_evidence_card"):
            self._edit_point_evidence_card.hide()
        if hasattr(self, "_live2d_mapping_host"):
            self._live2d_mapping_host.hide()
        if hasattr(self, "_live2d_evidence_card"):
            self._live2d_evidence_card.hide()
        if hasattr(self, "_mmd_editor_host"):
            self._mmd_editor_host.hide()
        if hasattr(self, "_ar_pbr_evidence_card"):
            self._ar_pbr_evidence_card.hide()
        self._node_graph_widget.hide()
        if hasattr(self, "_fx_summary_host"):
            self._fx_summary_host.hide()
        self._set_vfx_graph_strip(None)
        if hasattr(self, "_fx_vfx_graph_btn"):
            self._fx_vfx_graph_btn.hide()
        self._set_tab_empty_visible("clip", True, "Select a timeline clip or track to edit properties.")
        self._set_tab_empty_visible("audio", True, "Select an audio clip to edit gain, fades, and cleanup.")
        self._set_tab_empty_visible("fx", True, "Select a video track to edit its effect graph.")
        self._set_tab_empty_visible("mask", True, "Select a mask-capable node to edit tracking and masks.")
        self._set_tab_empty_visible("meta", True, "Selection metadata appears here.")

    def set_live2d_clip(self, track, clip) -> None:
        if clip is None:
            self.clear()
            return
        self._target = ("live2d", track, clip)
        self._move_rows_to_tab("clip")
        self._set_inspector_tab("clip")
        self._title.setText("Live2D Actor")
        self._subtitle.setText("model / motion / source mapping")
        self._subtitle.show()
        model_path = str(getattr(clip, "model_path", "") or "")
        motion = str(getattr(clip, "motion_group", "") or getattr(clip, "motion_name", "") or "")
        source_path = str(getattr(clip, "performance_source_path", "") or "")
        subject = str(getattr(clip, "performance_source_subject_type", "") or getattr(clip, "mocap_subject_type", "") or "not mapped")
        self._row_name.set_value(basename(model_path) if model_path else "Live2D clip")
        self._row_source.set_value(_compact_source_label(model_path), tooltip=model_path)
        self._row_duration.set_value(_format_ms(int(getattr(clip, "duration_ms", 0) or 0)))
        self._row_position.set_value(_format_ms(int(getattr(clip, "start_ms", 0) or 0)))
        self._row_speed.set_value(motion or subject)
        self._row_fade_in.hide()
        self._row_fade_out.hide()
        self._row_volume.hide()
        self._hide_mmd_physics_rows()
        self._rows_host.show()
        if hasattr(self, "_audio_evidence_card"):
            self._audio_evidence_card.hide()
        if hasattr(self, "_sound_editor_panel"):
            self._sound_editor_panel.hide()
        if hasattr(self, "_typography_evidence_card"):
            self._typography_evidence_card.hide()
        if hasattr(self, "_live2d_mapping_host"):
            self._live2d_mapping_host.show()
            key_count = 0
            for attr in ("kf_pos_x", "kf_pos_y", "kf_scale", "kf_opacity"):
                try:
                    key_count += len(list(getattr(clip, attr, []) or []))
                except Exception:
                    pass
            try:
                param_tracks = getattr(clip, "parameter_keyframes", None)
                if isinstance(param_tracks, dict):
                    key_count += sum(len(list(values or [])) for values in param_tracks.values())
            except Exception:
                pass
            self._live2d_mapping_meta.setText(
                f"{motion or 'Motion'} / {_format_ms(int(getattr(clip, 'duration_ms', 0) or 0))} / keys {key_count}"
            )
            source_label = basename(source_path) if source_path else ""
            if len(source_label) > 30:
                source_label = _compact_source_label(source_path, max_chars=30)
            mapped = f"Mapped source: {source_label} | subject: {subject}" if source_path else f"Mapped source: -- | subject: {subject}"
            self._live2d_mapping_body.setText(mapped)
            self._live2d_mapping_body.setToolTip(
                (
                    f"{source_path}\n"
                    "Performance Source Mapping writes face, eye, mouth, and framing keys to this actor clip."
                )
                if source_path
                else "Performance Source Mapping writes face, eye, mouth, and framing keys to this actor clip."
            )
        if hasattr(self, "_live2d_evidence_card"):
            self._live2d_evidence_card.set_clip(track, clip)
            self._live2d_evidence_card.show()
        if hasattr(self, "_mmd_editor_host"):
            self._mmd_editor_host.hide()
        if hasattr(self, "_ar_pbr_evidence_card"):
            self._ar_pbr_evidence_card.hide()
        self._node_graph_widget.hide()
        if hasattr(self, "_fx_summary_host"):
            self._fx_summary_host.hide()
        self._set_vfx_graph_strip(None)
        self._set_tab_empty_visible("clip", False)
        self._set_tab_empty_visible("audio", True, "Live2D actor clips do not use audio controls here.")
        self._set_tab_empty_visible("fx", True, "Live2D model/motion editing opens in the Live2D viewer.")
        self._set_tab_empty_visible("mask", True, "Performance Source tracking is an input-only VTuber mapping workflow.")
        self._set_tab_empty_visible(
            "meta",
            True,
            "Live2D actor\n"
            f"Track: {getattr(track, 'label', 'Live2D')}\n"
            f"Start: {_format_ms(int(getattr(clip, 'start_ms', 0) or 0))}\n"
            f"Duration: {_format_ms(int(getattr(clip, 'duration_ms', 0) or 0))}\n"
            f"Performance Source: {source_path or '-'}\n"
            f"Subject: {subject}",
        )

    def set_mmd_track(self, track: dict[str, Any] | None) -> None:
        if not isinstance(track, dict):
            self.clear()
            return
        self._target = ("mmd", track)
        self._move_rows_to_tab("clip")
        self._set_inspector_tab("clip")
        self._title.setText("MMD Model")
        self._subtitle.setText("toon shading / VMD motion / cloth-hair physics")
        self._subtitle.show()

        model_path = str(track.get("model_path") or track.get("asset_path") or "")
        motion_path = str(track.get("motion_path") or track.get("vmd_path") or "")
        start_ms = int(track.get("start_ms", 0) or 0)
        end_ms = int(track.get("end_ms", start_ms) or start_ms)
        playback = self._mmd_playback_values(track)
        rotation_hint = float(playback.get("physics_rotation_hint_scale", 0.12) or 0.12)
        spring_response = float(playback.get("physics_spring_response", 0.60) or 0.60)
        physics_state = "physics on" if bool(playback.get("enable_physics", True)) else "physics off"
        gpu_state = "gpu skinning" if bool(playback.get("gpu_skinning", True)) else "cpu skinning"
        motion_label = basename(motion_path) if motion_path else "no VMD"

        self._row_name.set_value(basename(model_path) if model_path else str(track.get("id") or "MMD model"))
        self._row_source.set_value(_compact_source_label(model_path), tooltip=model_path)
        self._row_duration.set_value(_format_ms(max(0, end_ms - start_ms)))
        self._row_position.set_value(_format_ms(start_ms))
        self._row_speed.set_value(f"{motion_label} / {physics_state} / {gpu_state}")
        self._row_fade_in.hide()
        self._row_fade_out.hide()
        self._row_volume.hide()
        self._row_mmd_cloth_hair.set_value(int(round(rotation_hint * 100.0)))
        self._row_mmd_follow.set_value(int(round(spring_response * 100.0)))
        self._row_mmd_cloth_hair.set_enabled(True)
        self._row_mmd_follow.set_enabled(True)
        self._row_mmd_cloth_hair.show()
        self._row_mmd_follow.show()
        self._rows_host.show()

        if hasattr(self, "_audio_evidence_card"):
            self._audio_evidence_card.hide()
        if hasattr(self, "_sound_editor_panel"):
            self._sound_editor_panel.hide()
        if hasattr(self, "_typography_evidence_card"):
            self._typography_evidence_card.hide()
        if hasattr(self, "_edit_point_evidence_card"):
            self._edit_point_evidence_card.hide()
        if hasattr(self, "_live2d_mapping_host"):
            self._live2d_mapping_host.hide()
        if hasattr(self, "_live2d_evidence_card"):
            self._live2d_evidence_card.hide()
        if hasattr(self, "_mmd_editor_host"):
            self._mmd_editor_host.show()
        if hasattr(self, "_ar_pbr_evidence_card"):
            self._ar_pbr_evidence_card.hide()
        self._node_graph_widget.hide()
        if hasattr(self, "_fx_summary_host"):
            self._fx_summary_host.hide()
        self._set_vfx_graph_strip(None)
        self._set_tab_empty_visible("clip", False)
        self._set_tab_empty_visible("audio", True, "MMD model tracks do not use audio controls here.")
        self._set_tab_empty_visible("fx", True, "MMD toon shading controls live on the model track.")
        self._set_tab_empty_visible("mask", True, "MMD model masks are not exposed in the editor yet.")
        self._set_tab_empty_visible(
            "meta",
            True,
            "MMD model\n"
            f"Track: {track.get('id', '-')}\n"
            f"Model: {model_path or '-'}\n"
            f"Motion: {motion_path or '-'}\n"
            f"Cloth/Hair: {rotation_hint:.2f}\n"
            f"Follow: {spring_response:.2f}",
        )

    def set_ar_pbr_track(self, track: dict[str, Any] | None) -> None:
        if not isinstance(track, dict):
            self.clear()
            return
        self._target = ("ar_pbr", track)
        self._move_rows_to_tab("clip")
        self._set_inspector_tab("clip")
        self._title.setText("3D / AR-PBR Object")
        self._subtitle.setText("Placed in the Viewer with transform, lighting, shadow, and scene-anchor state.")
        self._subtitle.show()
        asset_path = str(track.get("asset_path") or "")
        transform = track.get("transform") if isinstance(track.get("transform"), dict) else {}
        placement = track.get("placement") if isinstance(track.get("placement"), dict) else {}
        scale = transform.get("scale") if isinstance(transform, dict) else None
        position = transform.get("position") if isinstance(transform, dict) else None
        rotation = transform.get("rotation") if isinstance(transform, dict) else None
        start_ms = int(track.get("start_ms", 0) or 0)
        end_ms = int(track.get("end_ms", start_ms) or start_ms)
        self._row_name.set_value(basename(asset_path) if asset_path else str(track.get("id") or "3D object"))
        self._row_source.set_value(_compact_source_label(asset_path), tooltip=asset_path)
        self._row_duration.set_value(_format_ms(max(0, end_ms - start_ms)))
        self._row_position.set_value(_format_ms(start_ms))
        if isinstance(scale, (list, tuple)) and scale:
            try:
                avg_scale = sum(float(v) for v in scale[:3]) / max(1, min(3, len(scale)))
            except Exception:
                avg_scale = 1.0
        else:
            avg_scale = 1.0
        mode = str(placement.get("mode") or "manual") if isinstance(placement, dict) else "manual"
        self._row_speed.set_value(f"{mode} / scale {avg_scale:.2f}")
        self._row_fade_in.hide()
        self._row_fade_out.hide()
        self._row_volume.hide()
        self._hide_mmd_physics_rows()
        self._rows_host.show()
        if hasattr(self, "_audio_evidence_card"):
            self._audio_evidence_card.hide()
        if hasattr(self, "_sound_editor_panel"):
            self._sound_editor_panel.hide()
        if hasattr(self, "_typography_evidence_card"):
            self._typography_evidence_card.hide()
        if hasattr(self, "_live2d_mapping_host"):
            self._live2d_mapping_host.hide()
        if hasattr(self, "_live2d_evidence_card"):
            self._live2d_evidence_card.hide()
        if hasattr(self, "_mmd_editor_host"):
            self._mmd_editor_host.hide()
        if hasattr(self, "_ar_pbr_evidence_card"):
            self._ar_pbr_evidence_card.set_track(track)
            self._ar_pbr_evidence_card.show()
        self._node_graph_widget.hide()
        if hasattr(self, "_fx_summary_host"):
            self._fx_summary_host.hide()
        self._set_vfx_graph_strip(None)
        self._set_tab_empty_visible("clip", False)
        self._set_tab_empty_visible("audio", True, "3D object tracks do not use audio controls here.")
        self._set_tab_empty_visible("fx", True, "3D material and lighting controls are shown in the object workspace.")
        self._set_tab_empty_visible("mask", True, "Scene anchors, shadow catcher, and occlusion are handled by the 3D placement tools.")
        self._set_tab_empty_visible(
            "meta",
            True,
            "3D / AR-PBR object\n"
            f"Track: {track.get('id', '-')}\n"
            f"Asset: {asset_path or '-'}\n"
            f"Position: {position or '-'}\n"
            f"Rotation: {rotation or '-'}\n"
            f"Scale: {scale or '-'}",
        )

    def set_video_track(self, track, selected_clip=None) -> None:
        if track is None:
            self.clear()
            return
        self._target = ("video", track, selected_clip) if selected_clip is not None else ("video", track)
        self._move_rows_to_tab("clip")
        self._set_inspector_tab("clip")
        self._title.setText(tr("workbench.video_track.title"))
        self._subtitle.hide()
        src = getattr(track, "source_path", None)
        name = basename(str(src)) if src else "—"
        self._row_name.set_value(name)
        self._row_source.set_value(_compact_source_label(src), tooltip=str(src) if src else "")
        self._row_duration.set_value(_format_ms(getattr(track, "duration_ms", 0)))
        offset_ms = int(getattr(track, "offset_ms", 0))
        self._row_position.set_value(_format_ms(offset_ms))
        # Video tracks model fades as a FadeSegment list. The
        # workbench treats a leading ``kind="in"`` segment at offset 0
        # as the fade-in and a trailing ``kind="out"`` segment ending
        # at duration as the fade-out. Slider edits push back through
        # the editor's ``_on_workbench_fade_*_changed`` handlers,
        # which create / update / remove these segments.
        fi_ms, fo_ms = self._derive_video_fades(track)
        self._row_fade_in.set_value(min(fi_ms, self.FADE_MAX_MS))
        self._row_fade_out.set_value(min(fo_ms, self.FADE_MAX_MS))
        self._row_fade_in.set_enabled(True)
        self._row_fade_out.set_enabled(True)
        self._row_fade_in.show()
        self._row_fade_out.show()
        # Video tracks don't carry a per-clip volume; hide that row.
        self._row_volume.hide()
        self._hide_mmd_physics_rows()
        segs = getattr(track, "speed_segments", []) or []
        if segs:
            self._row_speed.set_value(
                tr("workbench.value.speed_segments", count=len(segs))
            )
        else:
            self._row_speed.set_value("1.00x")
        self._rows_host.show()
        if hasattr(self, "_audio_evidence_card"):
            self._audio_evidence_card.hide()
        if hasattr(self, "_sound_editor_panel"):
            self._sound_editor_panel.hide()
        if hasattr(self, "_typography_evidence_card"):
            self._typography_evidence_card.hide()
        if hasattr(self, "_edit_point_evidence_card"):
            show_edit_point = bool(selected_clip is not None and _EditPointEvidenceCard.has_edit_point(track, selected_clip))
            if show_edit_point:
                self._edit_point_evidence_card.set_context(track, selected_clip)
            self._edit_point_evidence_card.setVisible(show_edit_point)
        self._set_tab_empty_visible("clip", False)
        self._set_tab_empty_visible("audio", True, "Select an audio clip to edit gain, fades, and cleanup.")

        if hasattr(self, "_live2d_mapping_host"):
            self._live2d_mapping_host.hide()
        if hasattr(self, "_live2d_evidence_card"):
            self._live2d_evidence_card.hide()
        if hasattr(self, "_mmd_editor_host"):
            self._mmd_editor_host.hide()
        if hasattr(self, "_ar_pbr_evidence_card"):
            self._ar_pbr_evidence_card.hide()
        self._set_fx_summary(track, selected_clip)
        vfx_summary = self.vfx_node_graph_summary_text(track)
        has_selected_clip_fx = False
        has_typography_actor = False
        typography_actors: list[Any] = []
        if selected_clip is not None:
            target_start = int(getattr(selected_clip, "timeline_in_ms", 0) or 0)
            target_end = int(getattr(selected_clip, "timeline_out_ms", target_start) or target_start)
            for actor in getattr(track, "typography_actors", []) or []:
                if self._overlaps(
                    target_start,
                    target_end,
                    int(getattr(actor, "start_ms", 0) or 0),
                    int(getattr(actor, "end_ms", 0) or 0),
                ):
                    typography_actors.append(actor)
            has_typography_actor = bool(typography_actors)
            has_selected_clip_fx = any(
                self._param_active(getattr(selected_clip, attr, None))
                for attr in (
                    "video_filters",
                    "chroma_key",
                    "bg_removal",
                    "disabled_video_filters",
                    "disabled_chroma_key",
                    "disabled_bg_removal",
                )
            ) or bool(str(getattr(selected_clip, "transition_out_type", "") or ""))
        if hasattr(self, "_typography_evidence_card"):
            self._typography_evidence_card.set_actors(typography_actors)
            self._typography_evidence_card.setVisible(has_typography_actor)
        # NodeGraph is primary for node/effect work. Hide the empty default graph
        # when this selection is really a typography workspace.
        self._node_graph_widget.set_track(track)
        show_node_graph = bool(vfx_summary != "VFX graph: none" or not has_typography_actor)
        self._node_graph_widget.setVisible(show_node_graph)
        self._set_tab_empty_visible("fx", False)
        if has_selected_clip_fx or has_typography_actor or vfx_summary != "VFX graph: none":
            self._set_inspector_tab("fx")
        meta_text = (
            f"Video track\nName: {name}\nDuration: "
            f"{_format_ms(getattr(track, 'duration_ms', 0))}\n"
            f"Position: {_format_ms(offset_ms)}"
        )
        if vfx_summary != "VFX graph: none":
            meta_text = f"{meta_text}\n{vfx_summary}"
        self._set_tab_empty_visible("meta", True, meta_text)

    def vfx_node_graph_qa_payload(self, track=None) -> dict[str, Any]:
        if track is None:
            target = self._target or ()
            if target and target[0] == "video":
                track = target[1]
        return vfx_node_graph_status_for_track(track) if track is not None else {
            "ok": False,
            "graph_count": 0,
            "node_count": 0,
            "summary": "VFX graph: none",
            "warnings": [],
        }

    def vfx_node_graph_summary_text(self, track=None) -> str:
        return str(self.vfx_node_graph_qa_payload(track).get("summary") or "VFX graph: none")

    def set_audio_clip(self, track, clip) -> None:
        if clip is None:
            self.clear()
            return
        self._target = ("audio", track, clip)
        self._set_inspector_tab("audio")
        self._title.setText("Sound Editor")
        self._subtitle.hide()
        src = getattr(clip, "source_path", None)
        name = (
            getattr(clip, "display_name", None)
            or (basename(str(src)) if src else "—")
        )
        self._row_name.set_value(name)
        self._row_source.set_value(_compact_source_label(src), tooltip=str(src) if src else "")
        self._row_duration.set_value(_format_ms(getattr(clip, "duration_ms", 0)))
        self._row_position.set_value(_format_ms(int(getattr(clip, "offset_ms", 0))))
        fi = int(getattr(clip, "fade_in_ms", 0))
        fo = int(getattr(clip, "fade_out_ms", 0))
        self._row_fade_in.set_value(min(fi, self.FADE_MAX_MS))
        self._row_fade_out.set_value(min(fo, self.FADE_MAX_MS))
        self._row_fade_in.set_enabled(True)
        self._row_fade_out.set_enabled(True)
        self._row_fade_in.show()
        self._row_fade_out.show()
        # Volume slider — int tenths of dB.
        vol_db = float(getattr(track, "master_volume", 0.0) or 0.0)
        clamped = max(self.VOLUME_MIN_DB, min(self.VOLUME_MAX_DB, vol_db))
        self._row_volume.set_value(int(round(clamped * 10)))
        self._row_volume.set_enabled(True)
        self._row_volume.show()
        self._hide_mmd_physics_rows()
        if hasattr(self, "_audio_evidence_card"):
            self._audio_evidence_card.hide()
        if hasattr(self, "_sound_editor_panel"):
            self._sound_editor_panel.set_clip(
                clip,
                track=track,
                context_label="Timeline Audio",
                context_key=f"timeline:{getattr(track, 'id', 'none')}:{getattr(clip, 'id', 'none')}",
            )
            self._sound_editor_panel.show()
        self._set_tab_empty_visible("audio", False)
        self._set_tab_empty_visible("clip", True, "Select a video clip or track to edit clip properties.")
        self._set_tab_empty_visible("fx", True, "Audio clips do not carry video effect graphs yet.")
        speed = float(getattr(clip, "speed", 1.0))
        self._row_speed.set_value(f"{speed:.2f}x")
        self._rows_host.hide()
        if hasattr(self, "_live2d_mapping_host"):
            self._live2d_mapping_host.hide()
        if hasattr(self, "_live2d_evidence_card"):
            self._live2d_evidence_card.hide()
        if hasattr(self, "_mmd_editor_host"):
            self._mmd_editor_host.hide()
        if hasattr(self, "_ar_pbr_evidence_card"):
            self._ar_pbr_evidence_card.hide()
        # Audio clips don't carry a NodeGraph yet — hide the section.
        self._node_graph_widget.hide()
        if hasattr(self, "_fx_summary_host"):
            self._fx_summary_host.hide()
        if hasattr(self, "_fx_empty_label"):
            self._fx_empty_label.show()
        if hasattr(self, "_meta_empty_label"):
            self._meta_empty_label.setText(
                f"Audio clip\nName: {name}\nDuration: "
                f"{_format_ms(getattr(clip, 'duration_ms', 0))}\n"
                f"Position: {_format_ms(int(getattr(clip, 'offset_ms', 0)))}"
            )

    def set_audio_source_clip(self, clip, *, source_path=None) -> None:
        """Show a media-pool audio source in the Workbench sound editor."""
        if clip is None:
            self.clear()
            return
        self._target = ("audio_source", clip)
        self._set_inspector_tab("audio")
        self._title.setText("Sound Editor")
        self._subtitle.hide()
        src = source_path or getattr(clip, "source_path", None)
        name = getattr(clip, "display_name", None) or (basename(str(src)) if src else "Audio source")
        self._row_name.set_value(name)
        self._row_source.set_value(_compact_source_label(src), tooltip=str(src) if src else "")
        self._row_duration.set_value(_format_ms(getattr(clip, "duration_ms", 0)))
        self._row_position.set_value("Media Pool")
        self._row_fade_in.set_value(min(int(getattr(clip, "fade_in_ms", 0) or 0), self.FADE_MAX_MS))
        self._row_fade_out.set_value(min(int(getattr(clip, "fade_out_ms", 0) or 0), self.FADE_MAX_MS))
        self._row_fade_in.set_enabled(True)
        self._row_fade_out.set_enabled(True)
        self._row_fade_in.show()
        self._row_fade_out.show()
        gain = float(getattr(clip, "gain", 1.0) or 1.0)
        self._row_volume.set_value(int(round(max(self.VOLUME_MIN_DB, min(self.VOLUME_MAX_DB, gain * 10.0)) * 10)))
        self._row_volume.set_enabled(False)
        self._row_volume.hide()
        self._hide_mmd_physics_rows()
        self._row_speed.set_value(f"{float(getattr(clip, '_se_speed', 1.0) or 1.0):.2f}x")
        self._rows_host.hide()
        if hasattr(self, "_audio_evidence_card"):
            self._audio_evidence_card.hide()
        if hasattr(self, "_sound_editor_panel"):
            self._sound_editor_panel.set_clip(
                clip,
                track=None,
                context_label="Media Pool Audio",
                context_key=f"media:{src}",
            )
            self._sound_editor_panel.show()
        if hasattr(self, "_live2d_mapping_host"):
            self._live2d_mapping_host.hide()
        if hasattr(self, "_live2d_evidence_card"):
            self._live2d_evidence_card.hide()
        if hasattr(self, "_mmd_editor_host"):
            self._mmd_editor_host.hide()
        if hasattr(self, "_ar_pbr_evidence_card"):
            self._ar_pbr_evidence_card.hide()
        self._node_graph_widget.hide()
        if hasattr(self, "_fx_summary_host"):
            self._fx_summary_host.hide()
        self._set_tab_empty_visible("audio", False)
        self._set_tab_empty_visible("clip", True, "Select a timeline clip or track to edit clip properties.")
        self._set_tab_empty_visible("fx", True, "Media-pool audio sources do not carry video effect graphs.")
        self._set_tab_empty_visible("mask", True, "Audio sources do not use mask controls.")
        if hasattr(self, "_meta_empty_label"):
            self._meta_empty_label.setText(
                f"Media-pool audio\nName: {name}\nDuration: "
                f"{_format_ms(getattr(clip, 'duration_ms', 0))}\nSource: {src or '-'}"
            )

    def _on_sound_editor_changed(self) -> None:
        target = self.current_target()
        if target and target[0] == "audio" and hasattr(self, "_audio_evidence_card"):
            _kind, track, clip = target
            self._audio_evidence_card.set_clip(track, clip)
            self._audio_evidence_card.update()
        elif target and target[0] == "audio_source" and hasattr(self, "_audio_evidence_card"):
            _kind, clip = target
            self._audio_evidence_card.set_clip(None, clip)
            self._audio_evidence_card.update()
        self.sound_editor_changed.emit()

    def current_target(self) -> tuple | None:
        """Return the editor-side identifier for the currently
        displayed selection. Used by the editor to route slider
        signals to the right object."""
        return self._target

    def refresh_sound_editor_waveform(self) -> None:
        panel = getattr(self, "_sound_editor_panel", None)
        if panel is not None and hasattr(panel, "refresh_waveform"):
            panel.refresh_waveform()

    def _derive_video_fades(self, track) -> tuple[int, int]:
        """Best-effort fade-in / fade-out duration extraction from a
        video track's ``FadeSegment`` list. Returns ``(in_ms, out_ms)``.
        A FadeSegment is treated as the leading fade if it starts at
        ms 0 and its kind is in / both, and as the trailing fade if it
        ends within ~100 ms of the track duration."""
        fades = getattr(track, "fades", []) or []
        dur = int(getattr(track, "duration_ms", 0) or 0)
        in_ms = 0
        out_ms = 0
        for f in fades:
            start = int(getattr(f, "start_ms", -1) or 0)
            end = int(getattr(f, "end_ms", -1) or 0)
            kind = getattr(f, "kind", "both")
            length = max(0, end - start)
            if start <= 0 and kind in ("in", "both"):
                in_ms = max(in_ms, length)
            if dur > 0 and end >= dur - 100 and kind in ("out", "both"):
                out_ms = max(out_ms, length)
        return in_ms, out_ms

    # ---- i18n ----

    def retranslate(self) -> None:
        self._title.setText(tr("workbench.empty.title"))
        self._subtitle.setText(tr("workbench.empty.subtitle"))
        self._row_name.set_label(tr("workbench.row.name"))
        self._row_source.set_label(tr("workbench.row.source"))
        self._row_duration.set_label(tr("workbench.row.duration"))
        self._row_position.set_label(tr("workbench.row.position"))
        self._row_fade_in.set_label(tr("workbench.row.fade_in"))
        self._row_fade_out.set_label(tr("workbench.row.fade_out"))
        self._row_volume.set_label(tr("workbench.row.volume"))
        self._row_speed.set_label(tr("workbench.row.speed"))
        self._node_graph_widget.retranslate()

    # ---- NodeGraph popout (Phase 2A) ----

    def _on_node_graph_selection_changed(self, label: str) -> None:
        """Bubble selection to the legacy ``node_focused`` signal so
        editor-side hooks (color popout routing) stay live. Empty
        label means nothing is selected."""
        if label and "Color" in label:
            self.node_focused.emit("color")

    def _toggle_node_graph_popout(self) -> None:
        if (
            self._node_graph_popout is not None
            and self._node_graph_popout.isVisible()
        ):
            self._node_graph_popout.close()
            return
        from app.workbench.node_graph.popout import NodeGraphPopoutWindow
        self._node_graph_popout = NodeGraphPopoutWindow(self)
        self._node_graph_popout.closed.connect(
            self._on_node_graph_popout_closed,
        )
        # Reparent the widget into the popout. Save the index so we
        # can re-insert at the same spot when the window closes.
        self._node_graph_popout_index = self._node_graph_root_layout.indexOf(
            self._node_graph_widget,
        )
        self._node_graph_root_layout.removeWidget(self._node_graph_widget)
        # Drop a placeholder so the dock layout doesn't collapse.
        self._node_graph_placeholder = QLabel(
            tr("workbench.node_graph_popout.placeholder"),
            self,
        )
        self._node_graph_placeholder.setAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )
        self._node_graph_placeholder.setMinimumHeight(80)
        self._node_graph_placeholder.setWordWrap(True)
        self._node_graph_placeholder.setStyleSheet(
            "color: #8a8a8a; font-style: italic; font-size: 11px; "
            "background-color: #15151a; border: 1px dashed #2a2a2a; "
            "border-radius: 4px; padding: 12px;"
        )
        self._node_graph_root_layout.insertWidget(
            self._node_graph_popout_index,
            self._node_graph_placeholder,
            stretch=1,
        )
        self._node_graph_popout.install(self._node_graph_widget)
        self._node_graph_popout.show()
        self._node_graph_popout.raise_()
        self._node_graph_popout.activateWindow()

    def _on_node_graph_popout_closed(self) -> None:
        if self._node_graph_placeholder is not None:
            idx = self._node_graph_root_layout.indexOf(
                self._node_graph_placeholder,
            )
            self._node_graph_root_layout.removeWidget(
                self._node_graph_placeholder,
            )
            self._node_graph_placeholder.deleteLater()
            self._node_graph_placeholder = None
        else:
            idx = self._node_graph_popout_index
        self._node_graph_widget.setParent(self)
        self._node_graph_root_layout.insertWidget(
            max(0, idx), self._node_graph_widget, stretch=1,
        )
        # Only reveal if a video track is currently selected — keeps
        # the panel hidden after re-dock when the user switched to an
        # audio clip while the popout was open.
        if self._target is not None and self._target[0] == "video":
            self._node_graph_widget.show()
        else:
            self._node_graph_widget.hide()
        if self._node_graph_popout is not None:
            self._node_graph_popout.deleteLater()
            self._node_graph_popout = None
