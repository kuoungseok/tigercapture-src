"""Video editor integration for Character Asset Hub."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PySide6.QtWidgets import QMessageBox


def _open_character_asset_hub(self, root_path: str = "") -> Any:
    from app.character_asset_hub_window import CharacterAssetHubDialog

    existing = getattr(self, "_character_asset_hub_dialog", None)
    if existing is not None:
        try:
            if str(root_path or "").strip():
                existing.set_root_path(root_path)
                existing.scan_current_folder()
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return existing
        except Exception:
            pass

    dialog = CharacterAssetHubDialog(root_path, self)
    dialog.action_requested.connect(self._execute_character_asset_hub_action)
    dialog.finished.connect(lambda _code: setattr(self, "_character_asset_hub_dialog", None))
    self._character_asset_hub_dialog = dialog
    dialog.show()
    return dialog


def _execute_character_asset_hub_action(self, action_id: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    from app.actions import build_default_action_registry

    action = str(action_id or "").strip()
    if not action:
        return {"ok": False, "error": "missing_action"}
    payload = dict(params or {})
    registry = build_default_action_registry(self)
    result = registry.execute_action(action, payload)
    data = result.to_dict()
    if result.ok:
        _after_character_asset_hub_action(self, action, data)
        return data
    QMessageBox.warning(
        self,
        "Character Asset Hub",
        f"Could not add character asset.\n\n{action}\n{result.error}",
    )
    return data


def _after_character_asset_hub_action(self, action: str, result: Mapping[str, Any]) -> None:
    try:
        player = getattr(self, "_player", None)
        if player is not None and hasattr(player, "refresh_current_frame"):
            player.refresh_current_frame()
    except Exception:
        pass
    try:
        if hasattr(self, "_refresh_player_tracks"):
            self._refresh_player_tracks()
    except Exception:
        pass
    try:
        if hasattr(self, "_flash_status"):
            label = {
                "actor.add": "Actor added from Character Asset Hub",
                "mmd.actor.add": "MMD actor added from Character Asset Hub",
                "vtuber.vseeface_select_vrm0_avatar": "VRM Avatar Target selected from Character Asset Hub",
            }.get(str(action), "Character Asset Hub action complete")
            self._flash_status(label)
    except Exception:
        pass


def _open_character_asset_hub_for_path(self, path: str | Path) -> Any:
    return _open_character_asset_hub(self, str(path or ""))
