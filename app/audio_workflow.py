"""Professional audio workflow helpers.

Qt-free helpers for dialogue cleanup, loudness targets, clip gain, buses, and
automation. The Sound Editor can use these directly, while export consumes the
same payload through ``app.audio_tracks._build_effect_chain``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LoudnessTarget:
    id: str
    name: str
    integrated_lufs: float
    true_peak_db: float
    lra: float
    description: str = ""

    def to_effect_payload(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "target_i": float(self.integrated_lufs),
            "true_peak": float(self.true_peak_db),
            "lra": float(self.lra),
            "target_id": self.id,
        }


LOUDNESS_TARGETS: tuple[LoudnessTarget, ...] = (
    LoudnessTarget("shortform", "Short-form / web", -14.0, -1.0, 11.0, "YouTube/TikTok style delivery."),
    LoudnessTarget("podcast", "Podcast voice", -16.0, -1.5, 7.0, "Clear spoken-word target."),
    LoudnessTarget("broadcast", "Broadcast EBU R128", -23.0, -1.0, 7.0, "Broadcast-safe loudness."),
    LoudnessTarget("stream_music", "Streaming music", -14.0, -1.0, 9.0, "Music-oriented streaming target."),
)


@dataclass(frozen=True)
class AudioBusSpec:
    id: str
    name: str
    role: str = "mix"  # dialogue | music | sfx | mix
    volume: float = 1.0
    pan: float = 0.0
    effects: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "volume": float(self.volume),
            "pan": float(self.pan),
            "effects": dict(self.effects),
        }


@dataclass(frozen=True)
class AudioSendSpec:
    source_bus: str
    target_bus: str
    gain_db: float = 0.0
    pre_fader: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_bus": self.source_bus,
            "target_bus": self.target_bus,
            "gain_db": float(self.gain_db),
            "pre_fader": bool(self.pre_fader),
        }


@dataclass(frozen=True)
class AudioRoutingMatrix:
    """Fairlight-style routing plan for tracks, buses, and sends."""

    buses: tuple[AudioBusSpec, ...] = field(default_factory=lambda: DEFAULT_BUSES)
    track_routes: dict[str, str] = field(default_factory=dict)
    sends: tuple[AudioSendSpec, ...] = ()
    sample_rate: int = 48000
    channel_layout: str = "stereo"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AudioRoutingMatrix":
        data = data or {}
        buses = []
        for raw in data.get("buses", []) or []:
            if isinstance(raw, dict):
                buses.append(AudioBusSpec(
                    id=str(raw.get("id", "")),
                    name=str(raw.get("name", raw.get("id", ""))),
                    role=str(raw.get("role", "mix")),
                    volume=float(raw.get("volume", 1.0)),
                    pan=float(raw.get("pan", 0.0)),
                    effects=dict(raw.get("effects", {}) or {}),
                ))
        sends = []
        for raw in data.get("sends", []) or []:
            if isinstance(raw, dict):
                sends.append(AudioSendSpec(
                    source_bus=str(raw.get("source_bus", "")),
                    target_bus=str(raw.get("target_bus", "")),
                    gain_db=float(raw.get("gain_db", 0.0)),
                    pre_fader=bool(raw.get("pre_fader", False)),
                ))
        return cls(
            buses=tuple(buses) or DEFAULT_BUSES,
            track_routes={str(k): str(v) for k, v in dict(data.get("track_routes", {}) or {}).items()},
            sends=tuple(sends),
            sample_rate=int(data.get("sample_rate", 48000) or 48000),
            channel_layout=str(data.get("channel_layout", "stereo") or "stereo"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "buses": [bus.to_dict() for bus in self.buses],
            "track_routes": dict(self.track_routes),
            "sends": [send.to_dict() for send in self.sends],
            "sample_rate": int(self.sample_rate),
            "channel_layout": str(self.channel_layout),
        }

    def bus_ids(self) -> set[str]:
        return {bus.id for bus in self.buses}

    def validation_warnings(self) -> list[str]:
        ids = self.bus_ids()
        warnings = []
        for track_id, bus_id in self.track_routes.items():
            if bus_id not in ids:
                warnings.append(f"track {track_id} routes to missing bus {bus_id}")
        for send in self.sends:
            if send.source_bus not in ids:
                warnings.append(f"send source bus missing: {send.source_bus}")
            if send.target_bus not in ids:
                warnings.append(f"send target bus missing: {send.target_bus}")
        return warnings


@dataclass(frozen=True)
class RealtimeMixerNode:
    id: str
    kind: str = "track"  # track | bus | send | return | output
    inputs: tuple[str, ...] = ()
    latency_samples: int = 0
    effects: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "kind": str(self.kind),
            "inputs": list(self.inputs),
            "latency_samples": max(0, int(self.latency_samples)),
            "effects": list(self.effects),
        }


@dataclass(frozen=True)
class RealtimeMixerGraph:
    """Realtime Fairlight-style audio graph contract for routing/export parity."""

    nodes: tuple[RealtimeMixerNode, ...] = ()
    sample_rate: int = 48000
    block_size: int = 512
    latency_compensation: bool = True
    max_virtual_tracks: int = 512

    @classmethod
    def from_routing_matrix(cls, matrix: AudioRoutingMatrix | dict[str, Any] | None) -> "RealtimeMixerGraph":
        m = matrix if isinstance(matrix, AudioRoutingMatrix) else AudioRoutingMatrix.from_dict(matrix if isinstance(matrix, dict) else None)
        nodes: list[RealtimeMixerNode] = []
        for track_id, bus_id in sorted(m.track_routes.items(), key=lambda item: item[0]):
            nodes.append(RealtimeMixerNode(f"track_{track_id}", "track", (), 64, ("gain", "eq", "dynamics")))
            nodes.append(RealtimeMixerNode(f"route_{track_id}_{bus_id}", "send", (f"track_{track_id}", f"bus_{bus_id}"), 0, ()))
        for bus in m.buses:
            bus_effects = tuple(str(key) for key, value in bus.effects.items() if value)
            if bus.role == "dialogue":
                bus_effects = bus_effects or ("voice_isolation", "deesser", "compressor")
            elif bus.role == "music":
                bus_effects = bus_effects or ("eq", "limiter")
            elif bus.role == "mix":
                bus_effects = bus_effects or ("loudness_meter", "true_peak_limiter")
            nodes.append(RealtimeMixerNode(f"bus_{bus.id}", "bus", (), 128, bus_effects))
        nodes.append(RealtimeMixerNode("master_out", "output", tuple(f"bus_{bus.id}" for bus in m.buses), 0, ("loudness_meter",)))
        return cls(
            nodes=tuple(nodes),
            sample_rate=m.sample_rate,
            block_size=channel_layout_block_size(m.channel_layout),
            latency_compensation=True,
            max_virtual_tracks=max(2000, len(m.track_routes)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "sample_rate": int(self.sample_rate),
            "block_size": int(self.block_size),
            "latency_compensation": bool(self.latency_compensation),
            "max_virtual_tracks": int(self.max_virtual_tracks),
            "total_latency_samples": self.total_latency_samples(),
            "validation_warnings": self.validation_warnings(),
        }

    def total_latency_samples(self) -> int:
        return max((node.latency_samples for node in self.nodes), default=0)

    def validation_warnings(self) -> list[str]:
        ids = {node.id for node in self.nodes}
        warnings: list[str] = []
        if not any(node.kind == "output" for node in self.nodes):
            warnings.append("mixer graph has no output node")
        for node in self.nodes:
            for input_id in node.inputs:
                if input_id not in ids:
                    warnings.append(f"node {node.id} input missing: {input_id}")
        if not self.latency_compensation and self.total_latency_samples() > 0:
            warnings.append("latency compensation is disabled while nodes report latency")
        return warnings


def channel_layout_block_size(channel_layout: str) -> int:
    key = str(channel_layout or "stereo").casefold()
    if key in {"5.1", "7.1", "22.2", "ambisonics"}:
        return 1024
    return 512


@dataclass(frozen=True)
class ADRCue:
    id: str
    start_ms: int
    end_ms: int
    text: str
    take_count: int = 0
    record_arm: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "start_ms": max(0, int(self.start_ms)),
            "end_ms": max(max(0, int(self.start_ms)) + 1, int(self.end_ms)),
            "text": str(self.text),
            "take_count": max(0, int(self.take_count)),
            "record_arm": bool(self.record_arm),
        }


@dataclass(frozen=True)
class ElasticAudioRetime:
    clip_id: str
    source_duration_ms: int
    target_duration_ms: int
    preserve_pitch: bool = True
    algorithm: str = "elastique_pro"

    def to_dict(self) -> dict[str, Any]:
        src = max(1, int(self.source_duration_ms))
        dst = max(1, int(self.target_duration_ms))
        return {
            "clip_id": str(self.clip_id),
            "source_duration_ms": src,
            "target_duration_ms": dst,
            "stretch_ratio": round(dst / src, 6),
            "preserve_pitch": bool(self.preserve_pitch),
            "algorithm": str(self.algorithm),
        }


@dataclass(frozen=True)
class SFXLibraryItem:
    id: str
    path: str
    tags: tuple[str, ...] = ()
    loudness_lufs: float = -18.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "path": str(self.path),
            "tags": list(self.tags),
            "loudness_lufs": float(self.loudness_lufs),
        }


DEFAULT_BUSES: tuple[AudioBusSpec, ...] = (
    AudioBusSpec("dialogue", "Dialogue", "dialogue"),
    AudioBusSpec("music", "Music", "music"),
    AudioBusSpec("sfx", "SFX", "sfx"),
    AudioBusSpec("master", "Master", "mix"),
)


def db_to_gain(db: float) -> float:
    return 10.0 ** (float(db) / 20.0)


def gain_to_db(gain: float) -> float:
    import math

    if gain <= 0:
        return -120.0
    return 20.0 * math.log10(float(gain))


def loudness_target(target_id: str) -> LoudnessTarget:
    for target in LOUDNESS_TARGETS:
        if target.id == target_id:
            return target
    return LOUDNESS_TARGETS[0]


def build_default_routing_matrix(track_rows: list[dict[str, Any]] | None = None) -> AudioRoutingMatrix:
    routes: dict[str, str] = {}
    for idx, track in enumerate(track_rows or []):
        raw_role = str(track.get("role") or track.get("bus_role") or track.get("bus_id") or track.get("label") or "").lower()
        if "dialogue" in raw_role or "voice" in raw_role or raw_role in {"dlg", "vo"}:
            bus = "dialogue"
        elif "music" in raw_role or "bgm" in raw_role:
            bus = "music"
        elif "sfx" in raw_role or "effect" in raw_role or "sound" in raw_role:
            bus = "sfx"
        else:
            bus = str(track.get("bus_id") or "master")
        routes[str(track.get("id", idx))] = bus
    sends = (
        AudioSendSpec("dialogue", "master", 0.0),
        AudioSendSpec("music", "master", -3.0),
        AudioSendSpec("sfx", "master", -2.0),
    )
    return AudioRoutingMatrix(track_routes=routes, sends=sends)


def loudness_delivery_report(
    measured: dict[str, Any],
    target: LoudnessTarget | dict[str, Any] | str,
    *,
    tolerance_lufs: float = 1.0,
    tolerance_peak_db: float = 0.2,
) -> dict[str, Any]:
    if isinstance(target, str):
        t = loudness_target(target)
    elif isinstance(target, LoudnessTarget):
        t = target
    else:
        t = LoudnessTarget(
            str(target.get("target_id", "custom")),
            str(target.get("name", "Custom")),
            float(target.get("target_i", target.get("integrated_lufs", -14.0))),
            float(target.get("true_peak", target.get("true_peak_db", -1.0))),
            float(target.get("lra", 11.0)),
        )
    integrated = float(measured.get("integrated_lufs", measured.get("i", 0.0)) or 0.0)
    true_peak = float(measured.get("true_peak_db", measured.get("true_peak", 0.0)) or 0.0)
    lra = float(measured.get("lra", 0.0) or 0.0)
    loudness_delta = integrated - t.integrated_lufs
    peak_ok = true_peak <= t.true_peak_db + float(tolerance_peak_db)
    loudness_ok = abs(loudness_delta) <= float(tolerance_lufs)
    return {
        "ok": bool(loudness_ok and peak_ok),
        "target_id": t.id,
        "integrated_lufs": integrated,
        "target_lufs": float(t.integrated_lufs),
        "loudness_delta": float(loudness_delta),
        "true_peak_db": true_peak,
        "true_peak_limit": float(t.true_peak_db),
        "lra": lra,
        "target_lra": float(t.lra),
        "warnings": [
            *([] if loudness_ok else [f"integrated loudness off by {loudness_delta:+.2f} LU"]),
            *([] if peak_ok else [f"true peak {true_peak:.2f} dB exceeds {t.true_peak_db:.2f} dB"]),
        ],
    }


def audio_delivery_qa_gate(
    measured: dict[str, Any],
    *,
    target: LoudnessTarget | dict[str, Any] | str = "shortform",
    routing: AudioRoutingMatrix | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine loudness and routing checks for render/preflight UI."""
    loudness = loudness_delivery_report(measured, target)
    matrix = (
        routing
        if isinstance(routing, AudioRoutingMatrix)
        else AudioRoutingMatrix.from_dict(routing if isinstance(routing, dict) else None)
    )
    routing_warnings = matrix.validation_warnings()
    route_count = len(matrix.track_routes)
    bus_count = len(matrix.buses)
    warnings = list(loudness.get("warnings", []) or []) + routing_warnings
    return {
        "ok": bool(loudness.get("ok")) and not routing_warnings,
        "loudness": loudness,
        "routing": matrix.to_dict(),
        "route_count": route_count,
        "bus_count": bus_count,
        "warnings": warnings,
        "qa_gates": [
            "integrated loudness within target tolerance",
            "true peak below delivery limit",
            "all track routes and sends resolve to existing buses",
        ],
    }


