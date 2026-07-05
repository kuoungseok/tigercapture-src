from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RESULT_PREFIX = "__TIGERCAPTURE_LIVE2D_RESULT__"


CHILD = r"""
import faulthandler
import json
import os
import sys

RESULT_PREFIX = "__TIGERCAPTURE_LIVE2D_RESULT__"

faulthandler.enable()
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PySide6.QtWidgets import QApplication

from app.live2d.actor_track import Live2DActorClip
from app.live2d.compat import moc3_version, model_support_error, normalize_live2d_model_path

source = sys.argv[1]
width = int(sys.argv[2])
height = int(sys.argv[3])
motion_group = os.environ.get("TIGERCAPTURE_LIVE2D_QA_MOTION_GROUP", "")
expression_id = os.environ.get("TIGERCAPTURE_LIVE2D_QA_EXPRESSION_ID", "")
try:
    motion_idx = int(os.environ.get("TIGERCAPTURE_LIVE2D_QA_MOTION_IDX", "0") or "0")
except Exception:
    motion_idx = 0

runtime = normalize_live2d_model_path(source) or ""
load_path = runtime or source
error = model_support_error(load_path)
if error:
    print(RESULT_PREFIX + json.dumps({
        "status": "unsupported",
        "source": source,
        "runtime": runtime,
        "error": error,
        "moc3_version": moc3_version(load_path),
    }, ensure_ascii=False), flush=True)
    raise SystemExit(0)

app = QApplication([])
clip = Live2DActorClip(
    model_path=load_path,
    motion_group=motion_group,
    motion_idx=motion_idx,
    expression_id=expression_id,
)
img = None
nonblank = False
bbox = None
sample_ms = None
checked_ms = []
sweep_raw = os.environ.get("TIGERCAPTURE_LIVE2D_QA_SWEEP_MS", "").strip()
image_out = os.environ.get("TIGERCAPTURE_LIVE2D_QA_IMAGE_OUT", "").strip()
if sweep_raw:
    try:
        positions = [int(part) for part in sweep_raw.split(",") if part.strip()]
    except Exception:
        positions = [0, 250, 500, 1000]
else:
    positions = [0, 250, 500, 1000]
sweep_frames = []
for pos_ms in positions:
    checked_ms.append(pos_ms)
    candidate = clip.render_frame(width, height, pos_ms)
    if candidate is None:
        sweep_frames.append({"pos_ms": pos_ms, "nonblank": False, "bbox": None})
        continue
    img = candidate
    sample_ms = pos_ms
    try:
        alpha_bbox = candidate.getchannel("A").getbbox()
        nonblank = alpha_bbox is not None
        bbox = list(alpha_bbox) if alpha_bbox is not None else None
    except Exception:
        raw_bbox = candidate.getbbox()
        nonblank = raw_bbox is not None
        bbox = list(raw_bbox) if raw_bbox is not None else None
    sweep_frames.append({"pos_ms": pos_ms, "nonblank": nonblank, "bbox": bbox})
    if nonblank:
        if image_out:
            try:
                candidate.save(image_out)
                image_out = ""
            except Exception:
                pass
        if not sweep_raw:
            break
status = "pass" if nonblank else ("blank" if img is not None else "render_none")
if sweep_raw:
    blank_frames = sum(1 for frame in sweep_frames if not frame.get("nonblank"))
    status = "pass" if blank_frames == 0 else ("blank" if img is not None else "render_none")
print(RESULT_PREFIX + json.dumps({
    "status": status,
    "source": source,
    "runtime": runtime,
    "load_path": load_path,
    "motion_group": motion_group,
    "motion_idx": motion_idx,
    "expression_id": expression_id,
    "runtime_exists": bool(runtime),
    "moc3_version": moc3_version(load_path),
    "size": list(img.size) if img is not None else None,
    "nonblank": nonblank,
    "bbox": bbox,
    "sample_ms": sample_ms,
    "checked_ms": checked_ms,
    "sweep": {
        "sample_count": len(sweep_frames),
        "blank_frames": sum(1 for frame in sweep_frames if not frame.get("nonblank")),
        "frames": sweep_frames,
    } if sweep_raw else None,
}, ensure_ascii=False), flush=True)
"""


