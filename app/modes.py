from enum import Enum

from app.i18n import tr


class CaptureMode(Enum):
    SCREENSHOT = "screenshot"
    GIF = "gif"
    VIDEO = "video"


MODE_ICONS: dict[CaptureMode, str] = {
    CaptureMode.SCREENSHOT: "📷",
    CaptureMode.GIF: "🎞",
    CaptureMode.VIDEO: "🎬",
}


def mode_label(mode: CaptureMode) -> str:
    key = {
        CaptureMode.SCREENSHOT: "mode.screenshot",
        CaptureMode.GIF: "mode.gif",
        CaptureMode.VIDEO: "mode.video",
    }[mode]
    return tr(key)