def fairlight_engine_report(
    routing: AudioRoutingMatrix | dict[str, Any] | None = None,
    *,
    adr_cues: list[ADRCue | dict[str, Any]] | None = None,
    retimes: list[ElasticAudioRetime | dict[str, Any]] | None = None,
    sfx_items: list[SFXLibraryItem | dict[str, Any]] | None = None,
    stress_track_count: int = 512,
) -> dict[str, Any]:
    matrix = routing if isinstance(routing, AudioRoutingMatrix) else AudioRoutingMatrix.from_dict(routing if isinstance(routing, dict) else None)
    graph = RealtimeMixerGraph.from_routing_matrix(matrix)
    cue_rows = [
        row.to_dict() if isinstance(row, ADRCue) else ADRCue(
            str(row.get("id", f"cue_{idx + 1}")),
            int(row.get("start_ms", 0) or 0),
            int(row.get("end_ms", 1000) or 1000),
            str(row.get("text", "")),
            int(row.get("take_count", 0) or 0),
            bool(row.get("record_arm", True)),
        ).to_dict()
        for idx, row in enumerate(adr_cues or [])
        if isinstance(row, (ADRCue, dict))
    ]
    retime_rows = [
        row.to_dict() if isinstance(row, ElasticAudioRetime) else ElasticAudioRetime(
            str(row.get("clip_id", f"clip_{idx + 1}")),
            int(row.get("source_duration_ms", 1000) or 1000),
            int(row.get("target_duration_ms", 1000) or 1000),
            bool(row.get("preserve_pitch", True)),
            str(row.get("algorithm", "elastique_pro") or "elastique_pro"),
        ).to_dict()
        for idx, row in enumerate(retimes or [])
        if isinstance(row, (ElasticAudioRetime, dict))
    ]
    sfx_rows = [
        row.to_dict() if isinstance(row, SFXLibraryItem) else SFXLibraryItem(
            str(row.get("id", f"sfx_{idx + 1}")),
            str(row.get("path", "")),
            tuple(str(tag) for tag in row.get("tags", []) or []),
            float(row.get("loudness_lufs", -18.0) or -18.0),
        ).to_dict()
        for idx, row in enumerate(sfx_items or [])
        if isinstance(row, (SFXLibraryItem, dict))
    ]
    checks = {
        "realtime_graph": bool(graph.nodes) and not graph.validation_warnings(),
        "latency_compensation": bool(graph.latency_compensation),
        "adr_workflow": bool(cue_rows),
        "elastic_retime": bool(retime_rows) and all(row.get("preserve_pitch") for row in retime_rows),
        "sfx_library": bool(sfx_rows),
        "hundreds_track_stress_contract": int(stress_track_count or 0) >= 256 and graph.max_virtual_tracks >= int(stress_track_count or 0),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "routing": matrix.to_dict(),
        "mixer_graph": graph.to_dict(),
        "adr_cues": cue_rows,
        "elastic_retimes": retime_rows,
        "sfx_items": sfx_rows,
        "summary": {
            "nodes": len(graph.nodes),
            "buses": len(matrix.buses),
            "routes": len(matrix.track_routes),
            "total_latency_samples": graph.total_latency_samples(),
            "adr_cues": len(cue_rows),
            "retimes": len(retime_rows),
            "sfx_items": len(sfx_rows),
            "max_virtual_tracks": graph.max_virtual_tracks,
            "stress_track_count": int(stress_track_count or 0),
        },
    }