def _is_maybe_bundle(path: Path) -> bool:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix in {".bundle", ".unity3d", ".ab", ".assets"}:
        return True
    return (
        not suffix
        and path.is_file()
        and path.stat().st_size > 1024
        and ("live2d" in name or "model" in name or "sekai" in name)
    )


def discover_candidates(source: Path) -> tuple[list[Path], list[Path]]:
    from app.live2d.compat import is_live2d_candidate

    candidates: list[Path] = []
    bundles: list[Path] = []
    if source.is_file():
        if is_live2d_candidate(source):
            candidates.append(source)
        elif _is_maybe_bundle(source):
            bundles.append(source)
        return candidates, bundles

    for path in source.rglob("*"):
        if not path.is_file():
            continue
        try:
            if is_live2d_candidate(path):
                candidates.append(path)
                continue
        except Exception:
            pass
        if _is_maybe_bundle(path):
            bundles.append(path)
    return sorted(dict.fromkeys(candidates)), sorted(dict.fromkeys(bundles))


def _read_model3(path: Path) -> dict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def live2d_metadata_coverage(path: Path) -> dict:
    data = _read_model3(path)
    refs = data.get("FileReferences") if isinstance(data.get("FileReferences"), dict) else {}
    motions = refs.get("Motions") if isinstance(refs.get("Motions"), dict) else {}
    expressions = refs.get("Expressions") if isinstance(refs.get("Expressions"), list) else []
    motion_count = 0
    motion_groups: list[dict] = []
    for group, rows in motions.items():
        group_rows = rows if isinstance(rows, list) else []
        motion_count += len(group_rows)
        motion_groups.append({"group": str(group), "count": len(group_rows)})
    expression_rows: list[dict] = []
    for item in expressions:
        if not isinstance(item, dict):
            continue
        expression_rows.append({
            "name": str(item.get("Name") or item.get("Id") or item.get("File") or ""),
            "file": str(item.get("File") or ""),
        })
    return {
        "motion_groups": motion_groups,
        "motion_count": motion_count,
        "expression_count": len(expression_rows),
        "expressions": expression_rows[:20],
        "physics": bool(refs.get("Physics")),
        "pose": bool(refs.get("Pose")),
        "display_info": bool(refs.get("DisplayInfo")),
        "user_data": bool(refs.get("UserData")),
        "hit_area_count": len(data.get("HitAreas") or []) if isinstance(data.get("HitAreas"), list) else 0,
    }


def live2d_motion_variants(path: Path, *, max_motions: int = 4) -> list[dict]:
    data = _read_model3(path)
    refs = data.get("FileReferences") if isinstance(data.get("FileReferences"), dict) else {}
    motions = refs.get("Motions") if isinstance(refs.get("Motions"), dict) else {}
    variants: list[dict] = []
    for group in sorted(motions):
        rows = motions.get(group)
        if not isinstance(rows, list):
            continue
        for idx, item in enumerate(rows):
            if not isinstance(item, dict):
                continue
            label = str(item.get("File") or item.get("Sound") or f"{group}[{idx}]")
            variants.append({
                "motion_group": str(group),
                "motion_idx": int(idx),
                "label": label,
            })
    if not variants:
        variants.append({"motion_group": "", "motion_idx": 0, "label": "static"})
    return variants[: max(1, int(max_motions or 1))]


def live2d_expression_variants(path: Path, *, max_expressions: int = 3) -> list[dict]:
    data = _read_model3(path)
    refs = data.get("FileReferences") if isinstance(data.get("FileReferences"), dict) else {}
    expressions = refs.get("Expressions") if isinstance(refs.get("Expressions"), list) else []
    variants: list[dict] = []
    for item in expressions:
        if not isinstance(item, dict):
            continue
        expression_id = str(item.get("Name") or Path(str(item.get("File") or "")).stem)
        if not expression_id:
            continue
        variants.append({
            "expression_id": expression_id,
            "label": str(item.get("File") or expression_id),
        })
    return variants[: max(0, int(max_expressions or 0))]


