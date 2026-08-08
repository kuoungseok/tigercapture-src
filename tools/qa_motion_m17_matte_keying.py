"""Generate deterministic M17 matte/keying acceptance evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.keying import apply_keyer_rgba
from app.motion_designer.mask_matting import refine_alpha_matte


WIDTH = 320
HEIGHT = 180


def _soft_subject(index: int) -> tuple[np.ndarray, np.ndarray]:
    scale = 4
    alpha_large = np.zeros((HEIGHT * scale, WIDTH * scale), dtype=np.uint8)
    offset = (index % 3 - 1) * 8 * scale
    center = (WIDTH * scale // 2 + offset, 92 * scale)
    cv2.ellipse(alpha_large, center, (38 * scale, 56 * scale), 0, 0, 360, 255, -1)
    cv2.rectangle(
        alpha_large,
        (center[0] - 48 * scale, 130 * scale),
        (center[0] + 48 * scale, HEIGHT * scale),
        255,
        -1,
    )
    for strand in range(11):
        x = center[0] - 38 * scale + strand * 7 * scale
        cv2.line(
            alpha_large,
            (x, 54 * scale),
            (x + (strand - 5) * scale, (20 + strand % 3 * 8) * scale),
            255,
            max(2, scale),
        )
    if index in {2, 7}:
        cv2.line(
            alpha_large,
            (center[0] + 25 * scale, 105 * scale),
            (center[0] + 100 * scale, 65 * scale),
            210,
            13 * scale,
        )
    alpha = cv2.resize(
        alpha_large,
        (WIDTH, HEIGHT),
        interpolation=cv2.INTER_AREA,
    )
    if index in {3, 8}:
        alpha = cv2.GaussianBlur(alpha, (0, 0), sigmaX=2.6)
    if index in {4, 9}:
        alpha = np.minimum(alpha, 165).astype(np.uint8)
    foreground = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    foreground[:] = (224, 164, 118)
    foreground[:, :, 0] += np.linspace(0, 20, WIDTH, dtype=np.uint8)[None, :]
    return foreground, alpha


def _case(index: int) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int], str]:
    blue = index >= 5
    key = (20, 42, 238) if blue else (22, 226, 38)
    label = ("blue" if blue else "green") + (
        "_hair",
        "_clean",
        "_fast_arm",
        "_motion_blur",
        "_translucent",
    )[index % 5]
    foreground, expected = _soft_subject(index)
    rng = np.random.default_rng(1700 + index)
    background = np.empty_like(foreground)
    background[:] = key
    noise = rng.normal(0.0, 2.0, background.shape).astype(np.int16)
    background = np.clip(background.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    amount = expected.astype(np.float32)[..., None] / 255.0
    rgb = np.clip(
        foreground.astype(np.float32) * amount
        + background.astype(np.float32) * (1.0 - amount),
        0,
        255,
    ).astype(np.uint8)
    rgba = np.dstack([rgb, np.full((HEIGHT, WIDTH), 255, dtype=np.uint8)])
    return rgba, expected, key, label


def _metrics(predicted: np.ndarray, expected: np.ndarray) -> dict[str, float]:
    prediction = predicted >= 128
    target = expected >= 128
    intersection = np.count_nonzero(prediction & target)
    union = np.count_nonzero(prediction | target)
    mae = float(np.mean(np.abs(
        predicted.astype(np.float32) - expected.astype(np.float32)
    ))) / 255.0
    return {
        "iou": float(intersection) / float(max(1, union)),
        "alpha_mae": mae,
    }


def _checkerboard() -> np.ndarray:
    y, x = np.indices((HEIGHT, WIDTH))
    block = ((x // 12 + y // 12) % 2)[..., None]
    return np.where(block, 62, 38).astype(np.uint8).repeat(3, axis=2)


def run(output_dir: str | Path) -> dict[str, object]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    rows: list[np.ndarray] = []
    reports: list[dict[str, object]] = []
    temporal_samples: list[np.ndarray] = []
    checker = _checkerboard()

    for index in range(10):
        rgba, expected, key, label = _case(index)
        result = apply_keyer_rgba(
            rgba,
            "chroma_key",
            {
                "key_color": "#{:02x}{:02x}{:02x}".format(*key),
                "similarity": 0.22,
                "softness": 0.08,
                "despill": 0.9,
                "feather": 0.6,
            },
        )
        predicted = np.clip(result.rgba[..., 3], 0, 255).astype(np.uint8)
        temporal_samples.append(predicted.astype(np.float32) / 255.0)
        alpha = predicted[..., None].astype(np.float32) / 255.0
        composite = np.clip(
            result.rgba[..., :3] * alpha + checker * (1.0 - alpha),
            0,
            255,
        ).astype(np.uint8)
        alpha_rgb = np.repeat(predicted[..., None], 3, axis=2)
        caption = np.zeros((24, WIDTH * 3, 3), dtype=np.uint8)
        cv2.putText(
            caption,
            label,
            (8, 17),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (235, 235, 235),
            1,
            cv2.LINE_AA,
        )
        rows.append(np.vstack([np.hstack([rgba[..., :3], alpha_rgb, composite]), caption]))
        metrics = _metrics(predicted, expected)
        edge = (expected > 8) & (expected < 247)
        key_channel = int(np.argmax(key))
        other_channels = [item for item in range(3) if item != key_channel]
        spill = np.maximum(
            0.0,
            result.rgba[..., key_channel]
            - np.maximum(
                result.rgba[..., other_channels[0]],
                result.rgba[..., other_channels[1]],
            ),
        )
        metrics["edge_spill"] = float(np.mean(spill[edge]) / 255.0) if np.any(edge) else 0.0
        reports.append({"name": label, **metrics, **result.diagnostics})

    contact_sheet = np.vstack(rows)
    cv2.imwrite(str(destination / "m17_keying_contact_sheet.png"), cv2.cvtColor(contact_sheet, cv2.COLOR_RGB2BGR))

    sequence = []
    for frame in range(12):
        rgba, _expected, key, _label = _case(0)
        rng = np.random.default_rng(3100 + frame)
        background = rgba[..., 1] > 180
        jitter = rng.integers(-3, 4, size=rgba.shape[:2])
        rgba[..., 1] = np.where(
            background,
            np.clip(rgba[..., 1].astype(np.int16) + jitter, 0, 255),
            rgba[..., 1],
        ).astype(np.uint8)
        keyed = apply_keyer_rgba(
            rgba,
            "chroma_key",
            {
                "key_color": "#{:02x}{:02x}{:02x}".format(*key),
                "similarity": 0.22,
                "softness": 0.08,
                "despill": 0.9,
                "feather": 0.6,
            },
        )
        sequence.append(keyed.rgba[..., 3].astype(np.float32) / 255.0)
    temporal_flicker = float(np.mean(np.std(np.stack(sequence), axis=0)))

    soft_source = np.tile(np.linspace(0, 255, WIDTH, dtype=np.uint8), (HEIGHT, 1))
    refined = refine_alpha_matte(
        np.full((HEIGHT, WIDTH, 3), 128, dtype=np.uint8),
        soft_source,
        mode="edge_aware",
    )
    soft_alpha_mae = float(np.mean(np.abs(
        refined.alpha.astype(np.float32) - soft_source.astype(np.float32)
    ))) / 255.0

    minimum_iou = min(float(item["iou"]) for item in reports)
    maximum_halo = max(float(item["edge_spill"]) for item in reports)
    ok = (
        minimum_iou >= 0.88
        and maximum_halo <= 0.12
        and temporal_flicker <= 0.015
        and soft_alpha_mae <= 0.08
    )
    report: dict[str, object] = {
        "schema": "tigerstudio.motion.m17_qa.v1",
        "ok": ok,
        "case_count": len(reports),
        "minimum_iou": minimum_iou,
        "maximum_edge_spill": maximum_halo,
        "temporal_flicker": temporal_flicker,
        "soft_alpha_mae": soft_alpha_mae,
        "cases": reports,
        "contact_sheet": str(destination / "m17_keying_contact_sheet.png"),
    }
    (destination / "m17_matte_keying_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="debugCapture/motion_designer/m17_matte_keying",
    )
    args = parser.parse_args()
    report = run(args.output_dir)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
