from __future__ import annotations

import subprocess
import sys
from typing import Any


def hidden_subprocess_kwargs() -> dict[str, Any]:
    """Return Windows kwargs that prevent helper console windows.

    ffmpeg, Python helpers, and native workers are command-line programs.
    When TigerCapture itself is launched as a GUI app on Windows, spawning
    those helpers without these flags can flash black terminal windows.
    """
    if sys.platform != "win32":
        return {}
    kwargs: dict[str, Any] = {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
    }
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        kwargs["startupinfo"] = startupinfo
    except Exception:
        pass
    return kwargs


def merge_hidden_subprocess_kwargs(**kwargs: Any) -> dict[str, Any]:
    """Merge caller kwargs with Windows no-console defaults.

    Explicit caller values win, so tests can still override subprocess
    behavior without fighting the helper.
    """
    hidden = hidden_subprocess_kwargs()
    hidden.update(kwargs)
    return hidden


def configure_hidden_qprocess(process: Any) -> None:
    """Apply Windows no-console flags to a QProcess instance."""
    if sys.platform != "win32" or process is None:
        return

    def _modifier(args: Any) -> None:
        try:
            args.flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        except Exception:
            pass
        try:
            args.startupInfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            args.startupInfo.wShowWindow = 0
        except Exception:
            pass

    try:
        process.setCreateProcessArgumentsModifier(_modifier)
    except Exception:
        pass
