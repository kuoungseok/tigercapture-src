def test_virtual_camera_probe_reports_dependency_error(monkeypatch):
    import builtins

    from app.vtuber.virtual_camera_probe import probe_virtual_camera_frames

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cv2":
            raise ImportError("cv2 unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    report = probe_virtual_camera_frames(max_index=0)

    assert report["ok"] is False
    assert report["schema"] == "tigerstudio.vtuber.virtual_camera_probe.v1"
    assert report["errors"][0].startswith("opencv_capture_unavailable")
    assert "ffmpeg_camera" in report