def live2d_render_variants(
    path: Path,
    *,
    max_motions: int = 4,
    max_expressions: int = 3,
) -> list[dict]:
    motions = live2d_motion_variants(path, max_motions=max_motions)
    expressions = live2d_expression_variants(path, max_expressions=max_expressions)
    variants: list[dict] = [dict(motion, expression_id="", variant_kind="motion") for motion in motions]
    if expressions:
        base_motion = motions[0] if motions else {"motion_group": "", "motion_idx": 0, "label": "static"}
        for expression in expressions:
            variants.append({
                **base_motion,
                "expression_id": expression["expression_id"],
                "label": f"{base_motion.get('label', 'static')} + {expression['label']}",
                "variant_kind": "expression",
            })
    return variants


def _decode_json_fragment(fragment: str) -> dict | None:
    decoder = json.JSONDecoder()
    text = str(fragment or "").strip()
    if not text:
        return None
    try:
        payload, _end = decoder.raw_decode(text)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _extract_child_payload(stdout: str) -> dict | None:
    text = stdout or ""
    marker = text.rfind(RESULT_PREFIX)
    if marker >= 0:
        payload = _decode_json_fragment(text[marker + len(RESULT_PREFIX):])
        if payload is not None:
            return payload
    for line in reversed([line for line in text.splitlines() if line.strip()]):
        payload = _decode_json_fragment(line)
        if payload is not None:
            return payload
    return None


def _text_tail(value: object, *, lines: int = 20) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    return "\n".join(text.splitlines()[-lines:])


def run_one(
    path: Path,
    width: int,
    height: int,
    timeout: int,
    *,
    image_out: Path | str | None = None,
    sweep_ms: list[int] | None = None,
    motion_group: str = "",
    motion_idx: int = 0,
    expression_id: str = "",
) -> dict:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if image_out is not None:
        env["TIGERCAPTURE_LIVE2D_QA_IMAGE_OUT"] = str(image_out)
    if sweep_ms:
        env["TIGERCAPTURE_LIVE2D_QA_SWEEP_MS"] = ",".join(str(int(ms)) for ms in sweep_ms)
    env["TIGERCAPTURE_LIVE2D_QA_MOTION_GROUP"] = str(motion_group or "")
    env["TIGERCAPTURE_LIVE2D_QA_MOTION_IDX"] = str(int(motion_idx or 0))
    env["TIGERCAPTURE_LIVE2D_QA_EXPRESSION_ID"] = str(expression_id or "")
    try:
        cp = subprocess.run(
            [sys.executable, "-c", CHILD, str(path), str(width), str(height)],
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "source": str(path),
            "runtime": "",
            "error": f"timed out after {timeout}s",
            "stdout_tail": _text_tail(exc.output),
            "stderr_tail": _text_tail(exc.stderr),
        }
    payload = _extract_child_payload(cp.stdout or "")
    if payload is None:
        payload = {
            "status": "crash" if cp.returncode else "unknown",
            "source": str(path),
            "runtime": "",
            "error": "no json result from child process",
        }
    if cp.returncode and payload.get("status") not in {"unsupported"}:
        payload["status"] = "crash"
        payload["exit_code"] = cp.returncode
    payload["stdout_tail"] = "\n".join((cp.stdout or "").splitlines()[-20:])
    payload["stderr_tail"] = "\n".join((cp.stderr or "").splitlines()[-20:])
    return payload


