"""Production music renderer router for TigerCapture Music Lab.

The renderer contract is intentionally tiny:

    --composition-json <request.json> --output-wav <mix.wav>

This router tries configured AI music providers first. If none are available,
it falls back to the local LMMS bridge so Music Lab remains usable offline.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from lmms_music_renderer import render_with_lmms


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "external" / "tools" / "music_renderer" / "provider.json"
DEFAULT_ACE_URL = "http://127.0.0.1:8001"
DEFAULT_STABLE_AUDIO_3_SPACE = "stabilityai/stable-audio-3"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return row if isinstance(row, dict) else {}


def _request_row(composition_json: Path) -> dict[str, Any]:
    row = _load_json(composition_json)
    composition = row.get("composition")
    if not isinstance(composition, dict):
        raise ValueError("composition-json must contain a composition object")
    return row


def _composition(row: dict[str, Any]) -> dict[str, Any]:
    composition = row.get("composition")
    if not isinstance(composition, dict):
        raise ValueError("composition-json must contain a composition object")
    return composition


def build_ai_music_prompt(composition: dict[str, Any]) -> str:
    sections = []
    for section in list(composition.get("sections") or [])[:8]:
        if not isinstance(section, dict):
            continue
        chords = "-".join(str(chord) for chord in list(section.get("chord_progression") or [])[:4] if str(chord).strip())
        label = str(section.get("name") or "section")
        duration = float(section.get("duration_ms") or 0) / 1000.0
        sections.append(f"{label} {duration:.1f}s {chords}".strip())
    track_roles = [
        str(track.get("role") or "")
        for track in list(composition.get("tracks") or [])
        if isinstance(track, dict) and str(track.get("role") or "").strip()
    ]
    base_prompt = str(composition.get("prompt") or "instrumental creator background music").strip()
    genre = str(composition.get("genre") or "electronic").strip()
    mood = str(composition.get("mood") or "confident").strip()
    bpm = int(composition.get("bpm") or 120)
    key = str(composition.get("key") or "C minor").strip()
    duration_s = max(10.0, float(composition.get("duration_ms") or 30000) / 1000.0)
    prompt_parts = [
        base_prompt,
        f"instrumental {genre} music",
        f"{mood} mood",
        f"{bpm} BPM",
        f"key {key}",
        f"{duration_s:.0f} seconds",
        "modern produced stereo mix, full arrangement, polished drums, bass, chords, lead, transitions",
    ]
    if sections:
        prompt_parts.append("song form: " + "; ".join(sections))
    if track_roles:
        prompt_parts.append("arrangement roles: " + ", ".join(track_roles[:12]))
    return ". ".join(part for part in prompt_parts if part)


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None, *, timeout: float = 10.0, token: str = "") -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if not raw:
        return {}
    parsed = json.loads(raw.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _ace_base_url(config: dict[str, Any]) -> str:
    return str(
        os.environ.get("TIGERCAPTURE_ACESTEP_API_URL")
        or config.get("base_url")
        or DEFAULT_ACE_URL
    ).rstrip("/")


def _ace_token(config: dict[str, Any]) -> str:
    return str(os.environ.get("TIGERCAPTURE_ACESTEP_API_KEY") or config.get("api_key") or "").strip()


def _ace_health(config: dict[str, Any]) -> bool:
    try:
        _http_json("GET", _ace_base_url(config) + "/health", timeout=float(config.get("health_timeout_sec") or 1.0), token=_ace_token(config))
        return True
    except Exception:
        return False


def _ace_parse_task_id(row: dict[str, Any]) -> str:
    data = row.get("data")
    if isinstance(data, dict):
        return str(data.get("task_id") or "").strip()
    return ""


def _ace_result_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    data = row.get("data")
    if isinstance(data, dict):
        data = [data]
    rows = data if isinstance(data, list) else []
    parsed: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        result = item.get("result")
        if isinstance(result, str) and result.strip():
            try:
                loaded = json.loads(result)
            except Exception:
                loaded = []
            if isinstance(loaded, dict):
                parsed.append(loaded)
            elif isinstance(loaded, list):
                parsed.extend(row for row in loaded if isinstance(row, dict))
        else:
            parsed.append(item)
    return parsed


def _download_ace_audio(base_url: str, file_url: str, output_wav: Path, *, token: str = "", timeout: float = 120.0) -> None:
    if file_url.startswith("http://") or file_url.startswith("https://"):
        url = file_url
    else:
        url = base_url + file_url if file_url.startswith("/") else base_url + "/v1/audio?path=" + urllib.parse.quote(file_url, safe="")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        output_wav.write_bytes(response.read())


def _first_existing_path(value: Any) -> Path | None:
    if isinstance(value, (str, os.PathLike)):
        path = Path(value)
        return path if path.exists() else None
    if isinstance(value, dict):
        for key in ("path", "name", "file", "value"):
            found = _first_existing_path(value.get(key))
            if found:
                return found
        for item in value.values():
            found = _first_existing_path(item)
            if found:
                return found
    if isinstance(value, (list, tuple)):
        for item in value:
            found = _first_existing_path(item)
            if found:
                return found
    return None


def _stable_audio_3_space(config: dict[str, Any]) -> str:
    return str(
        os.environ.get("TIGERCAPTURE_STABLE_AUDIO_3_SPACE")
        or config.get("space")
        or DEFAULT_STABLE_AUDIO_3_SPACE
    ).strip()


def render_stable_audio_3_hf_space(request_row: dict[str, Any], output_wav: Path, config: dict[str, Any]) -> dict[str, Any]:
    try:
        from gradio_client import Client
    except Exception as exc:
        raise RuntimeError("Stable Audio 3.0 Hugging Face Space requires the gradio_client package.") from exc

    composition = _composition(request_row)
    duration_s = max(
        float(config.get("min_duration_s") or 8.0),
        min(float(config.get("max_duration_s") or 120.0), float(composition.get("duration_ms") or 30000) / 1000.0),
    )
    prompt = build_ai_music_prompt(composition)
    suffix = str(config.get("prompt_suffix") or "").strip()
    if suffix:
        prompt = f"{prompt}. {suffix}"
    variant_key = str(config.get("variant_key") or "small-music")
    steps = int(config.get("steps") or 8)
    cfg_scale = float(config.get("cfg_scale") or 1.0)
    sampler_type = str(config.get("sampler_type") or "pingpong")
    seed = int(os.environ.get("TIGERCAPTURE_STABLE_AUDIO_3_SEED") or config.get("seed") or 0)
    space = _stable_audio_3_space(config)
    client = Client(space)
    result = client.predict(
        variant_key=variant_key,
        prompt=prompt,
        duration=duration_s,
        steps=steps,
        cfg_scale=cfg_scale,
        sampler_type=sampler_type,
        seed=seed,
        api_name="/infer",
    )
    generated_path = _first_existing_path(result)
    if not generated_path:
        raise RuntimeError(f"Stable Audio 3.0 did not return a downloadable file: {result!r}")
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(generated_path, output_wav)
    return {
        "provider": "stable_audio_3",
        "provider_engine": f"Stable Audio 3.0 HF Space/{variant_key}",
        "space": space,
        "variant_key": variant_key,
        "prompt": prompt,
        "duration_s": duration_s,
        "fallback_used": False,
    }


def render_acestep_api(request_row: dict[str, Any], output_wav: Path, config: dict[str, Any]) -> dict[str, Any]:
    composition = _composition(request_row)
    base_url = _ace_base_url(config)
    token = _ace_token(config)
    duration_s = max(10.0, min(600.0, float(composition.get("duration_ms") or 30000) / 1000.0))
    payload: dict[str, Any] = {
        "prompt": build_ai_music_prompt(composition),
        "lyrics": str(config.get("lyrics") or ""),
        "audio_format": str(config.get("audio_format") or "wav"),
        "audio_duration": duration_s,
        "bpm": int(composition.get("bpm") or 120),
        "key_scale": str(composition.get("key") or ""),
        "time_signature": "4",
        "thinking": bool(config.get("thinking", True)),
        "use_random_seed": bool(config.get("use_random_seed", True)),
        "batch_size": int(config.get("batch_size") or 1),
        "inference_steps": int(config.get("inference_steps") or 8),
    }
    if config.get("model"):
        payload["model"] = str(config.get("model"))
    if config.get("seed") is not None:
        payload["seed"] = int(config.get("seed"))
        payload["use_random_seed"] = False
    if token:
        payload["ai_token"] = token
    submit = _http_json("POST", base_url + "/release_task", payload, timeout=float(config.get("submit_timeout_sec") or 30.0), token=token)
    task_id = _ace_parse_task_id(submit)
    if not task_id:
        raise RuntimeError(f"ACE-Step did not return a task_id: {submit}")
    deadline = time.time() + float(config.get("timeout_sec") or 900.0)
    poll_interval = max(1.0, float(config.get("poll_interval_sec") or 3.0))
    last_payload: dict[str, Any] = {}
    while time.time() < deadline:
        time.sleep(poll_interval)
        query = _http_json(
            "POST",
            base_url + "/query_result",
            {"task_id_list": [task_id]},
            timeout=float(config.get("query_timeout_sec") or 30.0),
            token=token,
        )
        last_payload = query
        result_rows = _ace_result_rows(query)
        for row in result_rows:
            status = int(row.get("status") if row.get("status") is not None else 0)
            if status == 2:
                raise RuntimeError(f"ACE-Step generation failed: {row}")
            if status == 1 and str(row.get("file") or "").strip():
                _download_ace_audio(base_url, str(row.get("file")), output_wav, token=token, timeout=float(config.get("download_timeout_sec") or 180.0))
                return {
                    "provider": "acestep_api",
                    "provider_engine": str(row.get("dit_model") or config.get("model") or "ACE-Step"),
                    "task_id": task_id,
                    "prompt": payload["prompt"],
                    "duration_s": duration_s,
                    "fallback_used": False,
                }
    raise TimeoutError(f"ACE-Step generation timed out for task {task_id}: {last_payload}")


def _write_meta(output_wav: Path, payload: dict[str, Any]) -> None:
    meta_path = output_wav.with_suffix(output_wav.suffix + ".renderer.json")
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def render_production_music(composition_json: Path, output_wav: Path, *, config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    request_row = _request_row(composition_json)
    config = _load_json(config_path)
    request_provider = request_row.get("ai_provider") or request_row.get("provider")
    provider = str(
        os.environ.get("TIGERCAPTURE_MUSIC_AI_PROVIDER")
        or request_provider
        or config.get("preferred_provider")
        or "auto"
    ).strip().lower()
    providers = config.get("providers") if isinstance(config.get("providers"), dict) else {}
    stable_config = providers.get("stable_audio_3") if isinstance(providers.get("stable_audio_3"), dict) else {}
    ace_config = providers.get("acestep_api") if isinstance(providers.get("acestep_api"), dict) else {}
    strict = str(os.environ.get("TIGERCAPTURE_MUSIC_AI_STRICT") or config.get("strict") or "").strip().lower() in {"1", "true", "yes"}
    fallback_reason = ""
    stable_explicit = provider in {"stable_audio", "stable_audio_3", "stable_audio_3_hf_space", "sa3"}
    should_try_stable = provider in {"auto", "ai", "stable_audio", "stable_audio_3", "stable_audio_3_hf_space", "sa3"} and (
        stable_explicit or bool(stable_config.get("enabled"))
    )
    if should_try_stable:
        try:
            if str(stable_config.get("mode") or "huggingface_space") != "huggingface_space":
                raise RuntimeError(f"Unsupported Stable Audio 3.0 mode: {stable_config.get('mode')}")
            meta = render_stable_audio_3_hf_space(request_row, output_wav, stable_config)
            _write_meta(output_wav, {"schema": "tigerstudio.music.renderer_meta.v1", **meta})
            return meta
        except Exception as exc:
            fallback_reason = str(exc)
            if strict or provider in {"stable_audio", "stable_audio_3", "stable_audio_3_hf_space", "sa3"}:
                raise
    should_try_ace = provider in {"auto", "ai", "acestep", "acestep_api"} and bool(ace_config.get("enabled", provider in {"acestep", "acestep_api"}))
    if should_try_ace:
        try:
            if not _ace_health(ace_config):
                raise RuntimeError(f"ACE-Step API is not healthy at {_ace_base_url(ace_config)}")
            meta = render_acestep_api(request_row, output_wav, ace_config)
            _write_meta(output_wav, {"schema": "tigerstudio.music.renderer_meta.v1", **meta})
            return meta
        except Exception as exc:
            fallback_reason = str(exc)
            if strict or provider in {"acestep", "acestep_api"}:
                raise
    keep_project = output_wav.with_suffix(".lmms.mmp") if bool(config.get("keep_lmms_project")) else None
    render_with_lmms(composition_json, output_wav, keep_project=keep_project)
    meta = {
        "provider": "lmms",
        "provider_engine": "LMMS",
        "fallback_used": bool(fallback_reason),
        "fallback_reason": fallback_reason,
        "prompt": build_ai_music_prompt(_composition(request_row)),
    }
    _write_meta(output_wav, {"schema": "tigerstudio.music.renderer_meta.v1", **meta})
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Route Music Lab production rendering to AI providers or LMMS fallback.")
    parser.add_argument("--composition-json", required=True, type=Path)
    parser.add_argument("--output-wav", required=True, type=Path)
    parser.add_argument("--provider-config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args(argv)
    meta = render_production_music(args.composition_json, args.output_wav, config_path=args.provider_config)
    print(json.dumps({"output_wav": str(args.output_wav), **meta}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
