"""Separate updater process for staged TigerCapture update plans.

This script is intentionally standalone-friendly so it can be packaged into a
small updater executable later. The main app should create an apply plan, exit,
then launch this process.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.update.apply_plan import UpdateApplyPlan, read_apply_plan
from app.update.verifier import verify_sha256_file


def _wait_for_pid(pid: int, timeout: float) -> bool:
    if pid <= 0:
        return True
    deadline = time.monotonic() + max(0.0, float(timeout))
    if sys.platform == "win32":
        import ctypes

        synchronize = 0x00100000
        wait_timeout = 0x00000102
        wait_object_0 = 0x00000000
        handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, int(pid))
        if not handle:
            return True
        try:
            while time.monotonic() < deadline:
                result = ctypes.windll.kernel32.WaitForSingleObject(handle, 250)
                if result == wait_object_0:
                    return True
                if result != wait_timeout:
                    return False
            return False
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    while time.monotonic() < deadline:
        try:
            import os

            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(0.25)
    return False


def _copy_tree_contents(source: Path, target: Path) -> None:
    for child in source.iterdir():
        dest = target / child.name
        if child.is_dir():
            shutil.copytree(child, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, dest)


def _zip_source_root(extract_dir: Path) -> Path:
    children = list(extract_dir.iterdir())
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return extract_dir


def _safe_extract_zip(zf: zipfile.ZipFile, target_dir: Path) -> None:
    root = target_dir.resolve()
    for member in zf.infolist():
        target = (root / member.filename).resolve()
        if root != target and root not in target.parents:
            raise ValueError(f"unsafe zip member path: {member.filename}")
    zf.extractall(root)


def _apply_portable_zip(plan: UpdateApplyPlan, *, dry_run: bool) -> dict[str, object]:
    artifact = Path(plan.artifact_path)
    install_dir = Path(plan.install_dir)
    backup_dir = Path(plan.backup_dir)
    extract_dir = backup_dir.parent / "extracted"
    if dry_run:
        return {
            "action": "portable_zip",
            "artifact": str(artifact),
            "install_dir": str(install_dir),
            "backup_dir": str(backup_dir),
            "dry_run": True,
        }
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    backup_dir.parent.mkdir(parents=True, exist_ok=True)
    if install_dir.exists():
        shutil.copytree(install_dir, backup_dir, dirs_exist_ok=True)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(artifact, "r") as zf:
        _safe_extract_zip(zf, extract_dir)
    _copy_tree_contents(_zip_source_root(extract_dir), install_dir)
    return {
        "action": "portable_zip",
        "artifact": str(artifact),
        "install_dir": str(install_dir),
        "backup_dir": str(backup_dir),
        "dry_run": False,
    }


def _apply_installer(plan: UpdateApplyPlan, *, dry_run: bool) -> dict[str, object]:
    command = [plan.artifact_path, "/S"]
    if dry_run:
        return {"action": "installer", "command": command, "dry_run": True}
    completed = subprocess.run(command, check=False)
    return {
        "action": "installer",
        "command": command,
        "returncode": int(completed.returncode),
        "dry_run": False,
    }


def apply_plan(plan: UpdateApplyPlan, *, dry_run: bool = False) -> dict[str, object]:
    integrity = verify_sha256_file(plan.artifact_path, plan.artifact_sha256)
    if not bool(integrity["ok"]):
        return {"ok": False, "reason": "sha256_mismatch", "integrity": integrity}
    kind = str(plan.artifact_kind or "").strip().lower()
    try:
        if kind in {"zip", "portable_zip"}:
            result = _apply_portable_zip(plan, dry_run=dry_run)
        elif kind in {"installer", "exe"}:
            result = _apply_installer(plan, dry_run=dry_run)
        else:
            return {"ok": False, "reason": f"unsupported_artifact_kind:{kind}", "integrity": integrity}
    except Exception as exc:
        return {"ok": False, "reason": f"update_apply_failed:{type(exc).__name__}: {exc}", "integrity": integrity}
    app_path = Path(plan.install_dir) / plan.app_exe
    if not dry_run and app_path.exists():
        subprocess.Popen([str(app_path), *plan.restart_args], cwd=str(Path(plan.install_dir)))
    return {"ok": True, "integrity": integrity, "result": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a staged TigerCapture update plan.")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--wait-pid", type=int, default=0)
    parser.add_argument("--wait-timeout", type=float, default=45.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.wait_pid and not _wait_for_pid(args.wait_pid, args.wait_timeout):
        print(json.dumps({"ok": False, "reason": "app_process_still_running"}, ensure_ascii=False))
        return 2
    report = apply_plan(read_apply_plan(args.plan), dry_run=bool(args.dry_run))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