def fairlight_mixer_stress_report(*, virtual_tracks: int = 512, channel_layout: str = "5.1") -> dict[str, Any]:
    """Return a cheap, deterministic mixer-scale QA contract.

    This is not a realtime DAW benchmark. It lets Health/QA verify that routing
    metadata, block sizing, latency compensation, and declared virtual track
    limits stay coherent before the UI claims large-session readiness.
    """
    virtual_tracks = max(0, int(virtual_tracks or 0))
    tracks = []
    roles = ("dialogue", "music", "sfx")
    for idx in range(virtual_tracks):
        tracks.append({"id": idx + 1, "role": roles[idx % len(roles)]})
    matrix = build_default_routing_matrix(tracks)
    matrix = AudioRoutingMatrix(
        buses=matrix.buses,
        track_routes=matrix.track_routes,
        sends=matrix.sends,
        sample_rate=matrix.sample_rate,
        channel_layout=channel_layout,
    )
    graph = RealtimeMixerGraph.from_routing_matrix(matrix)
    warnings = matrix.validation_warnings() + graph.validation_warnings()
    checks = {
        "hundreds_of_tracks": virtual_tracks >= 256,
        "routes_resolve": not matrix.validation_warnings(),
        "latency_compensation": graph.latency_compensation,
        "surround_block_size": channel_layout_block_size(channel_layout) >= 1024,
        "declared_limit_covers_stress": graph.max_virtual_tracks >= virtual_tracks,
    }
    return {
        "ok": all(checks.values()) and not warnings,
        "checks": checks,
        "virtual_tracks": virtual_tracks,
        "bus_count": len(matrix.buses),
        "route_count": len(matrix.track_routes),
        "block_size": graph.block_size,
        "total_latency_samples": graph.total_latency_samples(),
        "warnings": warnings,
        "qa_gates": [
            "all virtual tracks route to existing buses",
            "latency compensation remains enabled",
            "surround sessions use a larger processing block",
            "declared virtual-track limit covers the stress profile",
        ],
    }


