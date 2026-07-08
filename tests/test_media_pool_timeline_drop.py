import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_media_pool_video_item_mime_contains_file_url(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool

    QApplication.instance() or QApplication([])
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not-a-real-video")

    pool = MediaPool()
    try:
        assert pool.add_path(video)
        item = pool._list.item(0)
        mime = pool._list.mimeData([item])

        assert item.data(Qt.ItemDataRole.UserRole + 2) == "V"
        assert mime.hasUrls()
        assert [Path(url.toLocalFile()) for url in mime.urls()] == [video.resolve()]
    finally:
        pool.deleteLater()


def test_media_pool_featured_item_can_start_file_drag(tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool

    QApplication.instance() or QApplication([])
    video = tmp_path / "featured_clip.mp4"
    video.write_bytes(b"not-a-real-video")
    drags = []

    class _FakeDrag:
        def __init__(self, source):
            self.source = source
            self.mime = None
            self.actions = None
            drags.append(self)

        def setMimeData(self, mime):
            self.mime = mime

        def setPixmap(self, pixmap):
            self.pixmap = pixmap

        def setHotSpot(self, point):
            self.hotspot = point

        def exec(self, actions):
            self.actions = actions
            return Qt.DropAction.CopyAction

    monkeypatch.setattr("app.media_pool.QDrag", _FakeDrag)

    pool = MediaPool()
    try:
        assert pool.add_path(video)
        assert pool.select_path(video)
        item = pool._find_item_for_path(video)
        assert item is not None
        assert item.isHidden()

        assert pool._begin_featured_drag() is True

        assert len(drags) == 1
        assert drags[0].source is pool._list
        assert drags[0].actions == Qt.DropAction.CopyAction
        assert drags[0].mime is not None
        assert drags[0].mime.hasUrls()
        assert [Path(url.toLocalFile()) for url in drags[0].mime.urls()] == [video.resolve()]
    finally:
        pool.deleteLater()


class _FakeTimelineDropEvent:
    def __init__(self, event_type, mime, x=120.0):
        self._event_type = event_type
        self._mime = mime
        self._x = float(x)
        self.accepted = False

    def type(self):
        return self._event_type

    def mimeData(self):
        return self._mime

    def position(self):
        return SimpleNamespace(x=lambda: self._x)

    def acceptProposedAction(self):
        self.accepted = True


class _FakeTrackRowDropEvent:
    def __init__(self, mime, point):
        self._mime = mime
        self._point = point
        self.accepted = False
        self.ignored = False

    def mimeData(self):
        return self._mime

    def position(self):
        point = self._point
        return SimpleNamespace(toPoint=lambda: point, x=lambda: float(point.x()))

    def acceptProposedAction(self):
        self.accepted = True
        self.ignored = False

    def ignore(self):
        self.ignored = True


def test_video_editor_tracks_host_accepts_media_pool_video_drop(tmp_path):
    from PySide6.QtCore import QEvent, QMimeData, QUrl

    from app.video_editor_window import VideoEditorWindow

    video = tmp_path / "pool_clip.mp4"
    video.write_bytes(b"not-a-real-video")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(video))])

    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    host = object()
    editor._tracks_host = host
    editor._performance_source_paths_from_mime = lambda _mime: []
    editor._mmd_paths_from_mime = lambda _mime: []
    added: list[Path] = []
    editor._add_track_with_source = lambda path: added.append(Path(path))
    editor._add_audio_track_with_source = lambda path, *, open_editor=False: None

    drag = _FakeTimelineDropEvent(QEvent.Type.DragEnter, mime)
    assert VideoEditorWindow.eventFilter(editor, host, drag) is True
    assert drag.accepted is True

    move = _FakeTimelineDropEvent(QEvent.Type.DragMove, mime)
    assert VideoEditorWindow.eventFilter(editor, host, move) is True
    assert move.accepted is True

    drop = _FakeTimelineDropEvent(QEvent.Type.Drop, mime)
    assert VideoEditorWindow.eventFilter(editor, host, drop) is True
    assert drop.accepted is True
    assert added == [video]


