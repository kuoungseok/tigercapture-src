"""Native runtime measurements for Painter evidence collection.

This module does not force a Qt platform plugin or scale factor.  Callers must
preserve that distinction: device enumeration is not a physical pen event,
and a simulated scale factor is not a native high-DPI run.
"""
from __future__ import annotations

import os
import platform
from typing import Any


NON_NATIVE_QPA_PLUGINS = {"offscreen", "minimal", "minimalegl", "vnc"}


def environment_overrides() -> dict[str, str]:
    return {
        name: os.environ.get(name, "")
        for name in ("QT_QPA_PLATFORM", "QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS")
    }


def is_native_qt_environment(platform_name: str, overrides: dict[str, str]) -> bool:
    plugin = str(platform_name or "").strip().casefold()
    forced_plugin = overrides.get("QT_QPA_PLATFORM", "").strip().casefold()
    has_simulated_scale = bool(
        overrides.get("QT_SCALE_FACTOR", "").strip()
        or overrides.get("QT_SCREEN_SCALE_FACTORS", "").strip()
    )
    return bool(
        plugin
        and plugin not in NON_NATIVE_QPA_PLUGINS
        and forced_plugin not in NON_NATIVE_QPA_PLUGINS
        and not has_simulated_scale
    )


def screen_measurements(app: Any) -> list[dict[str, Any]]:
    rows = []
    for screen in app.screens():
        geometry = screen.geometry()
        available = screen.availableGeometry()
        rows.append({
            "name": screen.name(),
            "geometry": [geometry.x(), geometry.y(), geometry.width(), geometry.height()],
            "available_geometry": [
                available.x(), available.y(), available.width(), available.height()
            ],
            "device_pixel_ratio": float(screen.devicePixelRatio()),
            "logical_dpi": [float(screen.logicalDotsPerInchX()), float(screen.logicalDotsPerInchY())],
            "physical_dpi": [float(screen.physicalDotsPerInchX()), float(screen.physicalDotsPerInchY())],
            "physical_size_mm": [float(screen.physicalSize().width()), float(screen.physicalSize().height())],
            "refresh_rate_hz": float(screen.refreshRate()),
        })
    return rows


def korean_font_measurement(app: Any, sample: str = "브러시 크기 불투명도 레이어") -> dict[str, Any]:
    from PySide6.QtGui import QFontMetrics

    font = app.font()
    metrics = QFontMetrics(font)
    missing = [character for character in sample if not character.isspace() and not metrics.inFont(character)]
    bounds = metrics.boundingRect(sample)
    return {
        "family": font.family(),
        "sample": sample,
        "all_glyphs_supported": not missing,
        "missing_characters": missing,
        "bounding_size": [bounds.width(), bounds.height()],
    }


def pointing_device_inventory() -> list[dict[str, Any]]:
    from PySide6.QtGui import QInputDevice, QPointingDevice

    rows = []
    for device in QInputDevice.devices():
        row = {
            "name": device.name(),
            "system_id": int(device.systemId()),
            "device_type": str(device.type()),
            "capabilities": str(device.capabilities()),
            "seat_name": device.seatName(),
        }
        if isinstance(device, QPointingDevice):
            row.update({
                "pointer_type": str(device.pointerType()),
                "maximum_points": int(device.maximumPoints()),
                "button_count": int(device.buttonCount()),
                "unique_id": int(device.uniqueId().numericId()),
            })
        rows.append(row)
    return rows


def runtime_identity() -> dict[str, Any]:
    from PySide6 import QtCore

    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "qt": QtCore.qVersion(),
        "pyside": QtCore.__version__,
    }


__all__ = [
    "NON_NATIVE_QPA_PLUGINS",
    "environment_overrides",
    "is_native_qt_environment",
    "korean_font_measurement",
    "pointing_device_inventory",
    "runtime_identity",
    "screen_measurements",
]