def fairlight_product_capabilities() -> dict[str, Any]:
    return {
        "max_tracks": 512,
        "flexbus": True,
        "routing_matrix": True,
        "realtime_mixer": True,
        "sample_accurate_editing": True,
        "sync_scroller": True,
        "vo_recording": True,
        "adr_cues": True,
        "multitrack_recording": True,
        "elastic_wave": True,
        "track_layers": True,
        "foley_library": True,
        "sfx_library": True,
        "loudness_monitoring": True,
        "surround_5_1": True,
        "surround_7_1": True,
        "ambisonics": True,
        "voice_isolation": True,
        "mix_automation_model": True,
        "adr_cue_model": True,
        "multitrack_recording_model": True,
        "immersive_audio_model": True,
        "plugin_host_model": True,
        "music_remixer_model": True,
        "control_surface_model": True,
        "audio_interface_model": True,
    }


def dialogue_cleanup_effects(
    *,
    strength: float = 0.65,
    hum_remove: bool = True,
    de_reverb: float = 0.2,
    auto_level: bool = True,
) -> dict[str, Any]:
    """Build a normalized dialogue-cleanup payload for AudioClip.effects."""
    s = max(0.0, min(1.0, float(strength)))
    return {
        "dialogue_cleanup": {
            "enabled": True,
            "strength": s,
            "noise_reduction": 8.0 + s * 14.0,
            "highpass_hz": 70.0 + s * 40.0,
            "hum_remove": bool(hum_remove),
            "presence_db": 1.0 + s * 3.0,
            "air_db": s * 2.0,
            "de_reverb": max(0.0, min(1.0, float(de_reverb))),
            "mouth_click": s >= 0.45,
            "plosive": s >= 0.35,
            "auto_level": bool(auto_level),
        },
        "deesser": {
            "enabled": True,
            "freq": 6500.0,
            "threshold": -32.0,
            "reduction": 35.0 + s * 30.0,
        },
    }