def test_video_editor_tracks_viewport_accepts_media_pool_video_drop(tmp_path):
    from PySide6.QtCore import QEvent, QMimeData, QUrl

    from app.video_editor_window import VideoEditorWindow

    video = tmp_path / "viewport_pool_clip.mp4"
    video.write_bytes(b"not-a-real-video")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(video))])

    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    viewport = object()
    editor._tracks_host = object()
    editor._tracks_scroll = SimpleNamespace(viewport=lambda: viewport)
    editor._performance_source_paths_from_mime = lambda _mime: []
    editor._mmd_paths_from_mime = lambda _mime: []
    added: list[Path] = []
    editor._add_track_with_source = lambda path: added.append(Path(path))
    editor._add_audio_track_with_source = lambda path, *, open_editor=False: None

    move = _FakeTimelineDropEvent(QEvent.Type.DragMove, mime)
    assert VideoEditorWindow.eventFilter(editor, viewport, move) is True
    assert move.accepted is True

    drop = _FakeTimelineDropEvent(QEvent.Type.Drop, mime)
    assert VideoEditorWindow.eventFilter(editor, viewport, drop) is True
    assert drop.accepted is True
    assert added == [video]


def test_video_track_row_accepts_and_emits_ar_pbr_asset_drop(tmp_path):
    from PySide6.QtCore import QMimeData, QPoint, QUrl
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import TrackRow, VideoTrack

    QApplication.instance() or QApplication([])
    asset = tmp_path / "prop.fbx"
    asset.write_bytes(b"Kaydara FBX Binary  \x00\x1a\x00")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(asset))])

    row = TrackRow(VideoTrack(id=7, duration_ms=10_000))
    row.set_px_per_sec(100.0)
    dropped: list[tuple[Path, int]] = []
    row.ar_pbr_asset_dropped.connect(lambda path, ms: dropped.append((Path(path), int(ms))))
    try:
        drag = _FakeTrackRowDropEvent(mime, QPoint(row.MARGIN + 250, row.LABEL_H + 4))
        row.dragEnterEvent(drag)
        assert drag.accepted is True
        assert row._drop_guide_text(mime) == "3D"

        drop = _FakeTrackRowDropEvent(mime, QPoint(row.MARGIN + 250, row.LABEL_H + 4))
        row.dropEvent(drop)

        assert drop.accepted is True
        assert dropped == [(asset, 2500)]
    finally:
        row.deleteLater()


def test_video_editor_tracks_host_accepts_ar_pbr_asset_drop(tmp_path):
    from PySide6.QtCore import QEvent, QMimeData, QUrl

    from app.video_editor_window import VideoEditorWindow

    asset = tmp_path / "timeline_prop.glb"
    asset.write_bytes(b"glTF")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(asset))])

    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    host = object()
    editor._tracks_host = host
    editor._px_per_sec = 100.0
    editor._timeline_content_margin = lambda: 180
    editor._performance_source_paths_from_mime = lambda _mime: []
    editor._mmd_paths_from_mime = lambda _mime: []
    editor._timeline_media_paths_from_mime = lambda _mime: []
    placed: list[tuple[Path, tuple[float, float] | None, int | None]] = []
    editor._add_ar_pbr_asset_to_preview = (
        lambda path, *, image_point=None, start_ms=None:
        placed.append((Path(path), image_point, start_ms))
    )

    drag = _FakeTimelineDropEvent(QEvent.Type.DragEnter, mime, x=430.0)
    assert VideoEditorWindow.eventFilter(editor, host, drag) is True
    assert drag.accepted is True

    drop = _FakeTimelineDropEvent(QEvent.Type.Drop, mime, x=430.0)
    assert VideoEditorWindow.eventFilter(editor, host, drop) is True
    assert drop.accepted is True
    assert placed == [(asset, (0.5, 0.62), 2500)]


