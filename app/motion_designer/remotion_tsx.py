"""Linked Remotion-style TSX sources backed by Tiger's compatibility runtime."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

from .schema import MotionLayer, SourceRef


REMOTION_TSX_SOURCE_KIND = "remotion_tsx"
REMOTION_TSX_RUNTIME_VERSION = 1
DEFAULT_REMOTION_TSX_DURATION_MS = 5000
MAX_REMOTION_TSX_DURATION_FRAMES = 1800
_ALLOWED_IMPORTS = {"react", "react/jsx-runtime", "remotion", "next/image"}
_IMPORT_PATTERN = re.compile(
    r"(?:import\s+(?:[^;]+?)\s+from\s+|import\s*)[\"']([^\"']+)[\"']"
)


@dataclass(frozen=True, slots=True)
class RemotionTsxInspection:
    path: str
    ok: bool
    source_sha256: str
    size: int
    imports: tuple[str, ...]
    unsupported_imports: tuple[str, ...]
    hooks: tuple[str, ...]
    has_default_export: bool
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "tigerstudio.motion.remotion_tsx.inspection.v1",
            "path": self.path,
            "ok": self.ok,
            "source_sha256": self.source_sha256,
            "size": self.size,
            "imports": list(self.imports),
            "unsupported_imports": list(self.unsupported_imports),
            "hooks": list(self.hooks),
            "has_default_export": self.has_default_export,
            "warnings": list(self.warnings),
            "source_preserved": True,
            "execution_policy": "explicit_trust_required",
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_remotion_tsx(path: str | Path) -> RemotionTsxInspection:
    source = Path(path).expanduser().resolve(strict=False)
    if source.suffix.lower() not in {".tsx", ".jsx"}:
        raise ValueError("Remotion source must be a .tsx or .jsx file")
    if not source.is_file():
        raise FileNotFoundError(source)
    text = source.read_text(encoding="utf-8-sig")
    imports = tuple(sorted(set(_IMPORT_PATTERN.findall(text))))
    unsupported = tuple(sorted(
        item for item in imports
        if item not in _ALLOWED_IMPORTS and not item.startswith(("./", "../"))
    ))
    hooks = tuple(name for name in (
        "useCurrentFrame", "useVideoConfig", "interpolate", "spring", "random",
    ) if re.search(rf"\b{re.escape(name)}\b", text))
    has_default_export = bool(re.search(r"\bexport\s+default\b", text))
    warnings: list[str] = []
    if unsupported:
        warnings.append("External imports require an additional trusted runtime package.")
    if not has_default_export:
        warnings.append("A default-exported React component is required.")
    if re.search(r"\b(?:eval|Function)\s*\(", text):
        warnings.append("Dynamic code execution was detected and is blocked by policy.")
    blocked_dynamic_code = any("Dynamic code execution" in row for row in warnings)
    return RemotionTsxInspection(
        path=str(source),
        ok=has_default_export and not unsupported and not blocked_dynamic_code,
        source_sha256=_sha256(source),
        size=source.stat().st_size,
        imports=imports,
        unsupported_imports=unsupported,
        hooks=hooks,
        has_default_export=has_default_export,
        warnings=tuple(warnings),
    )


def runtime_root() -> Path:
    override = str(os.environ.get("TIGER_REMOTION_TSX_RUNTIME") or "").strip()
    if override:
        return Path(override).expanduser().resolve(strict=False)
    repository = Path(__file__).resolve().parents[2]
    if (repository / ".git").exists():
        return repository / "external" / "tools" / "remotion_tsx_runtime"
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return local / "TigerStudio" / f"remotion_tsx_runtime_v{REMOTION_TSX_RUNTIME_VERSION}"


def _scaffold_source() -> Path:
    return Path(__file__).resolve().parents[2] / "resources" / "remotion_tsx_runtime"


def _npm_command() -> str:
    candidate = shutil.which("npm.cmd") or shutil.which("npm")
    return str(candidate or "")


def _node_command() -> str:
    return str(shutil.which("node") or "")


def sync_runtime_scaffold(root: str | Path | None = None) -> Path:
    destination = Path(root).expanduser().resolve(strict=False) if root else runtime_root()
    destination.mkdir(parents=True, exist_ok=True)
    for source in _scaffold_source().iterdir():
        if source.is_file():
            shutil.copy2(source, destination / source.name)
    return destination


def remotion_tsx_runtime_status(root: str | Path | None = None) -> dict[str, Any]:
    destination = Path(root).expanduser().resolve(strict=False) if root else runtime_root()
    packages = {
        name: (destination / "node_modules" / name / "package.json").is_file()
        for name in ("esbuild", "react", "react-dom")
    }
    installed = all(packages.values())
    return {
        "schema": "tigerstudio.motion.remotion_tsx.runtime_status.v1",
        "runtime_root": str(destination),
        "node": _node_command(),
        "npm": _npm_command(),
        "node_available": bool(_node_command()),
        "npm_available": bool(_npm_command()),
        "packages": packages,
        "installed": installed,
        "ready": bool(_node_command()) and installed,
        "runtime": "tiger_react_esbuild_compat",
        "remotion_dependency": False,
    }


def install_remotion_tsx_runtime(
    root: str | Path | None = None,
    *,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    destination = sync_runtime_scaffold(root)
    npm = _npm_command()
    if not npm:
        raise RuntimeError("Node.js/npm is required to install TSX preview support")
    completed = subprocess.run(
        [npm, "install", "--omit=dev", "--no-audit", "--no-fund"],
        cwd=str(destination),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(30, int(timeout_seconds)),
        check=False,
    )
    status = remotion_tsx_runtime_status(destination)
    status.update({
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    })
    if completed.returncode != 0 or not status["ready"]:
        raise RuntimeError(
            "TSX runtime installation failed: "
            + ((completed.stderr or "").strip() or (completed.stdout or "").strip() or "unknown npm error")
        )
    return status


def _job_key(
    inspection: RemotionTsxInspection,
    *,
    width: int,
    height: int,
    fps: float,
    duration_ms: int,
) -> str:
    payload = (
        f"{inspection.source_sha256}:{int(width)}:{int(height)}:"
        f"{float(fps):.6f}:{int(duration_ms)}:v{REMOTION_TSX_RUNTIME_VERSION}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def build_remotion_tsx_page(
    path: str | Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: float = 30.0,
    duration_ms: int = DEFAULT_REMOTION_TSX_DURATION_MS,
    trusted: bool = False,
    root: str | Path | None = None,
) -> dict[str, Any]:
    inspection = inspect_remotion_tsx(path)
    if not inspection.ok:
        raise ValueError("TSX compatibility preflight failed: " + "; ".join(inspection.warnings))
    if not trusted:
        raise PermissionError("TSX execution requires trusted=True after source review")
    sync_runtime_scaffold(root)
    status = remotion_tsx_runtime_status(root)
    if not status["ready"]:
        raise RuntimeError("TSX runtime is not installed")
    destination = Path(status["runtime_root"])
    job = destination / "jobs" / _job_key(
        inspection, width=width, height=height, fps=fps, duration_ms=duration_ms,
    )
    job.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(round(max(1, duration_ms) * max(1.0, fps) / 1000.0)))
    if frames > MAX_REMOTION_TSX_DURATION_FRAMES:
        raise ValueError(
            f"TSX preview is limited to {MAX_REMOTION_TSX_DURATION_FRAMES} frames; "
            "shorten the linked layer or lower its preview FPS"
        )
    command = [
        _node_command(), str(destination / "build.mjs"),
        "--source", inspection.path,
        "--output", str(job),
        "--width", str(max(1, int(width))),
        "--height", str(max(1, int(height))),
        "--fps", str(max(1.0, float(fps))),
        "--frames", str(frames),
    ]
    completed = subprocess.run(
        command, cwd=str(destination), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        timeout=120, check=False,
    )
    if completed.returncode != 0 or not (job / "index.html").is_file():
        raise RuntimeError(
            "TSX bundle failed: "
            + ((completed.stderr or "").strip() or (completed.stdout or "").strip() or "unknown esbuild error")
        )
    manifest = {
        "schema": "tigerstudio.motion.remotion_tsx.job.v1",
        "source": inspection.path,
        "source_sha256": inspection.source_sha256,
        "job_key": job.name,
        "job_dir": str(job),
        "html": str(job / "index.html"),
        "frame_dir": str(job / "frames"),
        "width": max(1, int(width)),
        "height": max(1, int(height)),
        "fps": max(1.0, float(fps)),
        "duration_ms": max(1, int(duration_ms)),
        "duration_frames": frames,
        "source_preserved": True,
    }
    (job / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return manifest


def prepare_remotion_tsx_frames(
    path: str | Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: float = 30.0,
    duration_ms: int = DEFAULT_REMOTION_TSX_DURATION_MS,
    trusted: bool = False,
    root: str | Path | None = None,
) -> dict[str, Any]:
    manifest = build_remotion_tsx_page(
        path, width=width, height=height, fps=fps, duration_ms=duration_ms,
        trusted=trusted, root=root,
    )
    frame_dir = Path(manifest["frame_dir"])
    expected = int(manifest["duration_frames"])
    cached = list(frame_dir.glob("frame_*.png")) if frame_dir.is_dir() else []
    if (
        len(cached) == expected
        and all(item.stat().st_size > 0 for item in cached)
        and (frame_dir / "frame_000000.png").is_file()
        and (frame_dir / f"frame_{expected - 1:06d}.png").is_file()
    ):
        return {
            **manifest,
            "ok": True,
            "frame_count": expected,
            "first_frame": str(frame_dir / "frame_000000.png"),
            "cache_reused": True,
        }
    repository = Path(__file__).resolve().parents[2]
    renderer = repository / "tools" / "render_remotion_tsx_cache.py"
    completed = subprocess.run(
        [
            sys.executable, str(renderer),
            "--manifest", str(Path(manifest["job_dir"]) / "manifest.json"),
        ],
        cwd=str(repository), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        timeout=max(180, int(manifest["duration_frames"]) * 3), check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "TSX frame preparation failed: "
            + ((completed.stderr or "").strip() or (completed.stdout or "").strip() or "unknown renderer error")
        )
    report = json.loads(completed.stdout.strip().splitlines()[-1])
    return {**manifest, **report, "cache_reused": False}


def create_remotion_tsx_layer(
    path: str | Path,
    *,
    width: int,
    height: int,
    duration_ms: int,
    fps: float = 30.0,
    name: str | None = None,
    prepared: dict[str, Any] | None = None,
) -> MotionLayer:
    inspection = inspect_remotion_tsx(path)
    params: dict[str, Any] = {
        "width": max(1, int(width)),
        "height": max(1, int(height)),
        "fps": max(1.0, float(fps)),
        "duration_ms": max(1, int(duration_ms)),
        "source_sha256": inspection.source_sha256,
        "imports": list(inspection.imports),
        "hooks": list(inspection.hooks),
        "source_preserved": True,
        "runtime": "tiger_react_esbuild_compat",
    }
    if prepared:
        params.update({
            "job_key": str(prepared.get("job_key") or ""),
            "frame_dir": str(prepared.get("frame_dir") or ""),
            "duration_frames": int(prepared.get("duration_frames") or 1),
            "prepared_source_sha256": str(prepared.get("source_sha256") or ""),
        })
    layer = MotionLayer(
        name=name or Path(inspection.path).stem,
        layer_type=REMOTION_TSX_SOURCE_KIND,
        source=SourceRef(
            kind=REMOTION_TSX_SOURCE_KIND,
            uri=inspection.path,
            revision=inspection.source_sha256,
            params=params,
            metadata={"linked_source": True, "explicit_trust_required": True},
        ),
        out_ms=max(1, int(duration_ms)),
    )
    layer.transform.position.default = [width * 0.5, height * 0.5]
    return layer


__all__ = [
    "DEFAULT_REMOTION_TSX_DURATION_MS", "MAX_REMOTION_TSX_DURATION_FRAMES",
    "REMOTION_TSX_SOURCE_KIND", "RemotionTsxInspection",
    "build_remotion_tsx_page", "create_remotion_tsx_layer",
    "inspect_remotion_tsx", "install_remotion_tsx_runtime",
    "prepare_remotion_tsx_frames", "remotion_tsx_runtime_status",
    "runtime_root", "sync_runtime_scaffold",
]
