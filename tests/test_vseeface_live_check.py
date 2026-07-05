def test_inspect_vmc_symbols_reports_receiver_runtime_api(tmp_path):
    from tools.vseeface_live_check import _inspect_vmc_symbols

    assembly = tmp_path / "external" / "tools" / "vseeface" / "VSeeFace" / "VSeeFace_Data" / "Managed" / "Assembly-CSharp.dll"
    assembly.parent.mkdir(parents=True)
    assembly.write_bytes(
        b"VMCReceiverManager\0SetVMCEnabled\0SetVMCPort\0EVMC4U.ExternalReceiver\0"
        + "/VMC/Ext/Bone/Pos".encode("utf-16le")
        + b"\0"
        + "/VMC/Ext/Blend/Val".encode("utf-16le")
    )

    report = _inspect_vmc_symbols(tmp_path)

    assert report["exists"] is True
    assert report["runtime_receiver_api_present"] is True
    assert report["missing_required"] == []


def test_inspect_vmc_symbols_reports_missing_assembly(tmp_path):
    from tools.vseeface_live_check import _inspect_vmc_symbols

    report = _inspect_vmc_symbols(tmp_path)

    assert report["exists"] is False
    assert report["runtime_receiver_api_present"] is False


def test_read_settings_marks_ip_port_as_openseeface_tracking(monkeypatch, tmp_path):
    from pathlib import Path

    from tools.vseeface_live_check import _read_settings

    settings = tmp_path / "AppData" / "LocalLow" / "Emiliana_vt" / "VSeeFace" / "settings.ini"
    settings.parent.mkdir(parents=True)
    settings.write_text("[OpenSeeDemo]\nIP=127.0.0.1\nPort=39540\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    report = _read_settings()

    assert report["values"]["IP"] == "127.0.0.1"
    assert report["openseeface_tracking_endpoint"]["port"] == "39540"
    assert "not the VMC receiver" in report["openseeface_tracking_endpoint"]["note"]
