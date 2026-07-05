"""Probe VSeeFace graphics backends and capture black-window diagnostics."""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
from pathlib import Path
import subprocess
import sys
import time

from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vseeface_capture_diagnostics import analyze_graphics_probe_report  # noqa: E402
from app.vtuber.vseeface_bridge import default_vseeface_exe  # noqa: E402

DEFAULT_EXE = default_vseeface_exe(ROOT)
PLAYER_LOG = Path.home() / "AppData" / "LocalLow" / "Emiliana_vt" / "VSeeFace" / "Player.log"
SCREEN_ARGS = ["-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "720"]


VARIANTS = [
    ("default_native", [], []),
    ("default_windowed", [], SCREEN_ARGS),
    ("d3d11_windowed", ["-force-d3d11"], SCREEN_ARGS),
    ("d3d11_popupwindow", ["-force-d3d11", "-popupwindow"], SCREEN_ARGS),
    ("d3d11_no_singlethreaded", ["-force-d3d11", "-force-d3d11-no-singlethreaded"], SCREEN_ARGS),
    ("d3d11_singlethreaded", ["-force-d3d11", "-force-d3d11-singlethreaded"], SCREEN_ARGS),
    ("vulkan_windowed", ["-force-vulkan"], SCREEN_ARGS),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Restart VSeeFace with graphics flags and capture diagnostics.")
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "vseeface_graphics_probe"))
    parser.add_argument("--wait-seconds", type=float, default=10.0)
    parser.add_argument("--include-glcore", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    variants = list(VARIANTS)
    if args.include_glcore:
        variants.append(("glcore_windowed", ["-force-glcore"], SCREEN_ARGS))
    report = {
        "schema": "tigerstudio.vtuber.vseeface_graphics_probe.v1",
        "exe": str(Path(args.exe).resolve()),
        "wait_seconds": max(1.0, float(args.wait_seconds)),
        "variants": [],
    }
    _stop_existing_vseeface()
    for name, flags, screen_args in variants:
        report["variants"].append(_probe_variant(Path(args.exe), name, flags, screen_args, out_dir, max(1.0, float(args.wait_seconds))))
    report["diagnostics"] = analyze_graphics_probe_report(report)
    report["best_variant"] = _choose_best(report["variants"], report["diagnostics"])
    out = out_dir / "report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "best_variant": report["best_variant"]}, ensure_ascii=False))
    return 0


def _probe_variant(exe: Path, name: str, flags: list[str], screen_args: list[str], out_dir: Path, wait_seconds: float) -> dict:
    _stop_existing_vseeface()
    before_log_size = PLAYER_LOG.stat().st_size if PLAYER_LOG.is_file() else 0
    command = [str(exe), *flags, *screen_args]
    proc = subprocess.Popen(command, cwd=str(exe.parent))
    time.sleep(wait_seconds)
    hwnd = _find_window_by_pid(proc.pid)
    row = {
        "name": name,
        "flags": flags,
        "screen_args": screen_args,
        "pid": proc.pid,
        "hwnd": hwnd,
        "alive": proc.poll() is None,
        "printwindow": {},
        "mss": {},
        "virtual_camera": {},
        "log_tail": _read_new_log_tail(before_log_size),
    }
    if hwnd:
        row["rect"] = _window_rect(hwnd)
        print_path = out_dir / f"{name}_printwindow.png"
        mss_path = out_dir / f"{name}_mss.png"
        try:
            _capture_printwindow(hwnd, print_path)
            row["printwindow"] = _image_stats(print_path)
        except Exception as exc:
            row["printwindow"] = {"ok": False, "error": repr(exc), "path": str(print_path)}
        try:
            _capture_mss(hwnd, mss_path)
            row["mss"] = _image_stats(mss_path)
        except Exception as exc:
            row["mss"] = {"ok": False, "error": repr(exc), "path": str(mss_path)}
    virtual_path = out_dir / f"{name}_virtual_camera.png"
    try:
        row["virtual_camera"] = _capture_virtual_camera(virtual_path)
    except Exception as exc:
        row["virtual_camera"] = {"ok": False, "error": repr(exc), "path": str(virtual_path)}
    _stop_process(proc)
    return row


def _choose_best(rows: list[dict], diagnostics: dict) -> dict:
    usable_names = {str(row.get("name")) for row in diagnostics.get("usable_variants") or [] if isinstance(row, dict)}
    if not usable_names:
        return {}
    best = None
    best_score = -1.0
    for row in rows:
        if str(row.get("name")) not in usable_names:
            continue
        stats = row.get("printwindow") if isinstance(row.get("printwindow"), dict) else {}
        content = stats.get("content") if isinstance(stats.get("content"), dict) else {}
        score = float(content.get("mean_luma", 0.0)) + float(content.get("unique_colors", 0)) / 1000.0
        if score > best_score:
            best = row
            best_score = score
    if not best:
        return {}
    return {
        "name": best.get("name"),
        "flags": best.get("flags"),
        "score": round(best_score, 3),
        "content": (best.get("printwindow") or {}).get("content"),
    }


def _stop_existing_vseeface() -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Process VSeeFace -ErrorAction SilentlyContinue | Stop-Process -Force"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    time.sleep(0.75)


def _stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _find_window_by_pid(pid: int) -> int:
    user32 = ctypes.windll.user32
    matches: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        window_pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if int(window_pid.value) == int(pid):
            matches.append(int(hwnd))
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return matches[0] if matches else 0


def _window_rect(hwnd: int) -> list[int]:
    rect = (ctypes.c_long * 4)()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])]


