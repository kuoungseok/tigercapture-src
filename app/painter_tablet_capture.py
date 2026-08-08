"""Raw QTabletEvent capture surface for Painter hardware evidence."""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPaintEvent, QPainter, QTabletEvent
from PySide6.QtWidgets import QWidget


class PainterTabletCaptureSurface(QWidget):
    """Collect actual Qt tablet events; synthetic samples are not accepted."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tiger Painter physical tablet evidence")
        self.setAttribute(Qt.WidgetAttribute.WA_TabletTracking, True)
        self.setMinimumSize(720, 420)
        self.events: list[dict[str, Any]] = []
        self.paint_receipts_ns: list[int] = []

    def tabletEvent(self, event: QTabletEvent) -> None:  # noqa: N802 - Qt override
        device = event.pointingDevice()
        position = event.position()
        global_position = event.globalPosition()
        self.events.append({
            "sequence": len(self.events),
            "event_type": event.type().name,
            "qt_timestamp_ms": int(event.timestamp()),
            "received_monotonic_ns": time.perf_counter_ns(),
            "position": [float(position.x()), float(position.y())],
            "global_position": [float(global_position.x()), float(global_position.y())],
            "pressure": float(event.pressure()),
            "x_tilt_degrees": float(event.xTilt()),
            "y_tilt_degrees": float(event.yTilt()),
            "rotation_degrees": float(event.rotation()),
            "tangential_pressure": float(event.tangentialPressure()),
            "z": float(event.z()),
            "button": event.button().name,
            "buttons": int(event.buttons().value),
            "device": {
                "name": device.name(),
                "system_id": int(device.systemId()),
                "device_type": str(device.type()),
                "pointer_type": str(device.pointerType()),
                "capabilities": str(device.capabilities()),
                "unique_id": int(device.uniqueId().numericId()),
            },
        })
        event.accept()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt override
        self.paint_receipts_ns.append(time.perf_counter_ns())
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawText(
            self.rect().adjusted(28, 28, -28, -28),
            Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            "Draw here with a physical pen. The report passes only after real "
            "TabletPress, TabletMove, and TabletRelease events are captured.",
        )
        painter.end()
        super().paintEvent(event)


def summarize_tablet_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    types = [str(row.get("event_type") or "") for row in events]
    devices = {
        (
            str((row.get("device") or {}).get("name") or ""),
            int((row.get("device") or {}).get("system_id") or 0),
            str((row.get("device") or {}).get("pointer_type") or ""),
        )
        for row in events
    }
    required = {"TabletPress", "TabletMove", "TabletRelease"}
    return {
        "event_count": len(events),
        "event_types": sorted(set(types)),
        "device_count": len(devices),
        "devices": [list(row) for row in sorted(devices)],
        "pressure_range": [
            min((float(row.get("pressure", 0.0)) for row in events), default=0.0),
            max((float(row.get("pressure", 0.0)) for row in events), default=0.0),
        ],
        "tilt_observed": any(
            float(row.get("x_tilt_degrees", 0.0)) != 0.0
            or float(row.get("y_tilt_degrees", 0.0)) != 0.0
            for row in events
        ),
        "rotation_observed": any(float(row.get("rotation_degrees", 0.0)) != 0.0 for row in events),
        "tangential_pressure_observed": any(
            float(row.get("tangential_pressure", 0.0)) != 0.0 for row in events
        ),
        "required_sequence_captured": required.issubset(types),
        "limitations": [
            "Zero tilt, rotation, or tangential pressure may mean the device does not support that axis.",
            "Qt timestamps and Python monotonic timestamps have different origins; this report does not subtract them.",
            "Paint-event receipt is not physical pen-down latency or display photon latency.",
        ],
    }


__all__ = ["PainterTabletCaptureSurface", "summarize_tablet_events"]
