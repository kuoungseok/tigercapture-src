from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_capture_to_studio_policy_defaults_to_blocked(monkeypatch):
    from app.launcher_studio_policy import capture_to_studio_enabled

    for name in (
        "TIGERCAPTURE_CAPTURE_TO_STUDIO",
        "TIGERCAPTURE_ALLOW_STUDIO_ENTRY",
        "TIGERSTUDIO_BUNDLED_STUDIO_ENTRY",
    ):
        monkeypatch.delenv(name, raising=False)

    assert capture_to_studio_enabled() is False


def test_capture_to_studio_policy_allows_explicit_bundle_opt_in(monkeypatch):
    from app.launcher_studio_policy import capture_to_studio_enabled

    for name in (
        "TIGERCAPTURE_CAPTURE_TO_STUDIO",
        "TIGERCAPTURE_ALLOW_STUDIO_ENTRY",
        "TIGERSTUDIO_BUNDLED_STUDIO_ENTRY",
    ):
        monkeypatch.delenv("TIGERCAPTURE_CAPTURE_TO_STUDIO", raising=False)
        monkeypatch.delenv("TIGERCAPTURE_ALLOW_STUDIO_ENTRY", raising=False)
        monkeypatch.delenv("TIGERSTUDIO_BUNDLED_STUDIO_ENTRY", raising=False)
        monkeypatch.setenv(name, "1")
        assert capture_to_studio_enabled() is True


def test_main_studio_flag_is_consumed_without_losing_payload_args():
    import main

    argv = ["main.py", "--studio", "clip.mp4"]
    assert main._consume_studio_flag(argv) is True
    assert argv == ["main.py", "clip.mp4"]

    argv = ["main.py", "--tiger-studio"]
    assert main._consume_studio_flag(argv) is True
    assert argv == ["main.py"]

    argv = ["main.py", "clip.mp4"]
    assert main._consume_studio_flag(argv) is False
    assert argv == ["main.py", "clip.mp4"]


def test_studio_entrypoint_arg_parser_distinguishes_projects_from_media():
    from studio_main import _consume_source_arg

    assert _consume_source_arg(["studio_main.py", "project.tgp"]) == Path("project.tgp")
    assert _consume_source_arg(["studio_main.py", "clip.mp4"]) == Path("clip.mp4")
    assert _consume_source_arg(["studio_main.py", "--flag"]) is None


def test_pyinstaller_spec_builds_capture_and_studio_executables():
    text = (ROOT / "TigerCapture.spec").read_text(encoding="utf-8")

    assert "['main.py', 'studio_main.py']" in text
    assert "name='TigerCapture'" in text
    assert "studio_exe = EXE(" in text
    assert "name='TigerStudio'" in text
    assert "COLLECT(" in text and "studio_exe" in text


def test_windows_launcher_routes_capture_and_studio_modes():
    text = (ROOT / "tools" / "windows_launcher" / "TigerCaptureLauncher.cs").read_text(encoding="utf-8")

    assert 'studioMode ? "studio_main.py" : "main.py"' in text
    assert 'Path.Combine(root, "dist", "TigerCapture", "TigerStudio.exe")' in text
    assert 'studioMode ? "--studio "' in text
    assert 'Path.GetFileNameWithoutExtension(Application.ExecutablePath)' in text


def test_build_and_installer_scripts_expose_tiger_studio_entrypoint():
    build_text = (ROOT / "build.ps1").read_text(encoding="utf-8")
    build_requirements = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
    nsis_text = (ROOT / "installer.nsi").read_text(encoding="utf-8")
    inno_text = (ROOT / "installer.iss").read_text(encoding="utf-8")

    assert "TigerStudio.exe" in build_text
    assert "dist\\TigerCapture\\TigerStudio.exe" in build_text
    assert "requirements-build.txt" in build_text
    assert "TigerCapture-InnoSetup-*.exe" in build_text
    assert "pyinstaller" in build_requirements.lower()
    assert "$INSTDIR\\TigerStudio.exe" in nsis_text
    assert '#define MyStudioExeName "TigerStudio.exe"' in inno_text
    assert "TigerCapture-InnoSetup-" in inno_text
    assert 'Filename: "{app}\\{#MyStudioExeName}"' in inno_text