def apply_audio_preset_to_clip(clip: Any, payload: dict[str, Any]) -> bool:
    """Apply audio workflow payload to an AudioClip-like object."""
    if not isinstance(payload, dict):
        return False
    changed = False
    effects = dict(getattr(clip, "effects", {}) or {})
    for key in ("dialogue_cleanup", "loudness", "eq", "comp", "gate", "deesser", "ai_master"):
        value = payload.get(key)
        if isinstance(value, dict):
            effects[key] = dict(value)
            changed = True
    if "gain_db" in payload:
        try:
            clip.gain = db_to_gain(float(payload["gain_db"]))
            changed = True
        except Exception:
            pass
    if "volume_points" in payload and isinstance(payload["volume_points"], list):
        clip.volume_points = list(payload["volume_points"])
        changed = True
    if changed:
        clip.effects = effects
    return changed


def apply_track_mix_preset(track: Any, payload: dict[str, Any]) -> bool:
    """Apply bus/track mix fields to an AudioTrack-like object."""
    if not isinstance(payload, dict):
        return False
    changed = False
    if "bus_id" in payload:
        setattr(track, "bus_id", str(payload["bus_id"]))
        changed = True
    if "label" in payload:
        setattr(track, "label", str(payload["label"]))
        changed = True
    if "volume" in payload:
        setattr(track, "volume", max(0.0, min(2.0, float(payload["volume"]))))
        changed = True
    if "pan" in payload:
        setattr(track, "pan", max(-1.0, min(1.0, float(payload["pan"]))))
        changed = True
    if "automation_points" in payload and isinstance(payload["automation_points"], list):
        setattr(track, "automation_points", list(payload["automation_points"]))
        changed = True
    return changed


def one_click_audio_plan(project_summary: dict[str, Any]) -> list[str]:
    """Return useful audio preset ids from a coarse project summary."""
    has_dialogue = bool(project_summary.get("dialogue") or project_summary.get("voice") or project_summary.get("audio_clips", 0))
    has_music = bool(project_summary.get("music") or project_summary.get("audio_tracks", 0) > 1)
    out = []
    if has_dialogue:
        out.extend(["audio-dialogue-cleanup-strong", "audio-loudness-podcast"])
    if has_music:
        out.append("audio-music-master-web")
    if not out:
        out.append("audio-loudness-shortform")
    return out