def _capture_mss(hwnd: int, out: Path) -> None:
    import mss
    import mss.tools

    left, top, right, bottom = _window_rect(hwnd)
    img = mss.mss().grab({"left": left, "top": top, "width": right - left, "height": bottom - top})
    mss.tools.to_png(img.rgb, img.size, output=str(out))


def _capture_printwindow(hwnd: int, out: Path) -> None:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    left, top, right, bottom = _window_rect(hwnd)
    width, height = max(1, right - left), max(1, bottom - top)
    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    old_obj = gdi32.SelectObject(mem_dc, bitmap)
    try:
        user32.PrintWindow(hwnd, mem_dc, 2)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buffer = ctypes.create_string_buffer(width * height * 4)
        gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(bmi), 0)
        image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
        image.save(out)
    finally:
        gdi32.SelectObject(mem_dc, old_obj)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, hwnd_dc)


def _capture_virtual_camera(out: Path) -> dict:
    try:
        import imageio_ffmpeg
    except Exception as exc:
        return {"ok": False, "opened": False, "error": f"imageio_ffmpeg_unavailable:{exc}", "path": str(out)}
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-y",
            "-f",
            "dshow",
            "-rtbufsize",
            "100M",
            "-i",
            "video=VSeeFaceCamera",
            "-frames:v",
            "1",
            "-update",
            "1",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if not out.is_file():
        return {
            "ok": False,
            "opened": False,
            "returncode": completed.returncode,
            "stderr_tail": (completed.stderr or "")[-1200:],
            "path": str(out),
        }
    stats = _image_stats(out)
    content = stats.get("content") if isinstance(stats.get("content"), dict) else {}
    return {
        "ok": bool(stats.get("content_nonblack")),
        "opened": completed.returncode == 0,
        "returncode": completed.returncode,
        "path": str(out),
        "content": content,
        "content_nonblack": bool(stats.get("content_nonblack")),
        "stderr_tail": (completed.stderr or "")[-1200:],
    }


def _image_stats(path: Path) -> dict:
    image = Image.open(path).convert("RGB")
    full = _stats_for_image(image)
    content = _stats_for_image(image.crop((0, min(40, image.height - 1), image.width, image.height)))
    return {
        "ok": True,
        "path": str(path),
        "size": list(image.size),
        "full": full,
        "content": content,
        "content_nonblack": content["mean_luma"] > 5.0 and content["unique_colors"] > 16,
    }


def _stats_for_image(image: Image.Image) -> dict:
    stat = ImageStat.Stat(image)
    mean = tuple(float(v) for v in stat.mean)
    mean_luma = 0.2126 * mean[0] + 0.7152 * mean[1] + 0.0722 * mean[2]
    colors = image.getcolors(maxcolors=1_000_000)
    return {
        "mean_rgb": [round(v, 3) for v in mean],
        "mean_luma": round(mean_luma, 3),
        "extrema": [list(item) for item in image.getextrema()],
        "unique_colors": len(colors) if colors is not None else -1,
    }


def _read_new_log_tail(before_size: int) -> str:
    if not PLAYER_LOG.is_file():
        return ""
    data = PLAYER_LOG.read_bytes()
    if before_size and len(data) > before_size:
        data = data[before_size:]
    return data.decode("utf-8", errors="replace")[-3000:]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", wt.LONG),
        ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG),
        ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


if __name__ == "__main__":
    raise SystemExit(main())
