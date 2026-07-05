"""Virtual camera capture probes for VSeeFace integration."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any


VIRTUAL_CAMERA_PROBE_SCHEMA = "tigerstudio.vtuber.virtual_camera_probe.v1"
DIRECTSHOW_VIDEO_INPUT_CATEGORY = "{860BB310-5D01-11D0-BD3B-00A0C911CE86}"


def probe_virtual_camera_frames(
    *,
    preferred_name: str = "VSeeFaceCamera",
    max_index: int = 8,
    frames_per_camera: int = 8,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Try to capture a non-black frame from local camera indexes.

    OpenCV cannot reliably enumerate DirectShow device names on every Windows
    installation, so this scans camera indexes and records pixel diagnostics.
    """
    report = {
        "schema": VIRTUAL_CAMERA_PROBE_SCHEMA,
        "ok": False,
        "preferred_name": preferred_name,
        "max_index": int(max_index),
        "frames_per_camera": int(frames_per_camera),
        "directshow_devices": enumerate_directshow_video_devices(),
        "preferred_registered": False,
        "named_cameras": [],
        "cameras": [],
        "ffmpeg_camera": None,
        "selected": None,
        "errors": [],
    }
    report["preferred_registered"] = any(
        preferred_name.casefold() in str(device.get("name", "")).casefold()
        for device in report["directshow_devices"]
    )
    try:
        from PIL import Image, ImageStat
    except Exception as exc:
        report["errors"].append(f"capture_dependencies_unavailable:{exc}")
        return report
    try:
        import cv2  # type: ignore
    except Exception as exc:
        cv2 = None
        report["errors"].append(f"opencv_capture_unavailable:{exc}")

    output_dir = Path(out_dir) if out_dir is not None else Path.cwd() / "debugCapture" / "virtual_camera_probe"
    output_dir.mkdir(parents=True, exist_ok=True)

    if cv2 is not None:
        named_sources = [preferred_name]
        for device in report["directshow_devices"]:
            name = str(device.get("name", "")).strip()
            if name and name not in named_sources and preferred_name.casefold() in name.casefold():
                named_sources.append(name)
        for name in named_sources:
            camera = _probe_capture(
                cv2,
                Image,
                ImageStat,
                f"video={name}",
                f"name:{name}",
                max(1, int(frames_per_camera)),
                output_dir / f"camera_name_{_safe_filename(name)}.png",
            )
            report["named_cameras"].append(camera)
            if camera["nonblack"] and report["selected"] is None:
                report["selected"] = camera
                report["ok"] = True

        for index in range(max(0, int(max_index)) + 1):
            camera = _probe_capture(
                cv2,
                Image,
                ImageStat,
                index,
                f"index:{index}",
                max(1, int(frames_per_camera)),
                output_dir / f"camera_{index}.png",
            )
            camera["index"] = index
            report["cameras"].append(camera)
            if camera["nonblack"] and report["selected"] is None:
                report["selected"] = camera
                report["ok"] = True

    ffmpeg_camera = _probe_ffmpeg_directshow(
        Image,
        ImageStat,
        preferred_name,
        output_dir / "camera_ffmpeg.png",
    )
    report["ffmpeg_camera"] = ffmpeg_camera
    if ffmpeg_camera["nonblack"] and report["selected"] is None:
        report["selected"] = ffmpeg_camera
        report["ok"] = True
    if not report["ok"]:
        if ffmpeg_camera.get("opened"):
            report["errors"].append("virtual_camera_black_frame")
        else:
            report["errors"].append("no_nonblack_virtual_camera_frame")
    return report


def enumerate_directshow_video_devices() -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    try:
        import winreg
    except Exception:
        return devices

    roots = [
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Classes\CLSID\{DIRECTSHOW_VIDEO_INPUT_CATEGORY}\Instance"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Classes\CLSID\{DIRECTSHOW_VIDEO_INPUT_CATEGORY}\Instance"),
        (winreg.HKEY_CURRENT_USER, rf"Software\Classes\CLSID\{DIRECTSHOW_VIDEO_INPUT_CATEGORY}\Instance"),
    ]
    seen: set[tuple[str, str]] = set()
    for hive, path in roots:
        try:
            with winreg.OpenKey(hive, path) as key:
                count = winreg.QueryInfoKey(key)[0]
                for index in range(count):
                    clsid = winreg.EnumKey(key, index)
                    with winreg.OpenKey(key, clsid) as child:
                        name = _read_registry_string(winreg, child, "FriendlyName") or clsid
                        merit = _read_registry_string(winreg, child, "Merit")
                    marker = (clsid, name)
                    if marker in seen:
                        continue
                    seen.add(marker)
                    devices.append({
                        "name": name,
                        "clsid": clsid,
                        "merit": merit,
                        "registry_path": path,
                    })
        except OSError:
            continue
    return devices


