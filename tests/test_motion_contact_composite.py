from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.actions.registry import ActionRegistry
from app.motion_designer.contact_composite import prepare_contact_composite


def _assets(root: Path) -> tuple[Path, Path]:
    foreground = np.zeros((120, 160, 4), dtype=np.uint8)
    cv2.circle(foreground, (80, 58), 30, (220, 220, 220, 255), -1, cv2.LINE_AA)
    background = np.full((120, 160, 3), (38, 68, 108), dtype=np.uint8)
    foreground_path = root / "foreground.png"
    background_path = root / "background.png"
    assert cv2.imwrite(str(foreground_path), foreground)
    assert cv2.imwrite(str(background_path), background)
    return foreground_path, background_path


def test_contact_composite_writes_shared_rgba_assets(tmp_path: Path) -> None:
    foreground, background = _assets(tmp_path)
    report = prepare_contact_composite(
        foreground_path=foreground,
        background_path=background,
        output_dir=tmp_path / "output",
    )

    corrected = cv2.imread(report["foreground_path"], cv2.IMREAD_UNCHANGED)
    shadow = cv2.imread(report["shadow_path"], cv2.IMREAD_UNCHANGED)
    assert corrected.shape == (120, 160, 4)
    assert shadow.shape == (120, 160, 4)
    assert np.count_nonzero(shadow[:, :, 3]) > 0
    assert report["diagnostics"]["preview_export_assets_shared"] is True


def test_contact_composite_action_is_ownerless(tmp_path: Path) -> None:
    foreground, background = _assets(tmp_path)
    execution = ActionRegistry().execute("motion.ai.contact_composite.prepare", {
        "foreground_path": str(foreground),
        "background_path": str(background),
        "output_dir": str(tmp_path / "action_output"),
    })

    assert execution.ok
    assert Path(execution.result["shadow_path"]).is_file()
