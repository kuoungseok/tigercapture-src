import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_media_pool_recognizes_fbx_and_emits_preview_request(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool

    QApplication.instance() or QApplication([])
    asset = tmp_path / "scooter.fbx"
    asset.write_bytes(b"Kaydara FBX Binary  \x00\x1a\x00")

    pool = MediaPool()
    try:
        assert pool.add_path(asset)
        assert pool.items() == [str(asset.resolve())]

        item = pool._list.item(0)
        assert item.data(Qt.ItemDataRole.UserRole + 2) == "3"
        assert item.data(Qt.ItemDataRole.UserRole + 8) == "support_deferred"
        assert "3D support: checked on preview/place" in item.toolTip()
        assert "3D support: checked on preview/place" in pool._item_metadata_text(item)

        requested: list[str] = []
        pool.asset_preview_requested.connect(requested.append)
        pool._on_item_double_clicked(item)

        assert requested == [str(asset.resolve())]
    finally:
        pool.deleteLater()


def test_media_pool_keeps_multiple_3d_assets_visible_when_featured(tmp_path):
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool

    QApplication.instance() or QApplication([])
    first = tmp_path / "first_prop.glb"
    second = tmp_path / "second_prop.fbx"
    first.write_bytes(b"glTF")
    second.write_bytes(b"Kaydara FBX Binary  \x00\x1a\x00")

    pool = MediaPool()
    try:
        assert pool.import_3d_paths([str(first), str(second)]) == 2
        assert pool.items() == sorted(str(p.resolve()) for p in (first, second))

        first_item = pool._find_item_for_path(first)
        second_item = pool._find_item_for_path(second)
        assert first_item is not None
        assert second_item is not None
        assert not first_item.isHidden()
        assert not second_item.isHidden()

        assert pool.select_path(second)
        assert not first_item.isHidden()
        assert not second_item.isHidden()
    finally:
        pool.deleteLater()


def test_media_pool_featured_3d_item_double_click_emits_preview_request(tmp_path):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool

    class _FeaturedDoubleClick:
        Type = QEvent.Type

        def __init__(self):
            self.accepted = False

        def type(self):
            return QEvent.Type.MouseButtonDblClick

        def button(self):
            return Qt.MouseButton.LeftButton

        def accept(self):
            self.accepted = True

    QApplication.instance() or QApplication([])
    asset = tmp_path / "featured_scooter.fbx"
    asset.write_bytes(b"Kaydara FBX Binary  \x00\x1a\x00")

    pool = MediaPool()
    try:
        assert pool.add_path(asset)
        requested: list[str] = []
        pool.asset_preview_requested.connect(requested.append)

        event = _FeaturedDoubleClick()
        assert pool.eventFilter(pool._featured_host, event) is True

        assert event.accepted is True
        assert requested == [str(asset.resolve())]
    finally:
        pool.deleteLater()


def test_media_pool_recognizes_vrm_as_avatar_target(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool

    QApplication.instance() or QApplication([])
    asset = tmp_path / "milica.vrm"
    asset.write_bytes(b"glTF")

    pool = MediaPool()
    try:
        assert pool.add_path(asset)
        item = pool._list.item(0)
        assert item.data(Qt.ItemDataRole.UserRole + 2) == "R"
        assert item.data(Qt.ItemDataRole.UserRole + 8) == "avatar_target"
        assert "VRM Avatar Target" in item.toolTip()

        requested: list[str] = []
        opened: list[str] = []
        pool.avatar_target_requested.connect(requested.append)
        pool.vtuber_studio_requested.connect(opened.append)
        pool._on_item_double_clicked(item)

        assert requested == [str(asset.resolve())]
        assert opened == [str(asset.resolve())]
    finally:
        pool.deleteLater()


def test_media_pool_recognizes_mmd_assets_and_pbx_json(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MMD_MIME_TYPE, ROLE_MMD_BADGE, MediaPool

    QApplication.instance() or QApplication([])
    model = tmp_path / "Cantarella.pbx.json"
    model.write_text("{}", encoding="utf-8")

    pool = MediaPool()
    try:
        assert pool.add_path(model)
        item = pool._list.item(0)
        mime = pool._list.mimeData([item])

        assert item.data(Qt.ItemDataRole.UserRole + 2) == "M"
        assert item.data(Qt.ItemDataRole.UserRole + 8) == "mmd_asset"
        assert item.data(ROLE_MMD_BADGE) == "MMD"
        assert "MMD asset" in item.toolTip()
        assert "MMD Asset" in pool._item_metadata_text(item)
        assert mime.hasFormat(MMD_MIME_TYPE)

        requested: list[str] = []
        pool.mmd_asset_requested.connect(requested.append)
        pool._on_item_double_clicked(item)
        assert requested == [str(model.resolve())]
    finally:
        pool.deleteLater()


def test_media_pool_hides_vmd_from_general_pool(tmp_path):
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool

    QApplication.instance() or QApplication([])
    motion = tmp_path / "flashy_dance.vmd"
    motion.write_bytes(b"Vocaloid Motion Data")

    pool = MediaPool()
    try:
        assert not pool.add_path(motion)
        assert pool.items() == []
    finally:
        pool.deleteLater()


def test_media_pool_3d_import_routes_model_asset_families_and_skips_vmd(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool

    QApplication.instance() or QApplication([])
    fbx = tmp_path / "camera_prop.fbx"
    vrm = tmp_path / "avatar.vrm"
    obj = tmp_path / "camera_prop.obj"
    usd = tmp_path / "stage.usd"
    usdz = tmp_path / "stage_pack.usdz"
    pmx = tmp_path / "mmd_actor.pmx"
    packaged = tmp_path / "packed_actor.pbx.json"
    vmd = tmp_path / "dance_motion.vmd"
    video = tmp_path / "plate.mp4"
    for path in (fbx, vrm, obj, usd, usdz, pmx, packaged, vmd, video):
        path.write_bytes(b"dummy")

    pool = MediaPool()
    try:
        added = pool.import_3d_paths([
            str(fbx),
            str(vrm),
            str(obj),
            str(usd),
            str(usdz),
            str(pmx),
            str(packaged),
            str(vmd),
            str(video),
        ])

        assert added == 7
        assert pool.items() == sorted(str(p.resolve()) for p in (fbx, vrm, obj, usd, usdz, pmx, packaged))
        kinds = {
            str(pool._list.item(i).data(Qt.ItemDataRole.UserRole)): pool._list.item(i).data(Qt.ItemDataRole.UserRole + 2)
            for i in range(pool._list.count())
        }
        assert kinds[str(fbx.resolve())] == "3"
        assert kinds[str(vrm.resolve())] == "R"
        assert kinds[str(obj.resolve())] == "3"
        assert kinds[str(usd.resolve())] == "3"
        assert kinds[str(usdz.resolve())] == "3"
        assert kinds[str(pmx.resolve())] == "M"
        assert kinds[str(packaged.resolve())] == "M"
    finally:
        pool.deleteLater()


def test_media_pool_3d_import_dialog_filter_lists_supported_asset_formats():
    from app.media_pool import THREE_D_IMPORT_FILTER

    for pattern in ("*.fbx", "*.glb", "*.gltf", "*.obj", "*.usd", "*.usdz", "*.vrm", "*.pmx", "*.pmd", "*.pbx.json"):
        assert pattern in THREE_D_IMPORT_FILTER
    assert "*.vmd" not in THREE_D_IMPORT_FILTER


def test_media_pool_context_menu_orders_3d_import_after_youtube(monkeypatch):
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool

    QApplication.instance() or QApplication([])
    labels: list[str] = []

    class _FakeMenu:
        def __init__(self, _parent=None):
            pass

        def addAction(self, label):
            labels.append(str(label))
            return object()

        def addSeparator(self):
            labels.append("---")

        def exec(self, _pos):
            return None

    monkeypatch.setattr("app.media_pool.QMenu", _FakeMenu)
    pool = MediaPool()
    try:
        pool._show_context_menu(QPoint(0, 0))
    finally:
        pool.deleteLater()

    assert labels[1:3] == [
        "Import YouTube URL as MP4",
        "Import 3D / MMD Asset...",
    ]


def test_media_pool_performance_source_flag_is_queryable_and_serializable(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool
    from app.vtuber.performance_source import PERFORMANCE_SOURCE_MIME_TYPE

    QApplication.instance() or QApplication([])
    video = tmp_path / "face_input.mp4"
    video.write_bytes(b"dummy")

    pool = MediaPool()
    try:
        assert pool.add_path(video)

        changed = pool.set_performance_source_path(video, True)
        rows = pool.media_pool_metadata()
        item = pool._list.item(0)
        mime = pool._list.mimeData([item])

        assert changed is True
        assert pool.is_performance_source_path(video)
        assert pool.performance_source_paths() == [str(video.resolve())]
        assert rows[0]["performance_source"] is True
        assert item.data(Qt.ItemDataRole.UserRole + 2) == "V"
        assert "PERF: Performance Source" in item.toolTip()
        assert "not used as Program Output background" in item.toolTip()
        assert mime.hasFormat(PERFORMANCE_SOURCE_MIME_TYPE)
    finally:
        pool.deleteLater()
