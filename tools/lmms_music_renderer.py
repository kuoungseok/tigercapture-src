"""Render TigerCapture Music Lab compositions through a local LMMS install.

This script implements the production-renderer contract used by
``app.music_composer``:

    --composition-json <request.json> --output-wav <mix.wav>

It converts the structured MusicComposition into a temporary LMMS ``.mmp``
project, then calls ``lmms.exe render``. The first version intentionally uses
LMMS bundled sample instruments so it works without extra commercial assets.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LMMS_TICKS_PER_BEAT = 48
MUSIC_TICKS_PER_BEAT = 480


def _find_lmms_exe() -> Path:
    env_value = os.environ.get("TIGERCAPTURE_LMMS_EXE", "").strip()
    candidates = []
    if env_value:
        candidates.append(Path(env_value).expanduser())
    candidates.extend(
        [
            REPO_ROOT / "external" / "tools" / "lmms" / "app" / "lmms.exe",
            REPO_ROOT / "external" / "tools" / "lmms" / "lmms.exe",
        ]
    )
    which = shutil.which("lmms")
    if which:
        candidates.append(Path(which))
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    raise FileNotFoundError("LMMS executable was not found under external/tools/lmms or TIGERCAPTURE_LMMS_EXE.")


def _music_to_lmms_tick(value: int | float) -> int:
    return max(0, int(round(float(value) * LMMS_TICKS_PER_BEAT / MUSIC_TICKS_PER_BEAT)))


def _role_family(role: str) -> str:
    text = str(role or "").lower()
    if text.startswith(("drums", "orchestral_percussion")):
        return "drums"
    if text.startswith(("bass", "sub_bass", "bass_pulse")):
        return "bass"
    if text.startswith(("chords", "pad", "hybrid_pad", "choir")):
        return "pad"
    if text.startswith(("arp", "melody", "lead", "counter", "woodwinds", "flutes", "oboes", "clarinets")):
        return "lead"
    if text.startswith(("fx", "cymbals")):
        return "fx"
    if text.startswith(("violins", "violas", "cellos", "contrabasses", "strings")):
        return "pad"
    if text.startswith(("brass", "horns", "trumpets", "trombones")):
        return "lead"
    return "pad"


def _sample_for_role(role: str, pitch: int | None = None) -> str:
    family = _role_family(role)
    if family == "drums":
        if pitch == 36:
            return "drums/kick_hard01.ogg"
        if pitch == 38:
            return "drums/snare_electro01.ogg"
        if pitch in {42, 44, 46}:
            return "drums/hihat_closed04.ogg"
        return "drums/clap03.ogg"
    if family == "bass":
        return "basses/bass_hard02.ogg"
    if family == "pad":
        return "stringsnpads/space_strings02.ogg"
    if family == "lead":
        return "instruments/e_piano_accord02.ogg"
    if family == "fx":
        return "effects/filter_sweep01.ogg"
    return "instruments/piano02.ogg"


def _track_splits(track: dict[str, Any]) -> list[tuple[str, str, list[dict[str, Any]]]]:
    role = str(track.get("role") or track.get("id") or "track")
    clips = [clip for clip in list(track.get("clips") or []) if isinstance(clip, dict)]
    family = _role_family(role)
    if family != "drums":
        notes = []
        for clip in clips:
            for note in list(clip.get("notes") or []):
                if isinstance(note, dict):
                    row = dict(note)
                    row["_clip_start_ms"] = int(clip.get("start_ms") or 0)
                    row["_clip_duration_ms"] = int(clip.get("duration_ms") or 1000)
                    notes.append(row)
        return [(role, _sample_for_role(role), notes)]

    buckets: dict[str, tuple[str, list[dict[str, Any]]]] = {
        "kick": (_sample_for_role(role, 36), []),
        "snare": (_sample_for_role(role, 38), []),
        "hat": (_sample_for_role(role, 42), []),
    }
    for clip in clips:
        for note in list(clip.get("notes") or []):
            if not isinstance(note, dict):
                continue
            pitch = int(note.get("pitch") or 0)
            key = "kick" if pitch == 36 else "snare" if pitch == 38 else "hat"
            row = dict(note)
            row["_clip_start_ms"] = int(clip.get("start_ms") or 0)
            row["_clip_duration_ms"] = int(clip.get("duration_ms") or 1000)
            buckets[key][1].append(row)
    return [(f"{role}_{name}", sample, rows) for name, (sample, rows) in buckets.items() if rows]


def _add_envelope(parent: ET.Element) -> None:
    eldata = ET.SubElement(parent, "eldata", {"ftype": "0", "fres": "0.5", "fcut": "14000", "fwet": "0"})
    envelope = {
        "latt": "0",
        "dec": "0.5",
        "lamt": "0",
        "lspd_numerator": "4",
        "att": "0",
        "sustain": "0.5",
        "amt": "0",
        "userwavefile": "",
        "ctlenvamt": "0",
        "lshp": "0",
        "lspd_denominator": "4",
        "x100": "0",
        "lpdel": "0",
        "lspd": "0.1",
        "pdel": "0",
        "hold": "0.5",
        "syncmode": "0",
        "rel": "0.1",
    }
    ET.SubElement(eldata, "elvol", envelope)
    ET.SubElement(eldata, "elcut", envelope)
    ET.SubElement(eldata, "elres", envelope)


def _add_instrument_track(parent: ET.Element, *, name: str, sample: str, volume: float, pan: float, notes: list[dict[str, Any]]) -> None:
    track = ET.SubElement(parent, "track", {"muted": "0", "name": name[:48], "solo": "0", "type": "0"})
    instrument_track = ET.SubElement(
        track,
        "instrumenttrack",
        {
            "pitch": "0",
            "fxch": "0",
            "basenote": "57",
            "usemasterpitch": "1",
            "pitchrange": "1",
            "vol": str(max(10, min(200, int(round(float(volume or 0.8) * 120))))),
            "pan": str(max(-100, min(100, int(round(float(pan or 0.0) * 100))))),
        },
    )
    instrument = ET.SubElement(instrument_track, "instrument", {"name": "audiofileprocessor"})
    ET.SubElement(
        instrument,
        "audiofileprocessor",
        {
            "stutter": "0",
            "interp": "1",
            "reversed": "0",
            "looped": "0",
            "sframe": "0",
            "lframe": "0",
            "src": sample,
            "eframe": "1",
            "amp": "120",
        },
    )
    _add_envelope(instrument_track)
    ET.SubElement(instrument_track, "chordcreator", {"chord": "0", "chordrange": "1", "chord-enabled": "0"})
    ET.SubElement(
        instrument_track,
        "arpeggiator",
        {
            "arp": "0",
            "arptime_numerator": "4",
            "arptime_denominator": "4",
            "arprange": "1",
            "arpmode": "0",
            "arptime": "100",
            "arpdir": "0",
            "arpgate": "100",
            "syncmode": "0",
            "arp-enabled": "0",
        },
    )
    ET.SubElement(
        instrument_track,
        "midiport",
        {
            "outputchannel": "1",
            "outputcontroller": "0",
            "basevelocity": "127",
            "outputprogram": "1",
            "fixedinputvelocity": "-1",
            "fixedoutputvelocity": "-1",
            "fixedoutputnote": "-1",
            "inputchannel": "0",
            "inputcontroller": "0",
            "readable": "0",
            "writable": "0",
        },
    )
    ET.SubElement(instrument_track, "fxchain", {"enabled": "0", "numofeffects": "0"})
    if not notes:
        ET.SubElement(track, "pattern", {"len": "192", "muted": "0", "name": name[:48], "steps": "16", "pos": "0", "type": "0"})
        return
    start = min(_music_to_lmms_tick(note.get("start_tick", 0)) for note in notes)
    end = max(
        _music_to_lmms_tick(int(note.get("start_tick") or 0) + max(1, int(note.get("duration_tick") or MUSIC_TICKS_PER_BEAT // 4)))
        for note in notes
    )
    length = max(48, end - start)
    pattern = ET.SubElement(track, "pattern", {"len": str(length), "muted": "0", "name": name[:48], "steps": "16", "pos": str(start), "type": "1"})
    for note in notes:
        source_pitch = int(note.get("pitch") or 57)
        key = 57 if _role_family(name) == "drums" else max(12, min(108, source_pitch))
        pos = max(0, _music_to_lmms_tick(int(note.get("start_tick") or 0)) - start)
        duration = max(6, _music_to_lmms_tick(max(1, int(note.get("duration_tick") or MUSIC_TICKS_PER_BEAT // 4))))
        velocity = max(10, min(200, int(round(float(note.get("velocity") or 90) * 100.0 / 127.0))))
        ET.SubElement(pattern, "note", {"len": str(duration), "key": str(key), "vol": str(velocity), "pos": str(pos), "pan": "0"})


def build_lmms_project(composition: dict[str, Any]) -> ET.ElementTree:
    root = ET.Element("lmms-project", {"creator": "TigerCapture", "version": "1.0", "type": "song", "creatorversion": "1.2.2"})
    ET.SubElement(
        root,
        "head",
        {
            "timesig_numerator": "4",
            "timesig_denominator": "4",
            "bpm": str(max(48, min(180, int(composition.get("bpm") or 120)))),
            "mastervol": "92",
            "masterpitch": "0",
        },
    )
    song = ET.SubElement(root, "song")
    container = ET.SubElement(
        song,
        "trackcontainer",
        {"maximized": "0", "height": "640", "visible": "1", "minimized": "0", "x": "5", "y": "5", "type": "song", "width": "900"},
    )
    for track in list(composition.get("tracks") or []):
        if not isinstance(track, dict):
            continue
        for split_name, sample, notes in _track_splits(track):
            _add_instrument_track(
                container,
                name=split_name,
                sample=sample,
                volume=float(track.get("volume") or 0.8),
                pan=float(track.get("pan") or 0.0),
                notes=notes,
            )
    return ET.ElementTree(root)


def _composition_from_request(path: Path) -> dict[str, Any]:
    row = json.loads(path.read_text(encoding="utf-8"))
    composition = row.get("composition") if isinstance(row, dict) else None
    if not isinstance(composition, dict):
        raise ValueError("composition-json must contain a composition object")
    return composition


def render_with_lmms(composition_json: Path, output_wav: Path, *, keep_project: Path | None = None) -> Path:
    lmms = _find_lmms_exe()
    composition = _composition_from_request(composition_json)
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tigercapture_lmms_") as tmp:
        project_path = Path(tmp) / f"{composition.get('id') or 'music_lab'}.mmp"
        tree = build_lmms_project(composition)
        tree.write(project_path, encoding="utf-8", xml_declaration=True)
        if keep_project:
            keep_project.parent.mkdir(parents=True, exist_ok=True)
            keep_project.write_bytes(project_path.read_bytes())
        command = [
            str(lmms),
            "render",
            str(project_path),
            "-o",
            str(output_wav),
            "-f",
            "wav",
            "-s",
            "44100",
            "-x",
            "2",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=240.0, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"LMMS render failed ({completed.returncode}): {detail[:1200]}")
    if not output_wav.exists() or output_wav.stat().st_size <= 44:
        raise RuntimeError("LMMS did not produce a usable WAV file")
    return output_wav


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render TigerCapture Music Lab JSON through LMMS.")
    parser.add_argument("--composition-json", required=True, type=Path)
    parser.add_argument("--output-wav", required=True, type=Path)
    parser.add_argument("--keep-project", type=Path)
    args = parser.parse_args(argv)
    render_with_lmms(args.composition_json, args.output_wav, keep_project=args.keep_project)
    print(str(args.output_wav))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
