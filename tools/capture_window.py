"""Capture a visible Windows window to PNG."""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a window by title substring or process id.")
    parser.add_argument("--title-contains", default="")
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--out", required=True)
    parser.add_argument("--backend", choices=["mss", "pil", "printwindow"], default="mss")
    args = parser.parse_args()

    hwnd = _find_window(args.title_contains, args.pid)
    if not hwnd:
        print({"ok": False, "error": "window_not_found"})
        return 2
    rect = _window_rect(hwnd)
    if rect[2] <= rect[0] or rect[3] <= rect[1]:
        print({"ok": False, "error": "invalid_window_rect", "hwnd": hwnd, "rect": rect})
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    left, top, right, bottom = rect
    if args.backend == "pil":
        from PIL import ImageGrab

        image = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
        image.save(out)
    elif args.backend == "printwindow":
        _capture_printwindow(hwnd, out)
    else:
        import mss
        import mss.tools

        img = mss.mss().grab({"left": left, "top": top, "width": right - left, "height": bottom - top})
        mss.tools.to_png(img.rgb, img.size, output=str(out))
    print({"ok": True, "hwnd": hwnd, "rect": rect, "out": str(out)})
    return 0


def _find_window(title_contains: str, pid: int) -> int:
    user32 = ctypes.windll.user32
    matches: list[int] = []
    needle = title_contains.casefold()

    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, 512)
        window_pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        title_ok = not needle or needle in title.value.casefold()
        pid_ok = not pid or int(window_pid.value) == int(pid)
        if title_ok and pid_ok:
            matches.append(int(hwnd))
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return matches[0] if matches else 0


def _window_rect(hwnd: int) -> list[int]:
    user32 = ctypes.windll.user32
    rect = (ctypes.c_long * 4)()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])]


def _capture_printwindow(hwnd: int, out: Path) -> None:
    from PIL import Image

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