def test_video_editor_ar_pbr_drop_creates_visible_lane_row(tmp_path):
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

    from app.video_editor_window import VideoEditorWindow

    QApplication.instance() or QApplication([])
    asset = tmp_path / "placed_prop.glb"
    asset.write_bytes(b"glTF")

    host = QWidget()
    layout = QVBoxLayout(host)
    ruler = QWidget(host)
    tail = QWidget(host)
    layout.addWidget(ruler)
    layout.addWidget(tail)

    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    editor._ar_pbr_tracks = []
    editor._ar_pbr_lane_rows = []
    editor._next_ar_pbr_id = 1
    editor._selected_ar_pbr_track_id = ""
    editor._ar_pbr_gizmo_visible_track_id = "stale"
    editor._px_per_sec = 100.0
    editor._tracks_layout = layout
    editor._timeline_ruler = ruler
    editor._tracks_host = host
    editor._media_pool = None
    editor._workbench_panel = None
    editor._drawing_canvas = QWidget()
    editor._player = SimpleNamespace(
        position=lambda: 0,
        duration=lambda: 20_000,
        refresh_current_frame=lambda: None,
    )
    editor._promote_ar_pbr_track_to_scene_anchor = lambda track, *, reason="": False
    editor._sync_ar_pbr_tracks_to_player = lambda: None
    editor._refresh_preview_canvas_interaction_hook = lambda: None
    editor._refresh_player_tracks = lambda: None
    editor._register_change = lambda _label: None
    editor._flash_status = lambda _text: None

    try:
        track = VideoEditorWindow._add_ar_pbr_asset_to_preview(
            editor,
            asset,
            image_point=(0.5, 0.62),
            start_ms=2500,
        )

        assert track is not None
        assert len(editor._ar_pbr_tracks) == 1
        assert len(editor._ar_pbr_lane_rows) == 1
        row = editor._ar_pbr_lane_rows[0]
        assert row.track is track
        assert layout.indexOf(row) >= 0
        assert track["start_ms"] == 2500
        assert track["end_ms"] > track["start_ms"]
        assert editor._selected_ar_pbr_track_id == track["id"]
        assert editor._ar_pbr_gizmo_visible_track_id == ""
    finally:
        host.deleteLater()


def test_video_editor_ar_pbr_gizmo_projects_rotated_local_axes():
    from app.video_editor_window import VideoEditorWindow

    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    editor._ar_pbr_gizmo_drag = None
    track = {
        "id": "ar_pbr_gizmo",
        "occlusion": False,
        "placement": {"image_point": [0.5, 0.5]},
        "transform": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        },
        "render": {
            "lighting": {
                "depth_edge_glow_enabled": False,
                "depth_edge_glow_strength": 0.12,
                "depth_edge_glow_radius_px": 3.0,
                "depth_edge_glow_color": [0.1, 0.2, 0.3],
            }
        },
    }

    base = VideoEditorWindow._ar_pbr_gizmo_geometry(editor, track, 1000, 800)
    base_x = base["axes"]["x"]["vec"]

    track["transform"]["rotation"] = [0.0, 0.0, 90.0]
    rotated = VideoEditorWindow._ar_pbr_gizmo_geometry(editor, track, 1000, 800)
    rotated_x = rotated["axes"]["x"]["vec"]

    assert base_x[0] > 0.95
    assert abs(base_x[1]) < 0.05
    assert abs(rotated_x[0]) < 0.08
    assert rotated_x[1] < -0.95
    assert all(len(rotated["rings"][axis]) >= 36 for axis in ("x", "y", "z"))


def test_video_editor_ar_pbr_gizmo_hit_test_uses_visible_3d_handles():
    from app.video_editor_window import VideoEditorWindow

    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    editor._ar_pbr_gizmo_drag = None
    editor._selected_ar_pbr_track_id = "ar_pbr_gizmo"
    editor._ar_pbr_gizmo_visible_track_id = "ar_pbr_gizmo"
    track = {
        "id": "ar_pbr_gizmo",
        "placement": {"image_point": [0.5, 0.5]},
        "transform": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [18.0, 28.0, 12.0],
            "scale": [1.0, 1.0, 1.0],
        },
    }
    editor._ar_pbr_active_tracks_at_playhead = lambda: [track]
    canvas_w = 1000
    canvas_h = 800
    geom = VideoEditorWindow._ar_pbr_gizmo_geometry(editor, track, canvas_w, canvas_h)

    x_end = geom["axes"]["x"]["end"]
    editor._ar_pbr_gizmo_visible_track_id = ""
    hit_track, mode = VideoEditorWindow._ar_pbr_gizmo_hit_test(
        editor,
        x_end[0] / canvas_w,
        x_end[1] / canvas_h,
        canvas_w,
        canvas_h,
    )
    assert hit_track is None
    assert mode == ""

    editor._ar_pbr_gizmo_visible_track_id = "ar_pbr_gizmo"
    hit_track, mode = VideoEditorWindow._ar_pbr_gizmo_hit_test(
        editor,
        x_end[0] / canvas_w,
        x_end[1] / canvas_h,
        canvas_w,
        canvas_h,
    )
    assert hit_track is track
    assert mode == "move_x"

    x_scale = geom["axes"]["x"]["scale"]
    hit_track, mode = VideoEditorWindow._ar_pbr_gizmo_hit_test(
        editor,
        x_scale[0] / canvas_w,
        x_scale[1] / canvas_h,
        canvas_w,
        canvas_h,
    )
    assert hit_track is track
    assert mode == "scale_x"

    ring_hit = None
    for point in geom["rings"]["z"]:
        hit_track, mode = VideoEditorWindow._ar_pbr_gizmo_hit_test(
            editor,
            point[0] / canvas_w,
            point[1] / canvas_h,
            canvas_w,
            canvas_h,
        )
        if hit_track is track and mode == "rotate_z":
            ring_hit = mode
            break
    assert ring_hit == "rotate_z"


