import os
from types import SimpleNamespace


def test_media_pool_vrm_import_is_avatar_target_not_track_media(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool, VRM_AVATAR_MIME_TYPE

    QApplication.instance() or QApplication([])
    vrm = tmp_path / "avatar.vrm"
    vrm.write_bytes(b"not-a-real-vrm-for-media-pool-ui")
    pool = MediaPool()

    assert pool.add_path(vrm) is True
    item = pool._list.item(0)
    rows = pool.media_pool_metadata()

    assert item.data(Qt.ItemDataRole.UserRole + 2) == "R"
    assert rows[0]["kind"] == "R"
    assert rows[0]["avatar_target"] is True
    assert rows[0]["vrm_avatar"] is True
    assert "VRM Avatar Target" in item.toolTip()

    mime = pool._list.mimeData([item])
    assert mime.hasFormat(VRM_AVATAR_MIME_TYPE)
    assert not mime.hasUrls()


def test_media_pool_vrm_double_click_selects_avatar_target_and_studio(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool

    QApplication.instance() or QApplication([])
    vrm = tmp_path / "avatar.vrm"
    vrm.write_bytes(b"not-a-real-vrm-for-media-pool-ui")
    pool = MediaPool()
    assert pool.add_path(vrm) is True
    item = pool._list.item(0)
    seen: list[tuple[str, str]] = []
    pool.avatar_target_requested.connect(lambda path: seen.append(("avatar", path)))
    pool.vtuber_studio_requested.connect(lambda path: seen.append(("studio", path)))

    pool._on_item_double_clicked(item)

    assert seen == [("avatar", str(vrm.resolve())), ("studio", str(vrm.resolve()))]


def test_video_editor_vrm_media_selection_persists_shared_avatar_target(tmp_path):
    from app.video_editor_window import VideoEditorWindow

    vrm = tmp_path / "avatar.vrm"
    vrm.write_bytes(b"not-a-real-vrm-for-settings-flow")
    saved: list[dict] = []
    messages: list[str] = []
    changes: list[str] = []
    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    editor._project_settings = {}
    editor._player = SimpleNamespace(set_project_settings=lambda settings: saved.append(dict(settings)))
    editor._vtuber_studio_window = None
    editor._flash_status = lambda msg: messages.append(msg)
    editor._register_change = lambda label="": changes.append(label)

    VideoEditorWindow._use_vrm_media_as_avatar_target(editor, str(vrm))

    assert editor._project_settings["vseeface_bridge"]["avatar_vrm"] == str(vrm)
    assert editor._project_settings["vtuber_studio"]["avatar_target_id"] == "vrm:vseeface_bridge"
    assert saved[-1]["vseeface_bridge"]["avatar_vrm"] == str(vrm)
    assert changes == ["Select VRM avatar target"]
    assert "VRM Avatar Target selected" in messages[-1]


def test_video_editor_routes_vrm_drop_away_from_ar_pbr_preview(tmp_path):
    from PySide6.QtCore import QMimeData, QUrl

    from app.video_editor_window import VideoEditorWindow

    vrm = tmp_path / "avatar.vrm"
    vrm.write_bytes(b"not-a-real-vrm-for-drop-routing")
    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(vrm))])

    assert VideoEditorWindow._vrm_avatar_paths_from_mime(editor, mime) == [vrm]
    assert VideoEditorWindow._ar_pbr_paths_from_mime(editor, mime) == []