def _probe_capture(
    cv2: Any,
    image_type: Any,
    image_stat_type: Any,
    source: Any,
    source_label: str,
    frames_per_camera: int,
    sample_path: Path,
) -> dict[str, Any]:
    cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    opened = bool(cap.isOpened())
    camera = {
        "source": source_label,
        "opened": opened,
        "frames_read": 0,
        "sample_path": "",
        "mean_luma": 0.0,
        "unique_colors": 0,
        "nonblack": False,
    }
    try:
        if opened:
            frame = None
            for _ in range(max(1, int(frames_per_camera))):
                ok, candidate = cap.read()
                if ok and candidate is not None:
                    frame = candidate
                    camera["frames_read"] += 1
            if frame is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = image_type.fromarray(rgb)
                stat = image_stat_type.Stat(image)
                mean = tuple(float(value) for value in stat.mean)
                mean_luma = 0.2126 * mean[0] + 0.7152 * mean[1] + 0.0722 * mean[2]
                colors = image.getcolors(maxcolors=1_000_000)
                image.save(sample_path)
                camera.update({
                    "sample_path": str(sample_path),
                    "mean_luma": round(mean_luma, 3),
                    "unique_colors": len(colors) if colors is not None else -1,
                    "nonblack": mean_luma > 5.0 and (len(colors) if colors is not None else 1000) > 16,
                })
    finally:
        cap.release()
    return camera


def _probe_ffmpeg_directshow(
    image_type: Any,
    image_stat_type: Any,
    preferred_name: str,
    sample_path: Path,
) -> dict[str, Any]:
    camera = {
        "source": f"ffmpeg:dshow:{preferred_name}",
        "available": False,
        "opened": False,
        "returncode": None,
        "sample_path": "",
        "mean_luma": 0.0,
        "unique_colors": 0,
        "nonblack": False,
        "stderr_tail": "",
        "errors": [],
    }
    try:
        import imageio_ffmpeg
    except Exception as exc:
        camera["errors"].append(f"imageio_ffmpeg_unavailable:{exc}")
        return camera

    try:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        camera["errors"].append(f"ffmpeg_exe_unavailable:{exc}")
        return camera

    camera["available"] = True
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-y",
        "-f",
        "dshow",
        "-rtbufsize",
        "100M",
        "-i",
        f"video={preferred_name}",
        "-frames:v",
        "1",
        "-update",
        "1",
        str(sample_path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        camera["errors"].append(f"ffmpeg_capture_failed:{exc}")
        return camera

    camera["returncode"] = int(completed.returncode)
    stderr = completed.stderr or ""
    camera["stderr_tail"] = stderr[-1200:]
    if sample_path.is_file() and sample_path.stat().st_size > 0:
        camera["opened"] = completed.returncode == 0
        camera.update(_analyze_image(image_type, image_stat_type, sample_path))
    elif completed.returncode != 0:
        camera["errors"].append("ffmpeg_returned_error")
    else:
        camera["errors"].append("ffmpeg_no_sample_frame")
    return camera


def _analyze_image(image_type: Any, image_stat_type: Any, sample_path: Path) -> dict[str, Any]:
    image = image_type.open(sample_path).convert("RGB")
    stat = image_stat_type.Stat(image)
    mean = tuple(float(value) for value in stat.mean)
    mean_luma = 0.2126 * mean[0] + 0.7152 * mean[1] + 0.0722 * mean[2]
    colors = image.getcolors(maxcolors=1_000_000)
    color_count = len(colors) if colors is not None else -1
    return {
        "sample_path": str(sample_path),
        "mean_luma": round(mean_luma, 3),
        "unique_colors": color_count,
        "nonblack": mean_luma > 5.0 and (color_count if color_count >= 0 else 1000) > 16,
    }


def _read_registry_string(winreg: Any, key: Any, name: str) -> str:
    try:
        value, _kind = winreg.QueryValueEx(key, name)
    except OSError:
        return ""
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def _safe_filename(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    return safe[:80] or "camera"
