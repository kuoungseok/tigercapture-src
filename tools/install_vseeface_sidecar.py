"""Install the external VSeeFace sidecar from a local zip or explicit URL."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any
from urllib.request import Request, urlopen
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INSTALL_DIR = ROOT / "external" / "tools" / "vseeface"
DEFAULT_REPORT = ROOT / "debugCapture" / "vseeface_install_report.json"
DOWNLOAD_PAGE_URL = "https://www.vseeface.icu/"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the external VSeeFace sidecar.")
    parser.add_argument("--source-zip", default="", help="Existing VSeeFace zip path.")
    parser.add_argument("--download-url", default="", help="Explicit VSeeFace zip URL to download.")
    parser.add_argument("--install-dir", default=str(DEFAULT_INSTALL_DIR))
    parser.add_argument("--out", default=str(DEFAULT_REPORT))
    args = parser.parse_args(argv)

    report = install_vseeface_sidecar(
        source_zip=Path(args.source_zip) if args.source_zip else None,
        download_url=str(args.download_url or ""),
        install_dir=Path(args.install_dir),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "status": report["status"], "out": str(out)}, ensure_ascii=False))
    return 0 if report["ok"] else 2


def install_vseeface_sidecar(
    *,
    source_zip: Path | None,
    download_url: str,
    install_dir: Path,
) -> dict[str, Any]:
    install_dir = install_dir.resolve()
    report: dict[str, Any] = {
        "schema": "tigerstudio.vtuber.vseeface_bridge.install.v1",
        "ok": False,
        "status": "not_started",
        "install_dir": str(install_dir),
        "exe": str(install_dir / "VSeeFace" / "VSeeFace.exe"),
        "source_zip": str(source_zip or ""),
        "download_url": str(download_url or ""),
        "download_page_url": DOWNLOAD_PAGE_URL,
        "downloaded_zip": "",
        "errors": [],
        "warnings": [],
        "next_action": "",
    }
    existing_exe = install_dir / "VSeeFace" / "VSeeFace.exe"
    if existing_exe.is_file():
        report.update({"ok": True, "status": "already_installed", "exe": str(existing_exe)})
        return report

    zip_path = _resolve_zip(source_zip, install_dir)
    if zip_path is None and download_url:
        zip_path = _download_zip(download_url, install_dir)
        report["downloaded_zip"] = str(zip_path)
    if zip_path is None:
        report["status"] = "zip_missing"
        report["errors"].append("vseeface_zip_missing")
        report["next_action"] = "download_vseeface_zip_or_choose_source_zip"
        return report
    if not zip_path.is_file():
        report["status"] = "zip_missing"
        report["errors"].append("source_zip_not_found")
        report["next_action"] = "choose_existing_vseeface_zip"
        return report

    try:
        exe = _extract_vseeface_zip(zip_path, install_dir)
    except zipfile.BadZipFile:
        report["status"] = "bad_zip"
        report["errors"].append("source_zip_invalid")
        report["next_action"] = "choose_valid_vseeface_zip"
        return report
    except Exception as exc:
        report["status"] = "install_failed"
        report["errors"].append(f"extract_failed:{exc}")
        report["next_action"] = "retry_install_or_choose_another_zip"
        return report

    report.update({
        "ok": exe.is_file(),
        "status": "installed" if exe.is_file() else "exe_missing_after_extract",
        "exe": str(exe),
        "source_zip": str(zip_path),
    })
    if not exe.is_file():
        report["errors"].append("vseeface_exe_missing_after_extract")
        report["next_action"] = "choose_vseeface_exe_manually"
    else:
        report["next_action"] = "select_installed_vseeface_exe"
    return report


def _resolve_zip(source_zip: Path | None, install_dir: Path) -> Path | None:
    if source_zip is not None:
        return source_zip
    candidates: list[Path] = []
    for folder in (install_dir.parent, ROOT / "debugCapture", Path.home() / "Downloads"):
        try:
            candidates.extend(folder.glob("VSeeFace*.zip"))
        except Exception:
            continue
    candidates = [item for item in candidates if item.is_file()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[0]


def _download_zip(download_url: str, install_dir: Path) -> Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    out = install_dir / "VSeeFace_download.zip"
    request = Request(str(download_url), headers={"User-Agent": "TigerCapture VSeeFace Sidecar Installer"})
    with urlopen(request, timeout=120) as response:
        with out.open("wb") as fh:
            shutil.copyfileobj(response, fh)
    return out


def _extract_vseeface_zip(zip_path: Path, install_dir: Path) -> Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vseeface_extract_", dir=str(install_dir)) as temp_text:
        temp_dir = Path(temp_text)
        with zipfile.ZipFile(zip_path, "r") as archive:
            _safe_extract_all(archive, temp_dir)
        exe = _find_exe(temp_dir)
        if exe is None:
            return install_dir / "VSeeFace" / "VSeeFace.exe"
        source_root = exe.parent
        target_root = install_dir / "VSeeFace"
        if target_root.exists():
            _assert_child_path(target_root, install_dir)
            shutil.rmtree(target_root)
        shutil.copytree(source_root, target_root)
    return install_dir / "VSeeFace" / "VSeeFace.exe"


def _safe_extract_all(archive: zipfile.ZipFile, target_dir: Path) -> None:
    target_root = target_dir.resolve()
    for member in archive.infolist():
        member_target = (target_root / member.filename).resolve()
        _assert_child_path(member_target, target_root)
        archive.extract(member, target_root)


def _assert_child_path(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"path escapes install directory: {resolved_path}")


def _find_exe(root: Path) -> Path | None:
    for candidate in root.rglob("VSeeFace.exe"):
        if candidate.is_file():
            return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
