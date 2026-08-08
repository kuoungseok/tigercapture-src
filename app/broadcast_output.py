"""Broadcast output profile and FFmpeg command builder.

This module intentionally does not start a stream. It gives the future live UI
and VSeeFace bridge a deterministic preflight/command contract first.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.broadcast_scene import BroadcastCanvas


OUTPUT_PREVIEW = "preview"
OUTPUT_RECORDING = "recording"
OUTPUT_RTMP = "rtmp"
OUTPUT_WINDOW_SHARE = "window_share"
OUTPUT_VIRTUAL_CAMERA = "virtual_camera"

AUDIO_SOURCE_NONE = "none"
AUDIO_SOURCE_SILENCE = "silence"
AUDIO_SOURCE_DSHOW = "dshow_device"
AUDIO_SOURCE_FILE = "file"
AUDIO_SOURCE_PROJECT_BUS = "project_audio_bus"
AUDIO_SOURCE_KINDS = {
    AUDIO_SOURCE_NONE,
    AUDIO_SOURCE_SILENCE,
    AUDIO_SOURCE_DSHOW,
    AUDIO_SOURCE_FILE,
    AUDIO_SOURCE_PROJECT_BUS,
}

LIVE_TARGET_RECORD_FILE = "record_file"
LIVE_TARGET_LOCAL_MP4_ALIAS = "local_mp4"
LIVE_TARGET_YOUTUBE = "youtube_live"
LIVE_TARGET_TWITCH = "twitch"
LIVE_TARGET_CUSTOM_RTMP = "custom_rtmp"
LIVE_TARGET_DISCORD = "discord_video_call"
LIVE_TARGET_TIKTOK = "tiktok_live"
LIVE_TARGET_INSTAGRAM = "instagram_live"
LIVE_TARGET_X = "x_live"
LIVE_TARGET_SCHEMA = "tigerstudio.broadcast.live_target.v1"

_LIVE_TARGET_ALIASES = {
    LIVE_TARGET_LOCAL_MP4_ALIAS: LIVE_TARGET_RECORD_FILE,
    "mp4": LIVE_TARGET_RECORD_FILE,
    "local_recording": LIVE_TARGET_RECORD_FILE,
    "local_file": LIVE_TARGET_RECORD_FILE,
}

_OUTPUT_KINDS = {
    OUTPUT_PREVIEW,
    OUTPUT_RECORDING,
    OUTPUT_RTMP,
    OUTPUT_WINDOW_SHARE,
    OUTPUT_VIRTUAL_CAMERA,
}


@dataclass
class BroadcastAudioInput:
    kind: str = AUDIO_SOURCE_NONE
    device_name: str = ""
    file_path: str = ""
    sample_rate: int = 48000
    channels: int = 2

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "BroadcastAudioInput":
        data = payload or {}
        kind = str(data.get("audio_source_kind") or data.get("source_kind") or data.get("kind") or AUDIO_SOURCE_NONE)
        if kind not in AUDIO_SOURCE_KINDS:
            kind = AUDIO_SOURCE_NONE
        return cls(
            kind=kind,
            device_name=str(data.get("device_name") or data.get("audio_device_name") or data.get("device") or ""),
            file_path=str(data.get("file_path") or data.get("audio_file") or data.get("path") or ""),
            sample_rate=max(8000, int(data.get("sample_rate", data.get("audio_sample_rate", 48000)) or 48000)),
            channels=max(1, min(8, int(data.get("channels", data.get("audio_channels", 2)) or 2))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "device_name": self.device_name,
            "file_path": self.file_path,
            "sample_rate": int(self.sample_rate),
            "channels": int(self.channels),
        }


@dataclass
class BroadcastOutputProfile:
    kind: str = OUTPUT_PREVIEW
    target: str = ""
    video_bitrate_kbps: int = 6000
    audio_bitrate_kbps: int = 160
    encoder: str = "libx264"
    preset: str = "veryfast"
    low_latency: bool = True
    keyframe_interval_seconds: float = 2.0
    include_audio: bool = False
    audio_input: BroadcastAudioInput = field(default_factory=BroadcastAudioInput)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "BroadcastOutputProfile":
        data = payload or {}
        audio_data = data.get("audio_input") if isinstance(data.get("audio_input"), Mapping) else data
        return cls(
            kind=str(data.get("kind") or OUTPUT_PREVIEW),
            target=str(data.get("target") or data.get("url") or data.get("path") or ""),
            video_bitrate_kbps=max(500, int(data.get("video_bitrate_kbps", 6000) or 6000)),
            audio_bitrate_kbps=max(32, int(data.get("audio_bitrate_kbps", 160) or 160)),
            encoder=str(data.get("encoder") or "libx264"),
            preset=str(data.get("preset") or "veryfast"),
            low_latency=bool(data.get("low_latency", True)),
            keyframe_interval_seconds=max(0.5, float(data.get("keyframe_interval_seconds", 2.0) or 2.0)),
            include_audio=bool(data.get("include_audio", False)),
            audio_input=BroadcastAudioInput.from_mapping(audio_data),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "video_bitrate_kbps": int(self.video_bitrate_kbps),
            "audio_bitrate_kbps": int(self.audio_bitrate_kbps),
            "encoder": self.encoder,
            "preset": self.preset,
            "low_latency": bool(self.low_latency),
            "keyframe_interval_seconds": float(self.keyframe_interval_seconds),
            "include_audio": bool(self.include_audio),
            "audio_input": self.audio_input.to_dict(),
        }


@dataclass(frozen=True)
class LiveTargetPreset:
    id: str
    label: str
    output_kind: str
    default_server_url: str = ""
    default_video_bitrate_kbps: int = 6000
    default_width: int = 1920
    default_height: int = 1080
    default_fps: float = 30.0
    requires_server_url: bool = False
    requires_stream_key: bool = False
    experimental: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "output_kind": self.output_kind,
            "default_server_url": self.default_server_url,
            "default_video_bitrate_kbps": int(self.default_video_bitrate_kbps),
            "default_width": int(self.default_width),
            "default_height": int(self.default_height),
            "default_fps": float(self.default_fps),
            "requires_server_url": bool(self.requires_server_url),
            "requires_stream_key": bool(self.requires_stream_key),
            "experimental": bool(self.experimental),
            "notes": list(self.notes),
        }


_LIVE_TARGET_PRESETS: tuple[LiveTargetPreset, ...] = (
    LiveTargetPreset(
        LIVE_TARGET_RECORD_FILE,
        "Local MP4",
        OUTPUT_RECORDING,
        default_video_bitrate_kbps=12000,
        notes=("Writes Program Output to a local .mp4 file.",),
    ),
    LiveTargetPreset(
        LIVE_TARGET_YOUTUBE,
        "YouTube Live",
        OUTPUT_RTMP,
        default_server_url="rtmps://a.rtmps.youtube.com/live2",
        default_video_bitrate_kbps=6000,
        requires_stream_key=True,
        notes=("Uses the stream key from YouTube Live Control Room.",),
    ),
    LiveTargetPreset(
        LIVE_TARGET_TWITCH,
        "Twitch",
        OUTPUT_RTMP,
        default_server_url="rtmp://live.twitch.tv/app",
        default_video_bitrate_kbps=6000,
        requires_stream_key=True,
        notes=("Uses the Twitch stream key. Advanced users can replace the ingest server.",),
    ),
    LiveTargetPreset(
        LIVE_TARGET_CUSTOM_RTMP,
        "Custom RTMP / RTMPS",
        OUTPUT_RTMP,
        default_video_bitrate_kbps=6000,
        requires_server_url=True,
        notes=("For any service that provides an RTMP/RTMPS server URL and key.",),
    ),
    LiveTargetPreset(
        LIVE_TARGET_DISCORD,
        "Discord / Video Call Output",
        OUTPUT_WINDOW_SHARE,
        default_video_bitrate_kbps=6000,
        notes=("Discord uses Program Output window sharing or an installed virtual-camera backend, not an RTMP stream key.",),
    ),
    LiveTargetPreset(
        LIVE_TARGET_TIKTOK,
        "TikTok Live",
        OUTPUT_RTMP,
        default_video_bitrate_kbps=6000,
        default_width=1080,
        default_height=1920,
        requires_server_url=True,
        requires_stream_key=True,
        experimental=True,
        notes=("Experimental. Paste the TikTok-issued server URL and stream key when the account has access.",),
    ),
    LiveTargetPreset(
        LIVE_TARGET_INSTAGRAM,
        "Instagram Live",
        OUTPUT_RTMP,
        default_video_bitrate_kbps=5000,
        default_width=1080,
        default_height=1920,
        requires_server_url=True,
        requires_stream_key=True,
        experimental=True,
        notes=("Experimental vertical live output. Paste the platform-issued Live Producer URL and key.",),
    ),
    LiveTargetPreset(
        LIVE_TARGET_X,
        "X Live",
        OUTPUT_RTMP,
        default_video_bitrate_kbps=6000,
        requires_server_url=True,
        requires_stream_key=True,
        experimental=True,
        notes=("Experimental. Paste the server URL and key if the account has producer/live access.",),
    ),
)


@dataclass
class LiveTargetProfile:
    target_id: str = LIVE_TARGET_RECORD_FILE
    server_url: str = ""
    stream_key: str = ""
    output_path: str = "broadcast_output.mp4"
    video_bitrate_kbps: int = 6000
    audio_bitrate_kbps: int = 160
    encoder: str = "libx264"
    preset: str = "veryfast"
    low_latency: bool = True
    keyframe_interval_seconds: float = 2.0
    include_audio: bool = False
    audio_input: BroadcastAudioInput = field(default_factory=BroadcastAudioInput)
    auto_reconnect: bool = False
    max_retries: int = 0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "LiveTargetProfile":
        data = payload or {}
        target_id = str(data.get("target_id") or data.get("id") or data.get("platform") or LIVE_TARGET_RECORD_FILE)
        preset = live_target_preset(target_id)
        audio_data = data.get("audio_input") if isinstance(data.get("audio_input"), Mapping) else data
        audio_input = BroadcastAudioInput.from_mapping(audio_data)
        explicit_audio_choice = (
            "include_audio" in data
            or "audio_input" in data
            or "audio_source_kind" in data
            or "source_kind" in data
        )
        include_audio = bool(data.get("include_audio", False))
        if preset.output_kind == OUTPUT_RTMP and not explicit_audio_choice and audio_input.kind == AUDIO_SOURCE_NONE:
            audio_input = BroadcastAudioInput(kind=AUDIO_SOURCE_SILENCE)
            include_audio = True
        if audio_input.kind != AUDIO_SOURCE_NONE:
            include_audio = True
        auto_reconnect = bool(data.get("auto_reconnect", preset.output_kind == OUTPUT_RTMP))
        max_retries = int(data.get("max_retries", 3 if auto_reconnect else 0) or 0)
        return cls(
            target_id=preset.id,
            server_url=str(data.get("server_url") or data.get("rtmp_url") or data.get("url") or preset.default_server_url),
            stream_key=str(data.get("stream_key") or data.get("key") or ""),
            output_path=str(data.get("output_path") or data.get("path") or data.get("target") or "broadcast_output.mp4"),
            video_bitrate_kbps=max(500, int(data.get("video_bitrate_kbps", preset.default_video_bitrate_kbps) or preset.default_video_bitrate_kbps)),
            audio_bitrate_kbps=max(32, int(data.get("audio_bitrate_kbps", 160) or 160)),
            encoder=str(data.get("encoder") or "libx264"),
            preset=str(data.get("preset") or "veryfast"),
            low_latency=bool(data.get("low_latency", True)),
            keyframe_interval_seconds=max(0.5, float(data.get("keyframe_interval_seconds", 2.0) or 2.0)),
            include_audio=include_audio,
            audio_input=audio_input,
            auto_reconnect=auto_reconnect,
            max_retries=max(0, min(20, max_retries)),
        )

    def to_dict(self, *, redact_secret: bool = True) -> dict[str, Any]:
        preset = live_target_preset(self.target_id)
        data = {
            "schema": LIVE_TARGET_SCHEMA,
            "target_id": preset.id,
            "label": preset.label,
            "output_kind": preset.output_kind,
            "server_url": self.server_url,
            "output_path": self.output_path,
            "video_bitrate_kbps": int(self.video_bitrate_kbps),
            "audio_bitrate_kbps": int(self.audio_bitrate_kbps),
            "encoder": self.encoder,
            "preset": self.preset,
            "low_latency": bool(self.low_latency),
            "keyframe_interval_seconds": float(self.keyframe_interval_seconds),
            "include_audio": bool(self.include_audio),
            "audio_input": self.audio_input.to_dict(),
            "auto_reconnect": bool(self.auto_reconnect),
            "max_retries": int(self.max_retries),
            "stream_key_present": bool(str(self.stream_key or "").strip()),
            "stream_key_storage": "session",
            "experimental": bool(preset.experimental),
        }
        if redact_secret:
            data["stream_key"] = "<session>" if data["stream_key_present"] else ""
        else:
            data["stream_key"] = self.stream_key
        return data

    def to_project_settings(self) -> dict[str, Any]:
        data = self.to_dict(redact_secret=True)
        data.pop("stream_key", None)
        data["stream_key_present"] = False
        return data


def live_target_presets() -> list[dict[str, Any]]:
    return [preset.to_dict() for preset in _LIVE_TARGET_PRESETS]


def live_target_preset(target_id: str) -> LiveTargetPreset:
    text = str(target_id or "").strip()
    text = _LIVE_TARGET_ALIASES.get(text, text)
    for preset in _LIVE_TARGET_PRESETS:
        if preset.id == text:
            return preset
    return _LIVE_TARGET_PRESETS[0]


def recommended_canvas_for_live_target(
    target: LiveTargetProfile | Mapping[str, Any],
    base_canvas: BroadcastCanvas | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    profile = target if isinstance(target, LiveTargetProfile) else LiveTargetProfile.from_mapping(target)
    preset = live_target_preset(profile.target_id)
    base = BroadcastCanvas.from_mapping(base_canvas if isinstance(base_canvas, Mapping) else (base_canvas.to_dict() if isinstance(base_canvas, BroadcastCanvas) else {}))
    if int(preset.default_height) > int(preset.default_width):
        return {
            "width": int(preset.default_width),
            "height": int(preset.default_height),
            "fps": float(preset.default_fps or base.fps),
            "orientation": "vertical",
            "source": "live_target_preset",
        }
    return {
        "width": int(base.width),
        "height": int(base.height),
        "fps": float(base.fps),
        "orientation": "horizontal" if int(base.width) >= int(base.height) else "vertical",
        "source": "base_canvas",
    }


def live_target_to_output_profile(profile: LiveTargetProfile | Mapping[str, Any]) -> BroadcastOutputProfile:
    target = profile if isinstance(profile, LiveTargetProfile) else LiveTargetProfile.from_mapping(profile)
    preset = live_target_preset(target.target_id)
    if preset.output_kind == OUTPUT_RECORDING:
        output_target = target.output_path
    elif preset.output_kind == OUTPUT_RTMP:
        output_target = build_rtmp_target_url(target.server_url or preset.default_server_url, target.stream_key)
    elif preset.output_kind in {OUTPUT_WINDOW_SHARE, OUTPUT_VIRTUAL_CAMERA}:
        output_target = preset.id
    else:
        output_target = ""
    return BroadcastOutputProfile(
        kind=preset.output_kind,
        target=output_target,
        video_bitrate_kbps=target.video_bitrate_kbps,
        audio_bitrate_kbps=target.audio_bitrate_kbps,
        encoder=target.encoder,
        preset=target.preset,
        low_latency=target.low_latency,
        keyframe_interval_seconds=target.keyframe_interval_seconds,
        include_audio=target.include_audio,
        audio_input=target.audio_input,
    )


def live_target_preflight(
    target: LiveTargetProfile | Mapping[str, Any],
    canvas: BroadcastCanvas | Mapping[str, Any],
    *,
    ffmpeg_exe: str | None = None,
) -> dict[str, Any]:
    target_obj = target if isinstance(target, LiveTargetProfile) else LiveTargetProfile.from_mapping(target)
    preset = live_target_preset(target_obj.target_id)
    secret = str(target_obj.stream_key or "").strip()
    output_profile = live_target_to_output_profile(target_obj)
    diag = broadcast_output_preflight(output_profile, canvas, ffmpeg_exe=ffmpeg_exe)
    diag = _redact_secret(diag, secret)
    errors = list(diag.get("errors") or [])
    warnings = list(diag.get("warnings") or [])

    if preset.requires_server_url and not str(target_obj.server_url or "").strip():
        errors.append(f"{preset.label} requires a server URL")
    if preset.requires_stream_key and not str(target_obj.stream_key or "").strip():
        errors.append(f"{preset.label} requires a stream key")
    if preset.output_kind == OUTPUT_RTMP and not _looks_like_rtmp_url(output_profile.target):
        if "rtmp output requires an rtmp:// or rtmps:// target" not in errors:
            errors.append("rtmp output requires an rtmp:// or rtmps:// target")
    if preset.id == LIVE_TARGET_RECORD_FILE and target_obj.output_path:
        suffix = Path(str(target_obj.output_path)).suffix.casefold()
        if suffix and suffix != ".mp4":
            warnings.append("Local MP4 target expects an .mp4 file path.")
    if preset.experimental:
        warnings.append(f"{preset.label} is experimental; use the platform-issued RTMP settings.")
    if preset.output_kind == OUTPUT_WINDOW_SHARE:
        warnings.append("Use the Program Output window or a virtual camera for this target; no RTMP command is generated.")
    if preset.output_kind == OUTPUT_VIRTUAL_CAMERA:
        warnings.append("Virtual camera output requires a backend device; no FFmpeg RTMP command is generated.")

    virtual_camera = {}
    if preset.output_kind in {OUTPUT_WINDOW_SHARE, OUTPUT_VIRTUAL_CAMERA}:
        try:
            from app.broadcast_virtual_camera import virtual_camera_output_plan

            virtual_camera = virtual_camera_output_plan({})
        except Exception as exc:
            virtual_camera = {"available": False, "warnings": [str(exc)], "manual_fallback": True}
    diag.update(
        {
            "schema": "tigerstudio.broadcast.live_target_preflight.v1",
            "ok": not errors,
            "target": target_obj.to_dict(redact_secret=True),
            "preset": preset.to_dict(),
            "output_profile": _redact_secret(output_profile.to_dict(), secret),
            "command": _redact_secret(diag.get("command") or [], secret) if not errors else [],
            "errors": errors,
            "warnings": warnings,
            "secret_redacted": bool(secret),
            "virtual_camera": virtual_camera,
        }
    )
    if errors:
        diag["ok"] = False
    return diag


def build_rtmp_target_url(server_url: str, stream_key: str = "") -> str:
    server = str(server_url or "").strip()
    key = str(stream_key or "").strip()
    if not key:
        return server
    if "{stream_key}" in server:
        return server.replace("{stream_key}", key)
    if server.endswith("/"):
        return f"{server}{key}"
    return f"{server}/{key}"


def find_ffmpeg_executable() -> str:
    """Return the app's FFmpeg executable path when discoverable."""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return str(get_ffmpeg_exe())
    except Exception:
        return "ffmpeg"


