from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal


class PreviewPrerenderWorker(QThread):
    """Pre-render CPU node effects for near-future preview frames.

    This worker is intentionally narrow: it bakes the active source frame plus
    node/effect/mask chain only. Timeline transitions, PIP, actor overlays, and
    final viewer emission stay in ``ProjectPlayer`` so complex edits cannot use
    stale worker output.
    """

    frame_ready = Signal(int, object)  # frame_idx, rgb ndarray
    failed = Signal(str)

    def __init__(
        self,
        source_path: Path | str,
        node_item_chain: list,
        *,
        start_frame: int,
        frame_count: int = 60,
    ) -> None:
        super().__init__()
        self._source_path = Path(source_path)
        self._node_item_chain = list(node_item_chain or [])
        self._start_frame = max(0, int(start_frame))
        self._frame_count = max(1, int(frame_count))

    def run(self) -> None:
        decoder = None
        try:
            import numpy as np

            from app.project_player import _apply_node_effect_player
            from app.video_decoder import open_decoder

            decoder = open_decoder(self._source_path)
            if decoder is None:
                self.failed.emit("preview source could not be opened")
                return
            decoder.seek_to_frame(self._start_frame)
            for offset in range(self._frame_count):
                if self.isInterruptionRequested():
                    return
                frame_idx = self._start_frame + offset
                rgb = decoder.read_rgb()
                if rgb is None:
                    return
                for node_item, masks in self._node_item_chain:
                    rgb = _apply_node_effect_player(node_item, rgb, masks or [], frame_idx)
                self.frame_ready.emit(frame_idx, np.ascontiguousarray(rgb))
        except Exception as exc:
            self.failed.emit(str(exc) or repr(exc))
        finally:
            if decoder is not None:
                try:
                    decoder.release()
                except Exception:
                    pass
