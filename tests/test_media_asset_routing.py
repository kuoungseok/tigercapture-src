import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _mime_for_paths(*paths: Path):
    from PySide6.QtCore import QMimeData, QUrl

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    return mime


def test_media_asset_routing_separates_3d_vrm_mmd_and_timeline_media(tmp_path):
    from app.media_asset_routing import (
        ar_pbr_paths_from_mime,
        mmd_paths_from_mime,
        timeline_media_paths_from_mime,
        vrm_avatar_paths_from_mime,
    )

    glb = tmp_path / "prop.glb"
    obj = tmp_path / "prop.obj"
    usd = tmp_path / "stage.usd"
    vrm = tmp_path / "avatar.vrm"
    pmx = tmp_path / "idol.pmx"
    vmd = tmp_path / "dance.vmd"
    video = tmp_path / "plate.mp4"
    audio = tmp_path / "voice.wav"
    image = tmp_path / "poster.jpg"

    mime = _mime_for_paths(glb, obj, usd, vrm, pmx, vmd, video, image, audio)

    assert ar_pbr_paths_from_mime(mime) == [glb, obj, usd]
    assert vrm_avatar_paths_from_mime(mime) == [vrm]
    assert mmd_paths_from_mime(mime) == [pmx, vmd]
    assert timeline_media_paths_from_mime(mime) == [video, image, audio]


def test_media_asset_routing_performance_source_uses_mime_or_pool_marker(tmp_path):
    from app.media_asset_routing import performance_source_paths_from_mime
    from app.vtuber.performance_source import PERFORMANCE_SOURCE_MIME_TYPE

    video = tmp_path / "face_input.mp4"
    audio = tmp_path / "voice.wav"

    marked_mime = _mime_for_paths(video, audio)
    marked_mime.setData(PERFORMANCE_SOURCE_MIME_TYPE, str(video).encode("utf-8"))

    assert performance_source_paths_from_mime(marked_mime) == [video]

    plain_mime = _mime_for_paths(video, audio)
    assert performance_source_paths_from_mime(
        plain_mime,
        lambda path: Path(path) == video,
    ) == [video]


def test_media_asset_routing_reads_internal_media_pool_drag_without_file_url(tmp_path):
    from PySide6.QtCore import QMimeData

    from app.media_asset_routing import MEDIA_POOL_ITEM_MIME_TYPE, timeline_media_paths_from_mime

    video = tmp_path / "pool_only.mp4"
    mime = QMimeData()
    mime.setData(MEDIA_POOL_ITEM_MIME_TYPE, str(video).encode("utf-8"))

    assert not mime.hasUrls()
    assert timeline_media_paths_from_mime(mime) == [video]