def broadcast_output_preflight(
    profile: BroadcastOutputProfile | Mapping[str, Any],
    canvas: BroadcastCanvas | Mapping[str, Any],
    *,
    ffmpeg_exe: str | None = None,
) -> dict[str, Any]:
    profile_obj = profile if isinstance(profile, BroadcastOutputProfile) else BroadcastOutputProfile.from_mapping(profile)
    canvas_obj = canvas if isinstance(canvas, BroadcastCanvas) else BroadcastCanvas.from_mapping(canvas)
    errors: list[str] = []
    warnings: list[str] = []

    if profile_obj.kind not in _OUTPUT_KINDS:
        errors.append(f"unsupported broadcast output kind: {profile_obj.kind}")
    if profile_obj.kind == OUTPUT_RTMP and not _looks_like_rtmp_url(profile_obj.target):
        errors.append("rtmp output requires an rtmp:// or rtmps:// target")
    if profile_obj.kind == OUTPUT_RECORDING and not profile_obj.target:
        errors.append("recording output requires a target file path")
    if profile_obj.kind == OUTPUT_PREVIEW and profile_obj.target:
        warnings.append("preview output ignores target")
    _validate_audio(profile=profile_obj, errors=errors, warnings=warnings)

    command: list[str] = []
    if profile_obj.kind == OUTPUT_WINDOW_SHARE:
        warnings.append("window share output uses the Program Output window and does not build an FFmpeg command")
    if profile_obj.kind == OUTPUT_VIRTUAL_CAMERA:
        warnings.append("virtual camera output is a backend target and does not build an FFmpeg RTMP command")

    if not errors and profile_obj.kind in {OUTPUT_RECORDING, OUTPUT_RTMP}:
        command = build_ffmpeg_broadcast_command(
            profile_obj,
            canvas_obj,
            ffmpeg_exe=ffmpeg_exe or find_ffmpeg_executable(),
        )

    return {
        "ok": not errors,
        "kind": profile_obj.kind,
        "canvas": canvas_obj.to_dict(),
        "profile": profile_obj.to_dict(),
        "ffmpeg_exe": ffmpeg_exe or find_ffmpeg_executable(),
        "command": command,
        "errors": errors,
        "warnings": warnings,
    }


