def test_register_vseeface_camera_writes_admin_batch(tmp_path, monkeypatch):
    import tools.register_vseeface_camera as tool

    monkeypatch.setattr(tool, "ROOT", tmp_path)
    monkeypatch.setattr(tool, "UNITY_CAPTURE_DIR", tmp_path / "UnityCapture")
    tool.UNITY_CAPTURE_DIR.mkdir()

    batch = tool._write_admin_batch()
    text = batch.read_text(encoding="ascii")

    assert batch.name == "register_vseeface_camera_admin.bat"
    assert "VSeeFaceCamera32bit.dll" in text
    assert "VSeeFaceCamera64bit.dll" in text
    assert "UnityCaptureName=VSeeFaceCamera" in text
    assert "pause" in text
