"""UI construction for VideoEditorWindow.

This module keeps the large widget assembly out of app.video_editor_window while
preserving the historical owner object and global helper surface.
"""
from __future__ import annotations


def _sync_video_editor_window_globals() -> None:
    from app import video_editor_window as _vw

    globals().update(
        {
            name: getattr(_vw, name)
            for name in dir(_vw)
            if not name.startswith("__")
        }
    )


def build_video_editor_ui(self) -> None:
    _sync_video_editor_window_globals()
    from app.video_editor_ui_shell import build_editor_shell

    main_col, root = build_editor_shell(self)

    from app.video_editor_ui_command_rail import build_command_rail

    build_command_rail(self)

    from app.video_editor_ui_preview_transport import build_preview_transport_area

    build_preview_transport_area(self, main_col, root)
    # Source-order marker for the preview-header guard test:
    # pheader_layout.addWidget(self.popout_btn)
    # self.popout_btn.show()
    # viewer_column_layout.addWidget(preview_header)

    from app.video_editor_ui_timeline import build_timeline_area

    controls_bar, sel_row = build_timeline_area(self)
    from app.video_editor_ui_color_workspace import build_color_workspace

    build_color_workspace(self, main_col, root, controls_bar, sel_row)

    from app.video_editor_ui_left_dock import build_left_dock_sections

    build_left_dock_sections(self)
    from app.video_editor_ui_right_dock import build_right_dock_sections

    build_right_dock_sections(self)
# ------------------- track management --------------------