def build_ffmpeg_broadcast_command(
    profile: BroadcastOutputProfile | Mapping[str, Any],
    canvas: BroadcastCanvas | Mapping[str, Any],
    *,
    ffmpeg_exe: str | None = None,
) -> list[str]:
    """Build a raw RGB stdin -> recording/RTMP FFmpeg command."""
    profile_obj = profile if isinstance(profile, BroadcastOutputProfile) else BroadcastOutputProfile.from_mapping(profile)
    canvas_obj = canvas if isinstance(canvas, BroadcastCanvas) else BroadcastCanvas.from_mapping(canvas)
    if profile_obj.kind in {OUTPUT_PREVIEW, OUTPUT_WINDOW_SHARE, OUTPUT_VIRTUAL_CAMERA}:
        return []
    if profile_obj.kind == OUTPUT_RTMP and not _looks_like_rtmp_url(profile_obj.target):
        raise ValueError("rtmp output requires an rtmp:// or rtmps:// target")
    if profile_obj.kind == OUTPUT_RECORDING and not profile_obj.target:
        raise ValueError("recording output requires a target file path")

    fps = max(1.0, float(canvas_obj.fps))
    keyint = max(1, int(round(fps * profile_obj.keyframe_interval_seconds)))
    bitrate = f"{int(profile_obj.video_bitrate_kbps)}k"
    cmd = [
        str(ffmpeg_exe or find_ffmpeg_executable()),
        "-hide_banner",
        "-loglevel",
        "warning",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{int(canvas_obj.width)}x{int(canvas_obj.height)}",
        "-r",
        _fps_arg(fps),
        "-i",
        "pipe:0",
        "-c:v",
        profile_obj.encoder,
        "-preset",
        profile_obj.preset,
    ]
    if profile_obj.include_audio:
        audio_args = _audio_input_args(profile_obj.audio_input)
        if audio_args:
            cmd[14:14] = audio_args
            cmd.extend([
                "-map",
                "0:v:0",
                "-map",
                "1:a:0?",
                "-c:a",
                "aac",
                "-b:a",
                f"{int(profile_obj.audio_bitrate_kbps)}k",
                "-ac",
                str(int(profile_obj.audio_input.channels)),
                "-ar",
                str(int(profile_obj.audio_input.sample_rate)),
            ])
        else:
            cmd.extend(["-an"])
    else:
        cmd.extend(["-an"])
    if profile_obj.low_latency:
        cmd.extend(["-tune", "zerolatency"])
    if profile_obj.kind == OUTPUT_RTMP:
        cmd.extend(
            [
                "-profile:v",
                "main",
                "-bf",
                "0",
                "-x264-params",
                f"keyint={keyint}:min-keyint={keyint}:scenecut=0",
            ]
        )
    cmd.extend([
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        bitrate,
        "-maxrate",
        bitrate,
        "-bufsize",
        f"{int(profile_obj.video_bitrate_kbps * 2)}k",
        "-g",
        str(keyint),
    ])
    if profile_obj.kind == OUTPUT_RTMP:
        cmd.extend(["-f", "flv", "-flvflags", "no_duration_filesize", profile_obj.target])
    else:
        target = str(Path(profile_obj.target))
        cmd.extend(["-y", "-movflags", "+faststart", target])
    return cmd


