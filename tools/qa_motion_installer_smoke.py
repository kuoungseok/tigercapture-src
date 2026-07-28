from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "debugCapture" / "motion_designer" / "installer_smoke"


def _hidden_kwargs() -> dict:
    if os.name != "nt":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _process_ids(root_pid: int) -> set[int]:
    ids = {int(root_pid)}
    try:
        import psutil

        process = psutil.Process(root_pid)
        ids.update(child.pid for child in process.children(recursive=True))
    except Exception:
        pass
    return ids


def _visible_windows(process_ids: set[int]) -> list[dict[str, object]]:
    if os.name != "nt":
        return []
    user32 = ctypes.windll.user32
    rows: list[dict[str, object]] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def callback(hwnd, _lparam):
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) not in process_ids or not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        rows.append({"hwnd": int(hwnd), "pid": int(pid.value), "title": title.value})
        return True

    user32.EnumWindows(callback, 0)
    return rows


def _close_windows(rows: list[dict[str, object]]) -> None:
    if os.name != "nt":
        return
    wm_close = 0x0010
    for row in rows:
        ctypes.windll.user32.PostMessageW(int(row["hwnd"]), wm_close, 0, 0)


def _latest_installer() -> Path:
    candidates = sorted(
        (ROOT / "installer_output").glob("TigerCapture-InnoSetup-*.exe"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No current Inno Setup installer found")
    return candidates[0].resolve()


def _latest_packaging_input() -> tuple[float, str]:
    candidates = [
        *ROOT.glob("*.py"),
        *ROOT.glob("*.spec"),
        *ROOT.glob("*.iss"),
        ROOT / "build.ps1",
        *ROOT.joinpath("app").rglob("*.py"),
    ]
    files = [path for path in candidates if path.is_file()]
    if not files:
        return 0.0, ""
    latest = max(files, key=lambda path: path.stat().st_mtime)
    return latest.stat().st_mtime, str(latest.resolve())


def _load_frozen_runtime_identity(
    report_path: Path | None,
) -> tuple[dict[str, object], float]:
    if report_path is None:
        return {}, 0.0
    resolved = report_path.expanduser().resolve(strict=False)
    if not resolved.is_file():
        return {}, 0.0
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    identity = payload.get("runtime_identity")
    if not isinstance(identity, dict):
        return {}, resolved.stat().st_mtime
    return identity, resolved.stat().st_mtime


def run(
    installer: Path,
    output_dir: Path,
    *,
    frozen_runtime_report: Path | None = None,
) -> dict:
    if os.name != "nt":
        raise RuntimeError("Motion installer smoke requires Windows")
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    latest_source_mtime, latest_source_path = _latest_packaging_input()
    installer_mtime = installer.stat().st_mtime
    frozen_identity, frozen_report_mtime = _load_frozen_runtime_identity(
        frozen_runtime_report
    )
    expected_studio_size = int(
        frozen_identity.get("executable_size_bytes") or 0
    )
    expected_studio_sha256 = str(
        frozen_identity.get("executable_sha256") or ""
    ).lower()
    provenance_requested = frozen_runtime_report is not None
    provenance_available = bool(
        frozen_identity.get("frozen")
        and expected_studio_size > 0
        and len(expected_studio_sha256) == 64
    )
    freshness_reference_mtime = (
        frozen_report_mtime if provenance_requested else latest_source_mtime
    )
    installer_current_for_source = installer_mtime >= latest_source_mtime
    installer_current_for_frozen_report = (
        provenance_requested
        and freshness_reference_mtime > 0.0
        and installer_mtime >= freshness_reference_mtime
    )
    installer_current = (
        freshness_reference_mtime > 0.0
        and installer_mtime >= freshness_reference_mtime
    )
    with tempfile.TemporaryDirectory(prefix="TigerStudioInstallerSmoke-") as temporary:
        install_dir = Path(temporary) / "TigerCapture"
        install = subprocess.run(
            [
                str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                f"/DIR={install_dir}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
            check=False,
            **_hidden_kwargs(),
        )
        studio = install_dir / "TigerStudio.exe"
        capture = install_dir / "TigerCapture.exe"
        installed_files = [path for path in install_dir.rglob("*") if path.is_file()]
        launch_env = dict(os.environ)
        launch_env.update({"QT_OPENGL": "desktop", "QT_QPA_PLATFORM": "windows"})
        process = None
        windows: list[dict[str, object]] = []
        launch_error = ""
        if install.returncode == 0 and studio.is_file():
            try:
                process = subprocess.Popen(
                    [str(studio)], cwd=str(install_dir), env=launch_env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    **_hidden_kwargs(),
                )
                deadline = time.monotonic() + 60.0
                while time.monotonic() < deadline and process.poll() is None:
                    windows = _visible_windows(_process_ids(process.pid))
                    if any(str(row.get("title") or "").strip() for row in windows):
                        break
                    time.sleep(0.25)
            except Exception as exc:
                launch_error = f"{type(exc).__name__}: {exc}"
        live_process = bool(process is not None and process.poll() is None)
        titled_windows = [row for row in windows if str(row.get("title") or "").strip()]
        capture_present = capture.is_file()
        studio_present = studio.is_file()
        installed_studio_size = studio.stat().st_size if studio_present else 0
        installed_studio_sha256 = _sha256(studio) if studio_present else ""
        frozen_provenance_matches = bool(
            provenance_available
            and installed_studio_size == expected_studio_size
            and installed_studio_sha256 == expected_studio_sha256
        )
        provenance_ok = (
            frozen_provenance_matches
            if provenance_requested
            else True
        )
        if process is not None:
            _close_windows(windows)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        uninstall = install_dir / "unins000.exe"
        uninstall_returncode = None
        if uninstall.is_file():
            uninstalled = subprocess.run(
                [str(uninstall), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120, check=False,
                **_hidden_kwargs(),
            )
            uninstall_returncode = uninstalled.returncode
        ok = bool(
            installer_current and install.returncode == 0 and studio_present and capture_present
            and installed_files and live_process and titled_windows and not launch_error
            and uninstall_returncode in {0, None} and provenance_ok
        )
        report = {
            "ok": ok,
            "generated_at": generated_at,
            "installer_path": str(installer),
            "installer_size": installer.stat().st_size,
            "installer_sha256": _sha256(installer),
            "installer_mtime_utc": datetime.fromtimestamp(installer_mtime, timezone.utc).isoformat(),
            "latest_packaging_input": latest_source_path,
            "latest_packaging_input_mtime_utc": datetime.fromtimestamp(
                latest_source_mtime, timezone.utc,
            ).isoformat(),
            "installer_current_for_source": installer_current_for_source,
            "installer_current_for_frozen_report": (
                installer_current_for_frozen_report
            ),
            "installer_freshness_ok": installer_current,
            "freshness_reference": (
                str(frozen_runtime_report.resolve(strict=False))
                if frozen_runtime_report is not None
                else latest_source_path
            ),
            "install_returncode": install.returncode,
            "install_output_tail": install.stdout[-4000:],
            "temporary_install_root": str(install_dir),
            "installed_file_count": len(installed_files),
            "capture_executable_present": capture_present,
            "studio_executable_present": studio_present,
            "installed_studio_size_bytes": installed_studio_size,
            "installed_studio_sha256": installed_studio_sha256,
            "expected_studio_size_bytes": expected_studio_size,
            "expected_studio_sha256": expected_studio_sha256,
            "frozen_provenance_requested": provenance_requested,
            "frozen_provenance_available": provenance_available,
            "frozen_provenance_matches": frozen_provenance_matches,
            "studio_process_live_at_probe": live_process,
            "studio_windows": titled_windows,
            "launch_error": launch_error,
            "uninstall_returncode": uninstall_returncode,
        }
    report_path = output_dir / "report.json"
    report["temporary_install_removed"] = not Path(report["temporary_install_root"]).exists()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path.resolve())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Install and launch-smoke the current Tiger Studio installer")
    parser.add_argument("--installer", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frozen-runtime-report", type=Path, default=None)
    args = parser.parse_args()
    installer = args.installer.resolve() if args.installer else _latest_installer()
    report = run(
        installer,
        args.output.resolve(),
        frozen_runtime_report=args.frozen_runtime_report,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
