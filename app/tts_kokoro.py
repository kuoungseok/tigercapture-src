"""Optional local Kokoro TTS provider boundary.

Kokoro is a lightweight local TTS engine, but it still pulls a torch/model
stack. Keep imports lazy and keep installed packages under external/tools so
the editor can start without the runtime installed.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Mapping

from app.tts_synthesis import VoiceSynthesisResult


KOKORO_PROVIDER_ID = "kokoro_local"
KOKORO_SCHEMA_VERSION = "tigercapture.tts_kokoro.v1"
KOKORO_ENV_ROOT = "TIGERCAPTURE_KOKORO_ROOT"
KOKORO_DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "external" / "tools" / "tts" / "kokoro"
KOKORO_PACKAGE_DIR_NAME = "python"
KOKORO_SAMPLE_RATE = 24000
KOKORO_LICENSE_NOTICE = (
    "Kokoro is an Apache-2.0 open-weight TTS runtime. Install it as an optional "
    "external local provider; generated model/cache files stay under external/tools."
)

KOKORO_VOICE_ROWS: tuple[dict[str, str], ...] = (
    {"id": "af_heart", "label": "Heart - English US Female", "lang_code": "a", "language": "English US"},
    {"id": "af_bella", "label": "Bella - English US Female", "lang_code": "a", "language": "English US"},
    {"id": "af_nicole", "label": "Nicole - English US Female", "lang_code": "a", "language": "English US"},
    {"id": "af_sarah", "label": "Sarah - English US Female", "lang_code": "a", "language": "English US"},
    {"id": "am_michael", "label": "Michael - English US Male", "lang_code": "a", "language": "English US"},
    {"id": "bf_emma", "label": "Emma - English UK Female", "lang_code": "b", "language": "English UK"},
    {"id": "bm_george", "label": "George - English UK Male", "lang_code": "b", "language": "English UK"},
    {"id": "jf_alpha", "label": "Alpha - Japanese Female", "lang_code": "j", "language": "Japanese"},
    {"id": "jf_gongitsune", "label": "Gongitsune - Japanese Female", "lang_code": "j", "language": "Japanese"},
    {"id": "jm_kumo", "label": "Kumo - Japanese Male", "lang_code": "j", "language": "Japanese"},
    {"id": "ef_dora", "label": "Dora - Spanish Female", "lang_code": "e", "language": "Spanish"},
    {"id": "ff_siwis", "label": "Siwis - French Female", "lang_code": "f", "language": "French"},
    {"id": "if_sara", "label": "Sara - Italian Female", "lang_code": "i", "language": "Italian"},
    {"id": "pf_dora", "label": "Dora - Portuguese Female", "lang_code": "p", "language": "Portuguese"},
)


@dataclass(frozen=True)
class KokoroInstallStatus:
    root: str
    exists: bool
    valid: bool
    package_path: str = ""
    python_path: str = ""
    cache_path: str = ""
    install_mode: str = ""
    version: str = ""
    voice_count: int = 0
    voice_names: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "exists": bool(self.exists),
            "valid": bool(self.valid),
            "package_path": self.package_path,
            "python_path": self.python_path,
            "cache_path": self.cache_path,
            "install_mode": self.install_mode,
            "version": self.version,
            "model_count": int(self.voice_count),
            "model_names": list(self.voice_names),
            "voice_count": int(self.voice_count),
            "voice_names": list(self.voice_names),
            "voice_rows": [dict(row) for row in KOKORO_VOICE_ROWS],
            "missing": list(self.missing),
        }


def _path_text(value: Any) -> str:
    return str(value or "").strip().strip('"')


def kokoro_default_root() -> Path:
    return KOKORO_DEFAULT_ROOT


def kokoro_package_path(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser() if root else KOKORO_DEFAULT_ROOT
    return base / KOKORO_PACKAGE_DIR_NAME


def kokoro_venv_python_path(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser() if root else KOKORO_DEFAULT_ROOT
    return base / ".venv" / "Scripts" / "python.exe"


def kokoro_venv_site_packages(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser() if root else KOKORO_DEFAULT_ROOT
    return base / ".venv" / "Lib" / "site-packages"


def kokoro_cache_path(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser() if root else KOKORO_DEFAULT_ROOT
    return base / "hf_cache"


def _candidate_root(env: Mapping[str, str] | None = None, root: str | Path | None = None) -> Path:
    if root not in ("", None):
        return Path(root).expanduser()
    source = env if env is not None else os.environ
    explicit = _path_text(source.get(KOKORO_ENV_ROOT) if source is not None else "")
    return Path(explicit).expanduser() if explicit else KOKORO_DEFAULT_ROOT


def _dist_version(package_dir: Path) -> str:
    try:
        for dist in sorted(package_dir.glob("kokoro-*.dist-info")):
            metadata = dist / "METADATA"
            if not metadata.exists():
                continue
            for line in metadata.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.lower().startswith("version:"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        return ""
    return ""


def kokoro_root_status(root: str | Path | None = None, env: Mapping[str, str] | None = None) -> KokoroInstallStatus:
    path = _candidate_root(env, root)
    package_dir = kokoro_package_path(path)
    venv_python = kokoro_venv_python_path(path)
    venv_packages = kokoro_venv_site_packages(path)
    cache_dir = kokoro_cache_path(path)
    missing: list[str] = []
    if not path.exists():
        missing.append("root")
    target_has_kokoro = (package_dir / "kokoro").exists()
    target_has_soundfile = (package_dir / "soundfile.py").exists() or (package_dir / "soundfile").exists()
    venv_has_kokoro = (venv_packages / "kokoro").exists()
    venv_has_soundfile = (venv_packages / "soundfile.py").exists() or (venv_packages / "soundfile").exists()
    has_target_runtime = package_dir.exists() and target_has_kokoro and target_has_soundfile
    has_venv_runtime = venv_python.exists() and venv_has_kokoro and venv_has_soundfile
    if not has_target_runtime and not has_venv_runtime:
        if not venv_python.exists() and not package_dir.exists():
            missing.append(".venv/Scripts/python.exe or python/")
    if not target_has_kokoro and not venv_has_kokoro:
        missing.append("kokoro package")
    if not target_has_soundfile and not venv_has_soundfile:
        missing.append("soundfile package")
    valid = path.exists() and (has_target_runtime or has_venv_runtime)
    install_mode = "venv" if has_venv_runtime else ("target" if has_target_runtime else "")
    active_package_dir = venv_packages if has_venv_runtime else package_dir
    voices = tuple(row["id"] for row in KOKORO_VOICE_ROWS)
    return KokoroInstallStatus(
        root=str(path),
        exists=path.exists(),
        valid=bool(valid),
        package_path=str(active_package_dir) if active_package_dir.exists() else "",
        python_path=str(venv_python) if venv_python.exists() else "",
        cache_path=str(cache_dir),
        install_mode=install_mode,
        version=_dist_version(active_package_dir) if active_package_dir.exists() else "",
        voice_count=len(voices) if valid else 0,
        voice_names=voices if valid else (),
        missing=tuple(missing),
    )


def kokoro_provider_status(env: Mapping[str, str] | None = None, root: str | Path | None = None) -> dict[str, Any]:
    status = kokoro_root_status(root, env)
    installed = bool(status.valid)
    setup_state = "ready" if installed else ("incomplete_install" if status.exists else "needs_install")
    reason = (
        f"Kokoro local runtime detected with {status.voice_count} selectable voice preset(s)."
        if installed
        else (
            "A partial Kokoro runtime was found; missing " + ", ".join(status.missing)
            if status.exists
            else "Kokoro local runtime is not installed under external/tools/tts/kokoro."
        )
    )
    return {
        "schema": KOKORO_SCHEMA_VERSION,
        "provider_id": KOKORO_PROVIDER_ID,
        "label": "Kokoro",
        "kind": "tts",
        "configured": installed,
        "installed": installed,
        "available": installed,
        "setup_needed": not installed,
        "setup_state": setup_state,
        "requires_network": False,
        "local_first": True,
        "requires_server": False,
        "endpoint": "",
        "root": status.to_dict(),
        "reason": reason,
        "server_command": [],
        "supports": [
            "local_tts",
            "subtitle_to_voice",
            "ppt_narration",
            "character_narration",
            "fast_preview_voiceover",
        ],
        "license": {
            "engine": "Kokoro",
            "license": "Apache-2.0",
            "notice": KOKORO_LICENSE_NOTICE,
            "bundle_policy": "optional_external_runtime",
        },
    }


def kokoro_install_plan(install_root: str | Path | None = None) -> dict[str, Any]:
    target = Path(install_root).expanduser() if install_root else KOKORO_DEFAULT_ROOT
    script = Path(__file__).resolve().parents[1] / "tools" / "install_kokoro_tts.py"
    return {
        "schema": KOKORO_SCHEMA_VERSION,
        "provider_id": KOKORO_PROVIDER_ID,
        "title": "Install Kokoro local TTS",
        "target_root": str(target),
        "requires_network": True,
        "requires_user_consent": True,
        "estimated_download": "Hundreds of MB for Python packages; model cache downloads on first warm-up/synthesis.",
        "license_notice": KOKORO_LICENSE_NOTICE,
        "source": {
            "engine": "Kokoro",
            "repository": "https://github.com/hexgrad/kokoro",
            "model": "https://huggingface.co/hexgrad/Kokoro-82M",
        },
        "steps": [
            {
                "id": "choose_location",
                "label": "Use external/tools/tts/kokoro",
                "description": "Keep the runtime outside the source tree and out of public distribution commits.",
            },
            {
                "id": "install_python_packages",
                "label": "Install Kokoro packages",
                "description": "Create external/tools/tts/kokoro/.venv with Python 3.12 and install kokoro, soundfile, and English/Japanese G2P extras.",
            },
            {
                "id": "warmup_optional",
                "label": "Warm up model cache",
                "description": "Optionally synthesize one short line so model files are cached under external/tools/tts/kokoro/hf_cache.",
            },
            {
                "id": "select_voice",
                "label": "Select provider and voice",
                "description": "Choose Kokoro in Voice Lab, then pick a voice preset such as af_heart or jf_alpha.",
            },
        ],
        "commands": {
            "install": [sys.executable, str(script), "--target", str(target)],
            "install_and_warmup": [sys.executable, str(script), "--target", str(target), "--warmup"],
        },
        "ui_copy": {
            "primary": "Install Kokoro",
            "secondary": "Connect existing Kokoro",
            "safe_default": "Packages and downloaded model cache stay under external/tools on this machine.",
            "why": "Useful as a lightweight local fallback when a Style-Bert-VITS2 sidecar is unavailable.",
        },
        "actions_after_install": [
            {"action": "tts.provider.select", "params": {"provider_id": KOKORO_PROVIDER_ID}},
            {"action": "tts.provider.status", "params": {"provider_id": KOKORO_PROVIDER_ID}},
        ],
    }


def kokoro_install_execution_gate(install_root: str | Path | None = None) -> dict[str, Any]:
    plan = kokoro_install_plan(install_root)
    return {
        "schema": KOKORO_SCHEMA_VERSION,
        "ready_to_execute": True,
        "requires_confirmation": True,
        "destructive": False,
        "network_download": True,
        "long_running": True,
        "title": "Confirm Kokoro local TTS installation",
        "message": (
            "This will download optional Kokoro packages into external/tools/tts/kokoro. "
            "It does not modify existing projects or bundle model files into Git."
        ),
        "plan": plan,
    }


def connect_installed_kokoro(root_path: str | Path) -> dict[str, Any]:
    status = kokoro_root_status(root_path)
    if not status.valid:
        return {
            "schema": KOKORO_SCHEMA_VERSION,
            "ok": False,
            "connected": False,
            "status": status.to_dict(),
            "error": "Selected folder is not a complete Kokoro runtime.",
            "missing": list(status.missing),
        }
    return {
        "schema": KOKORO_SCHEMA_VERSION,
        "ok": True,
        "connected": True,
        "status": status.to_dict(),
    }


def kokoro_voice_rows() -> list[dict[str, str]]:
    return [dict(row) for row in KOKORO_VOICE_ROWS]


def kokoro_language_code_for_voice(voice: str, *, language: str = "") -> str:
    requested = str(language or "").strip().casefold()
    if requested in {"ja", "jp", "japanese"}:
        return "j"
    if requested in {"en-gb", "british", "british english"}:
        return "b"
    if requested in {"es", "spanish"}:
        return "e"
    if requested in {"fr", "french"}:
        return "f"
    if requested in {"it", "italian"}:
        return "i"
    if requested in {"pt", "portuguese", "pt-br", "brazilian portuguese"}:
        return "p"
    voice_id = str(voice or "").strip()
    for row in KOKORO_VOICE_ROWS:
        if row["id"] == voice_id:
            return row["lang_code"]
    prefix = voice_id[:2].casefold()
    if prefix in {"bf", "bm"}:
        return "b"
    if prefix in {"jf", "jm"}:
        return "j"
    if prefix in {"ef", "em"}:
        return "e"
    if prefix in {"ff", "fm"}:
        return "f"
    if prefix in {"if", "im"}:
        return "i"
    if prefix in {"pf", "pm"}:
        return "p"
    return "a"


@contextmanager
def _kokoro_runtime_path(root: str | Path | None = None) -> Iterable[None]:
    package_dir = kokoro_package_path(root)
    cache_dir = kokoro_cache_path(root)
    inserted = False
    old_hf_home = os.environ.get("HF_HOME")
    old_xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if package_dir.exists():
        package_text = str(package_dir)
        if package_text not in sys.path:
            sys.path.insert(0, package_text)
            inserted = True
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(cache_dir)
    os.environ["XDG_CACHE_HOME"] = str(cache_dir)
    try:
        yield
    finally:
        if inserted:
            try:
                sys.path.remove(str(package_dir))
            except ValueError:
                pass
        if old_hf_home is None:
            os.environ.pop("HF_HOME", None)
        else:
            os.environ["HF_HOME"] = old_hf_home
        if old_xdg_cache is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = old_xdg_cache


def _audio_to_numpy(audio: Any) -> Any:
    try:
        if hasattr(audio, "detach"):
            audio = audio.detach()
        if hasattr(audio, "cpu"):
            audio = audio.cpu()
        if hasattr(audio, "numpy"):
            return audio.numpy()
    except Exception:
        pass
    return audio


def _concat_audio(chunks: list[Any]) -> Any:
    if not chunks:
        raise RuntimeError("Kokoro returned no audio chunks")
    if len(chunks) == 1:
        return chunks[0]
    try:
        import numpy as np

        return np.concatenate(chunks)
    except Exception:
        return chunks[0]


def synthesize_kokoro_voice(
    *,
    text: str,
    output_path: str | Path,
    voice: str = "af_heart",
    language: str = "",
    speed: float = 1.0,
    root: str | Path | None = None,
    timeout_s: float = 120.0,
) -> VoiceSynthesisResult:
    body_text = str(text or "").strip()
    if not body_text:
        raise ValueError("TTS text is empty")
    selected_voice = str(voice or "af_heart").strip() or "af_heart"
    install_status = kokoro_root_status(root)
    if not install_status.valid:
        raise RuntimeError(
            "Kokoro runtime is not installed. Use Voice Lab > Engine > Kokoro > Install first. "
            f"Missing: {', '.join(install_status.missing)}"
        )

    out = Path(output_path).expanduser()
    if not out.is_absolute():
        out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    lang_code = kokoro_language_code_for_voice(selected_voice, language=language)
    if install_status.install_mode == "venv" and install_status.python_path:
        helper = Path(__file__).resolve().parents[1] / "tools" / "kokoro_synthesize.py"
        command = [
            install_status.python_path,
            str(helper),
            "--root",
            install_status.root,
            "--output",
            str(out),
            "--voice",
            selected_voice,
            "--language",
            lang_code,
            "--speed",
            str(max(0.25, min(4.0, float(speed or 1.0)))),
            "--text",
            body_text,
        ]
        env = dict(os.environ)
        env["HF_HOME"] = install_status.cache_path
        env["XDG_CACHE_HOME"] = install_status.cache_path
        try:
            completed = subprocess.run(
                command,
                cwd=install_status.root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=max(1.0, float(timeout_s or 120.0)),
                check=False,
            )
        except Exception as exc:
            raise RuntimeError(f"Kokoro subprocess failed to start: {exc}") from exc
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"Kokoro synthesis failed: {details}")
        byte_count = out.stat().st_size if out.exists() else 0
        duration_ms = 0
        try:
            from app.audio_tracks import probe_audio_duration_ms

            duration_ms = int(probe_audio_duration_ms(out) or 0)
        except Exception:
            duration_ms = 0
        return VoiceSynthesisResult(
            path=out.resolve(),
            byte_count=int(byte_count),
            duration_ms=max(0, int(duration_ms)),
            endpoint=str(install_status.root),
            model_name=selected_voice,
        )

    with _kokoro_runtime_path(install_status.root):
        try:
            from kokoro import KPipeline
            import soundfile as sf
        except Exception as exc:
            raise RuntimeError(f"Kokoro runtime import failed: {exc}") from exc
        try:
            pipeline = KPipeline(lang_code=lang_code)
            generator = pipeline(
                body_text,
                voice=selected_voice,
                speed=max(0.25, min(4.0, float(speed or 1.0))),
                split_pattern=r"\n+",
            )
            chunks: list[Any] = []
            for _index, _graphemes, audio in generator:
                chunks.append(_audio_to_numpy(audio))
            merged = _concat_audio(chunks)
            sf.write(str(out), merged, KOKORO_SAMPLE_RATE)
            try:
                sample_count = len(merged)
            except Exception:
                sample_count = 0
        except Exception as exc:
            raise RuntimeError(f"Kokoro synthesis failed: {exc}") from exc

    byte_count = out.stat().st_size if out.exists() else 0
    duration_ms = int(round((float(sample_count or 0) / float(KOKORO_SAMPLE_RATE)) * 1000.0)) if sample_count else 0
    try:
        from app.audio_tracks import probe_audio_duration_ms

        duration_ms = int(probe_audio_duration_ms(out) or duration_ms)
    except Exception:
        pass
    return VoiceSynthesisResult(
        path=out.resolve(),
        byte_count=int(byte_count),
        duration_ms=max(0, int(duration_ms)),
        endpoint=str(install_status.root),
        model_name=selected_voice,
    )


def write_kokoro_install_manifest(root: str | Path, payload: Mapping[str, Any]) -> Path:
    target = Path(root).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    manifest = target / "install_manifest.json"
    manifest.write_text(json.dumps(dict(payload), indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


__all__ = [
    "KOKORO_DEFAULT_ROOT",
    "KOKORO_ENV_ROOT",
    "KOKORO_PROVIDER_ID",
    "KOKORO_SCHEMA_VERSION",
    "connect_installed_kokoro",
    "kokoro_cache_path",
    "kokoro_default_root",
    "kokoro_install_execution_gate",
    "kokoro_install_plan",
    "kokoro_language_code_for_voice",
    "kokoro_package_path",
    "kokoro_provider_status",
    "kokoro_root_status",
    "kokoro_venv_python_path",
    "kokoro_voice_rows",
    "synthesize_kokoro_voice",
    "write_kokoro_install_manifest",
]