def _looks_like_rtmp_url(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith("rtmp://") or text.startswith("rtmps://")


def _validate_audio(
    *,
    profile: BroadcastOutputProfile,
    errors: list[str],
    warnings: list[str],
) -> None:
    if not profile.include_audio:
        return
    audio = profile.audio_input
    if audio.kind == AUDIO_SOURCE_NONE:
        errors.append("live audio requires an audio source: silence, dshow_device, or file")
    elif audio.kind == AUDIO_SOURCE_DSHOW and not audio.device_name:
        errors.append("dshow audio requires an audio device name")
    elif audio.kind == AUDIO_SOURCE_FILE and not audio.file_path:
        errors.append("file audio requires an audio file path")
    elif audio.kind == AUDIO_SOURCE_PROJECT_BUS and not audio.file_path:
        warnings.append("project audio bus will be rendered to a temporary audio file when the live target starts")
    elif audio.kind == AUDIO_SOURCE_SILENCE:
        warnings.append("live audio uses generated silent stereo audio")


def _audio_input_args(audio: BroadcastAudioInput) -> list[str]:
    if audio.kind == AUDIO_SOURCE_SILENCE:
        layout = "mono" if int(audio.channels) == 1 else "stereo"
        return [
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout={layout}:sample_rate={int(audio.sample_rate)}",
        ]
    if audio.kind == AUDIO_SOURCE_DSHOW:
        return ["-f", "dshow", "-i", f"audio={audio.device_name}"]
    if audio.kind == AUDIO_SOURCE_FILE:
        return ["-stream_loop", "-1", "-i", str(Path(audio.file_path))]
    if audio.kind == AUDIO_SOURCE_PROJECT_BUS and audio.file_path:
        return ["-stream_loop", "-1", "-i", str(Path(audio.file_path))]
    return []


def _redact_secret(value: Any, secret: str) -> Any:
    key = str(secret or "")
    if not key:
        return value
    if isinstance(value, str):
        return value.replace(key, "<stream_key>")
    if isinstance(value, list):
        return [_redact_secret(item, key) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_secret(item, key) for item in value)
    if isinstance(value, dict):
        return {str(k): _redact_secret(v, key) for k, v in value.items()}
    return value


def _fps_arg(value: float) -> str:
    rounded = round(float(value))
    if abs(float(value) - rounded) < 1e-6:
        return str(int(rounded))
    return f"{float(value):.3f}".rstrip("0").rstrip(".")
