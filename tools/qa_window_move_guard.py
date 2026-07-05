"""QA for windowed titlebar drag responsiveness guards."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def run_window_move_guard_qa() -> dict[str, Any]:
    app = _qapp()
    from PySide6.QtCore import Qt

    from app.project_player import ProjectPlayer
    from app.video_editor_window import (
        AudioMixerPanel,
        VideoEditorWindow,
        _AnimatedTimelineToolButton,
        _PresetPreviewSwatch,
        _StudioPresetTile,
    )

    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    player = ProjectPlayer()
    try:
        player._timer.setTimerType(Qt.TimerType.PreciseTimer)
        player._timer.setInterval(17)
        player.set_window_move_guard(True)
        checks["project_player_uses_coarse_timer"] = (
            player._timer.timerType() == Qt.TimerType.CoarseTimer
            and player._timer.interval() >= 100
        )
        player.set_window_move_guard(False)
        checks["project_player_restores_precise_timer"] = (
            player._timer.timerType() == Qt.TimerType.PreciseTimer
            and player._timer.interval() == 17
        )
    finally:
        player.release()

    tool = _AnimatedTimelineToolButton("select", "cursor")
    tool.setCheckable(True)
    try:
        tool.setChecked(True)
        app.processEvents()
        tool_running_before = tool._anim_timer.isActive()
        tool.set_animation_suspended(True)
        tool_stopped = not tool._anim_timer.isActive()
        tool.set_animation_suspended(False)
        checks["timeline_tool_animation_suspends"] = tool_running_before and tool_stopped and tool._anim_timer.isActive()
    finally:
        tool.deleteLater()

    tile = _StudioPresetTile(
        "Soft Pop",
        "FX",
        palette_seed="soft-pop",
        tooltip="Soft Pop",
        preview_kind="effect",
        preview_payload={"video_filters": {"brightness": 8}},
    )
    try:
        tile._hovered = True
        tile._anim_timer.start()
        tile._preview_timer.start()
        tile._live_preview_timer.start()
        tile.set_window_move_suspended(True)
        tile_stopped = (
            not tile._anim_timer.isActive()
            and not tile._preview_timer.isActive()
            and not tile._live_preview_timer.isActive()
        )
        tile.set_window_move_suspended(False)
        checks["preset_tile_timers_suspend"] = tile_stopped and tile._anim_timer.isActive()
    finally:
        tile.deleteLater()

    swatch = _PresetPreviewSwatch(("#FF7B5C", "#8A7CFF", "#63D7FF"), label="Demo")
    try:
        swatch.show()
        app.processEvents()
        swatch_running_before = swatch._timer.isActive()
        swatch.set_window_move_suspended(True)
        swatch_stopped = not swatch._timer.isActive()
        swatch.set_window_move_suspended(False)
        checks["preset_swatch_timer_suspends"] = swatch_running_before and swatch_stopped and swatch._timer.isActive()
    finally:
        swatch.close()
        swatch.deleteLater()

    mixer = AudioMixerPanel()
    try:
        mixer_running_before = mixer._vu_decay_timer.isActive()
        mixer.set_window_move_suspended(True)
        mixer_stopped = not mixer._vu_decay_timer.isActive()
        mixer.set_window_move_suspended(False)
        checks["audio_mixer_vu_timer_suspends"] = mixer_running_before and mixer_stopped and mixer._vu_decay_timer.isActive()
    finally:
        mixer.close()
        mixer.deleteLater()

    win = VideoEditorWindow()
    try:
        win.show()
        app.processEvents()
        win._begin_window_move_guard()
        app.processEvents()
        stats = dict(getattr(win, "_window_move_guard_stats", {}) or {})
        checks["video_editor_guard_activates"] = bool(getattr(win, "_window_move_guard_active", False))
        checks["video_editor_guard_suspends_surfaces"] = (
            int(stats.get("blade_dash", 0) or 0) >= 1
            and int(stats.get("timeline_tool_buttons", 0) or 0) >= 6
        )
        checks["video_editor_player_guard_active"] = bool(getattr(win._player, "_window_move_guard_active", False))
        win._end_window_move_guard()
        checks["video_editor_guard_restores"] = (
            not bool(getattr(win, "_window_move_guard_active", False))
            and not bool(getattr(win._player, "_window_move_guard_active", False))
            and win._blade_dash_timer.isActive()
        )
        details["video_editor_stats"] = stats
    finally:
        win.close()
        win.deleteLater()
        app.processEvents()

    failures = [name for name, ok in checks.items() if not ok]
    return {
        "ok": not failures,
        "summary": {
            "checks": len(checks),
            "passing": len(checks) - len(failures),
            "failures": len(failures),
            **details,
        },
        "checks": checks,
        "failures": failures,
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Run window move guard QA.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/window_move_guard_qa.json"))
    args = parser.parse_args()
    report = run_window_move_guard_qa()
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