def test_video_editor_ar_pbr_gizmo_shows_only_after_viewer_object_click():
    from PySide6.QtCore import Qt

    from app.video_editor_window import VideoEditorWindow

    class _Canvas:
        def __init__(self):
            self._cursor = None
            self.update_count = 0

        def width(self):
            return 1000

        def height(self):
            return 800

        def setCursor(self, cursor):
            self._cursor = cursor

        def update(self):
            self.update_count += 1

    class _Event:
        def button(self):
            return Qt.MouseButton.LeftButton

    track = {
        "id": "ar_pbr_gizmo",
        "occlusion": False,
        "placement": {"image_point": [0.5, 0.5]},
        "transform": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        },
        "render": {
            "lighting": {
                "depth_edge_glow_enabled": False,
                "depth_edge_glow_strength": 0.12,
                "depth_edge_glow_radius_px": 3.0,
                "depth_edge_glow_color": [0.1, 0.2, 0.3],
            }
        },
    }
    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    editor._ar_pbr_tracks = [track]
    editor._ar_pbr_lane_rows = []
    editor._selected_ar_pbr_track_id = track["id"]
    editor._ar_pbr_gizmo_visible_track_id = ""
    editor._ar_pbr_gizmo_drag = None
    editor._preview_popout = None
    editor._ar_pbr_active_tracks_at_playhead = lambda: [track]
    editor._refresh_ar_pbr_preview_after_gizmo_change = lambda: None

    canvas = _Canvas()
    event = _Event()

    assert VideoEditorWindow._ar_pbr_gizmo_visible_track(editor) is None

    handled = VideoEditorWindow._ar_pbr_gizmo_interaction_for_canvas(
        editor,
        canvas,
        "press",
        0.5,
        0.5,
        event,
    )
    assert handled is True
    assert editor._selected_ar_pbr_track_id == track["id"]
    assert editor._ar_pbr_gizmo_visible_track_id == track["id"]
    assert isinstance(editor._ar_pbr_gizmo_drag, dict)
    assert track["occlusion"] is True
    assert track["render"]["lighting"]["depth_edge_glow_enabled"] is True
    assert track["render"]["lighting"]["depth_edge_glow_strength"] >= 0.65
    assert track["render"]["lighting"]["depth_edge_glow_radius_px"] >= 7.0

    handled = VideoEditorWindow._ar_pbr_gizmo_interaction_for_canvas(
        editor,
        canvas,
        "release",
        0.5,
        0.5,
        event,
    )
    assert handled is True
    assert editor._ar_pbr_gizmo_drag is None
    assert track["occlusion"] is False
    assert track["render"]["lighting"]["depth_edge_glow_enabled"] is False
    assert track["render"]["lighting"]["depth_edge_glow_strength"] == 0.12
    assert track["render"]["lighting"]["depth_edge_glow_radius_px"] == 3.0
    assert track["render"]["lighting"]["depth_edge_glow_color"] == [0.1, 0.2, 0.3]

    handled = VideoEditorWindow._ar_pbr_gizmo_interaction_for_canvas(
        editor,
        canvas,
        "press",
        0.05,
        0.05,
        event,
    )
    assert handled is True
    assert editor._selected_ar_pbr_track_id == track["id"]
    assert editor._ar_pbr_gizmo_visible_track_id == ""