def run_one_sweep(
    path: Path,
    width: int,
    height: int,
    timeout: int,
    *,
    samples: int = 5,
    duration_ms: int = 3000,
    max_motions: int = 4,
    max_expressions: int = 3,
) -> dict:
    samples = max(2, int(samples or 5))
    duration_ms = max(1, int(duration_ms or 3000))
    positions = sorted({
        max(0, min(duration_ms, int(round(duration_ms * idx / (samples - 1)))))
        for idx in range(samples)
    })
    variants = live2d_render_variants(
        path,
        max_motions=max_motions,
        max_expressions=max_expressions,
    )
    metadata = live2d_metadata_coverage(path)
    motions: list[dict] = []
    total_samples = 0
    total_blank = 0
    worst_status = "pass"
    for variant in variants:
        payload = run_one(
            path,
            width,
            height,
            timeout,
            sweep_ms=positions,
            motion_group=str(variant.get("motion_group") or ""),
            motion_idx=int(variant.get("motion_idx", 0) or 0),
            expression_id=str(variant.get("expression_id") or ""),
        )
        sweep = payload.get("sweep")
        motion_row = dict(variant)
        motion_row["status"] = payload.get("status", "unknown")
        motion_row["error"] = str(payload.get("error") or "")
        if isinstance(sweep, dict):
            motion_row["sample_count"] = int(sweep.get("sample_count", 0) or 0)
            motion_row["blank_frames"] = int(sweep.get("blank_frames", 0) or 0)
            motion_row["frames"] = list(sweep.get("frames", []) or [])
        else:
            motion_row["sample_count"] = 0
            motion_row["blank_frames"] = 0
            motion_row["frames"] = []
        total_samples += int(motion_row["sample_count"])
        total_blank += int(motion_row["blank_frames"])
        status = str(motion_row.get("status") or "unknown")
        if status not in {"pass"}:
            worst_status = status
        motions.append(motion_row)
    if total_blank > 0 and worst_status == "pass":
        worst_status = "blank"
    if motions:
        return {
            "source": str(path),
            "status": worst_status,
            "sample_count": total_samples,
            "blank_frames": total_blank,
            "motions_tested": len(motions),
            "motion_variants": motions,
            "frames": list(motions[0].get("frames", []) or []),
            "metadata_coverage": metadata,
            "error": "; ".join(row["error"] for row in motions if row.get("error")),
        }
    return {
        "source": str(path),
        "status": "unknown",
        "sample_count": 0,
        "blank_frames": 0,
        "motions_tested": 0,
        "motion_variants": [],
        "frames": [],
        "metadata_coverage": metadata,
        "error": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan and render-test Live2D resources one model per process."
    )
    parser.add_argument("source", help="Folder or file to scan")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"source not found: {source}", file=sys.stderr)
        return 2

    candidates, bundles = discover_candidates(source)
    results: list[dict] = []
    print(f"candidates={len(candidates)}")
    if bundles:
        print(f"raw_or_unity_bundles={len(bundles)}")
        print("bundle files need extraction before this app can load their Live2D assets:")
        for path in bundles[:20]:
            print(f"  bundle: {path}")
        if len(bundles) > 20:
            print(f"  ... {len(bundles) - 20} more")

    for index, path in enumerate(candidates, start=1):
        print(f"[{index}/{len(candidates)}] {path}")
        try:
            result = run_one(path, args.width, args.height, args.timeout)
        except subprocess.TimeoutExpired:
            result = {
                "status": "timeout",
                "source": str(path),
                "runtime": "",
                "error": f"timed out after {args.timeout}s",
            }
        results.append(result)
        status = result.get("status", "unknown")
        runtime = result.get("runtime") or ""
        print(f"  {status} runtime={runtime}")

    summary = {
        "source": str(source),
        "total": len(results),
        "bundles": [str(path) for path in bundles],
        "counts": {},
        "results": results,
    }
    for result in results:
        status = result.get("status", "unknown")
        summary["counts"][status] = summary["counts"].get(status, 0) + 1

    print("summary=" + json.dumps(summary["counts"], ensure_ascii=False))
    if args.report:
        report = Path(args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report={report}")
    return 1 if summary["counts"].get("crash") or summary["counts"].get("timeout") else 0


if __name__ == "__main__":
    raise SystemExit(main())
