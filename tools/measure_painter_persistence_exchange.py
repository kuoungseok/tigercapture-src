from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OFFICIAL_SOURCES = {
    "png_3": "https://www.w3.org/TR/png-3/",
    "photoshop_file_format": "https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/",
    "tiff_6": "https://printtechnologies.org/standards/files/tiff-v6.pdf",
    "icc_tiff_embedding": "https://www.color.org/icc32.pdf",
    "iso_216": "https://www.iso.org/standard/36631.html",
    "adobe_print_resolution": "https://helpx.adobe.com/photoshop/desktop/crop-resize-transform/resize-adjust-resolution/resolution-specs-for-printing-images.html",
    "clip_manga_resolution": "https://tips.clip-studio.com/en-us/articles/1019",
    "python_zipfile": "https://docs.python.org/3/library/zipfile.html",
    "python_os_replace": "https://docs.python.org/3/library/os.html#os.replace",
    "rfc7693": "https://www.rfc-editor.org/rfc/rfc7693",
}


def _png_bytes(color: tuple[int, int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (5, 3), color).save(buffer, "PNG")
    return buffer.getvalue()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_measurement() -> dict[str, Any]:
    from app.painter_autosave import (
        LEGACY_SCHEMA_V1,
        SCHEMA as RECOVERY_SCHEMA,
        inspect_recovery_archive,
        list_recovery_snapshots,
        save_recovery_snapshot,
    )
    from app.painter_document_io import (
        PainterDocumentError,
        load_painter_document,
        save_painter_document,
    )
    from app.painter_file_exchange import (
        _rgba16_to_rgba8,
        export_flat_image,
        inspect_flat_image,
    )
    from app.painter_output import (
        PRINT_PRESET_MODEL_CONTRACT,
        PRINT_PRESETS,
        normalize_output_settings,
        pixels_for_print,
    )

    with tempfile.TemporaryDirectory(prefix="tiger-painter-m53-") as temp_name:
        temp = Path(temp_name)
        raster = _png_bytes((31, 97, 211, 173))
        document = {
            "document": {"width": 5, "height": 3},
            "channels": {
                "saved_selection_channels": [],
                "saved_selection_channel_serial": 0,
            },
            "layers": [
                {
                    "layer_id": "paint-1",
                    "name": "Measured layer",
                    "raster_asset": "",
                    "mask_asset": "",
                }
            ],
        }
        document_path = temp / "measured.tspaint"
        save_report = save_painter_document(
            document_path,
            document,
            layer_raster_pngs={"paint-1": raster},
        )
        loaded, load_report = load_painter_document(
            document_path,
            asset_root=temp / "loaded-assets",
        )
        loaded_asset = Path(loaded["layers"][0]["raster_asset"])
        with zipfile.ZipFile(document_path, "r") as archive:
            archive_document = json.loads(archive.read("document.json"))
            manifest_row = archive_document["asset_manifest"][0]
            archive_asset = archive.read(manifest_row["entry"])

        malformed = dict(archive_document)
        malformed["asset_manifest"] = [dict(manifest_row, size=len(raster) + 1)]
        malformed_path = temp / "malformed-size.tspaint"
        with zipfile.ZipFile(malformed_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("document.json", json.dumps(malformed))
            archive.writestr(manifest_row["entry"], raster)
        malformed_blocked = False
        try:
            load_painter_document(
                malformed_path,
                asset_root=temp / "malformed-assets",
            )
        except PainterDocumentError:
            malformed_blocked = True

        recovery_root = temp / "recovery"
        recovery_first = save_recovery_snapshot(
            "m53-session",
            document,
            source_path="first.tspaint",
            layer_raster_pngs={"paint-1": raster},
            root=recovery_root,
        )
        recovery_skipped = save_recovery_snapshot(
            "m53-session",
            document,
            source_path="first.tspaint",
            layer_raster_pngs={"paint-1": raster},
            root=recovery_root,
        )
        recovery_path = Path(recovery_first["recovery_path"])
        with zipfile.ZipFile(recovery_path, "a") as archive:
            archive.writestr("valid-tamper.txt", b"changes whole archive hash")
        tamper_report = inspect_recovery_archive(
            recovery_path,
            expected_sha256=recovery_first["archive_sha256"],
        )
        tampered_rows = list_recovery_snapshots(root=recovery_root)
        recovery_repaired = save_recovery_snapshot(
            "m53-session",
            document,
            source_path="first.tspaint",
            layer_raster_pngs={"paint-1": raster},
            root=recovery_root,
        )
        repaired_integrity = inspect_recovery_archive(
            recovery_path,
            expected_sha256=recovery_repaired["archive_sha256"],
        )
        invalid_manifest = save_recovery_snapshot(
            "m53-invalid-manifest",
            document,
            source_path="first.tspaint",
            layer_raster_pngs={"paint-1": raster},
            root=recovery_root,
        )
        invalid_manifest_path = Path(invalid_manifest["manifest_path"])
        invalid_manifest_payload = json.loads(
            invalid_manifest_path.read_text(encoding="utf-8")
        )
        invalid_manifest_payload["saved_at"] = "not-a-time"
        invalid_manifest_path.write_text(
            json.dumps(invalid_manifest_payload),
            encoding="utf-8",
        )
        invalid_manifest_hidden = all(
            row["session_id"] != "m53-invalid-manifest"
            for row in list_recovery_snapshots(root=recovery_root)
        )
        invalid_manifest_repaired = save_recovery_snapshot(
            "m53-invalid-manifest",
            document,
            source_path="first.tspaint",
            layer_raster_pngs={"paint-1": raster},
            root=recovery_root,
        )
        legacy_payload = json.loads(
            invalid_manifest_path.read_text(encoding="utf-8")
        )
        legacy_payload["schema"] = LEGACY_SCHEMA_V1
        legacy_payload.pop("archive_sha256")
        legacy_payload.pop("manifest_sha256")
        legacy_payload.pop("retention_contract")
        invalid_manifest_path.write_text(
            json.dumps(legacy_payload),
            encoding="utf-8",
        )
        legacy_rows = [
            row
            for row in list_recovery_snapshots(root=recovery_root)
            if row["session_id"] == "m53-invalid-manifest"
        ]
        legacy_upgraded = save_recovery_snapshot(
            "m53-invalid-manifest",
            document,
            source_path="first.tspaint",
            layer_raster_pngs={"paint-1": raster},
            root=recovery_root,
        )

        all_u16 = np.arange(65536, dtype=np.uint16).reshape(128, 128, 4)
        converted = _rgba16_to_rgba8(all_u16)
        exact = np.floor(
            all_u16.astype(np.float64) * 255.0 / 65535.0 + 0.5
        ).astype(np.uint8)
        shifted = (all_u16 >> 8).astype(np.uint8)

        rgba16 = np.array(
            [[(0, 129, 32767, 65535), (65535, 32896, 257, 65535)]],
            dtype=np.uint16,
        )
        png8_path = temp / "linear-8.png"
        export_flat_image(png8_path, rgba16, format_name="png", bit_depth=8)
        png8_pixels = np.asarray(Image.open(png8_path).convert("RGBA"))
        png16_path = temp / "native-16.png"
        tiff16_path = temp / "native-16.tiff"
        export_flat_image(png16_path, rgba16, format_name="png", bit_depth=16)
        export_flat_image(tiff16_path, rgba16, format_name="tiff", bit_depth=16)
        png16_inspection = inspect_flat_image(png16_path)
        tiff16_inspection = inspect_flat_image(tiff16_path)

        normalized_nonfinite = normalize_output_settings(
            {
                "mode": "print",
                "width_mm": float("nan"),
                "height_mm": float("inf"),
                "ppi": float("nan"),
                "bleed_mm": float("-inf"),
                "include_bleed": "false",
                "resample": "false",
                "color_space": "CMYK",
            },
            pixel_width=1200,
            pixel_height=800,
        )
        preset_by_name = {preset.name: preset for preset in PRINT_PRESETS}

        checks = {
            "tspaint_roundtrip_asset_bytes_exact": loaded_asset.read_bytes() == raster,
            "tspaint_manifest_size_exact": manifest_row["size"] == len(archive_asset),
            "tspaint_manifest_sha256_exact": manifest_row["sha256"]
            == hashlib.sha256(archive_asset).hexdigest(),
            "tspaint_v5_size_mismatch_blocked_before_extraction": malformed_blocked
            and not (temp / "malformed-assets").exists(),
            "recovery_unchanged_content_skips_only_after_integrity": recovery_skipped["skipped"]
            is True,
            "recovery_valid_zip_tamper_blocked_by_whole_archive_hash": (
                tamper_report["valid"] is False
                and tamper_report["reason"] == "archive_hash_mismatch"
                and tampered_rows == []
            ),
            "recovery_tamper_is_rewritten_and_revalidated": recovery_repaired["skipped"]
            is False
            and repaired_integrity["valid"] is True,
            "recovery_invalid_manifest_is_skipped_and_rewritten": (
                invalid_manifest_hidden
                and invalid_manifest_repaired["skipped"] is False
                and any(
                    row["session_id"] == "m53-invalid-manifest"
                    for row in list_recovery_snapshots(root=recovery_root)
                )
            ),
            "recovery_v1_remains_visible_without_trusting_source_and_upgrades": (
                len(legacy_rows) == 1
                and legacy_rows[0]["legacy_manifest"] is True
                and legacy_rows[0]["source_path"] == ""
                and legacy_rows[0]["legacy_unverified_source_path"] is True
                and legacy_upgraded["skipped"] is False
                and legacy_upgraded["schema"] == RECOVERY_SCHEMA
            ),
            "uint16_to_uint8_matches_png_linear_formula_for_all_values": np.array_equal(
                converted, exact
            ),
            "linear_rescaling_differs_from_discarding_low_byte": int(
                np.count_nonzero(converted != shifted)
            )
            > 0,
            "exported_8bit_pixels_use_linear_rescaling": np.array_equal(
                png8_pixels, _rgba16_to_rgba8(rgba16)
            ),
            "png16_export_reopens_as_16bit": png16_inspection["bit_depth"] == 16
            and png16_inspection["integrity"]["valid"],
            "tiff16_export_reopens_as_16bit": tiff16_inspection["bit_depth"] == 16
            and tiff16_inspection["integrity"]["valid"],
            "a4_trim_and_pixel_math_match_declared_contract": (
                preset_by_name["A4 Print · 300 PPI"].width_mm == 210.0
                and preset_by_name["A4 Print · 300 PPI"].height_mm == 297.0
                and pixels_for_print(210, 297, ppi=300, bleed_mm=0) == (2480, 3508)
            ),
            "manga_b5_dimensions_and_resolution_are_explicit": any(
                preset.width_mm == 182.0
                and preset.height_mm == 257.0
                and preset.ppi == 600
                and "182×257" in preset.name
                for preset in PRINT_PRESETS
            ),
            "print_model_rejects_universal_quality_and_bleed_claims": (
                PRINT_PRESET_MODEL_CONTRACT["universal_print_quality_claim"] is False
                and PRINT_PRESET_MODEL_CONTRACT["universal_bleed_claim"] is False
            ),
            "malformed_nonfinite_output_state_is_finite_and_srgb": (
                np.isfinite(normalized_nonfinite["width_mm"])
                and np.isfinite(normalized_nonfinite["height_mm"])
                and normalized_nonfinite["ppi"] == 300
                and normalized_nonfinite["color_space"] == "srgb"
                and normalized_nonfinite["include_bleed"] is True
                and normalized_nonfinite["resample"] is True
            ),
        }
        measurements = {
            "tspaint_sha256": _sha256(document_path),
            "tspaint_asset_count": save_report["asset_count"],
            "tspaint_loaded_asset_count": load_report["asset_count"],
            "recovery_archive_sha256": recovery_repaired["archive_sha256"],
            "uint16_values_checked": int(all_u16.size),
            "shift_disagreement_count": int(np.count_nonzero(converted != shifted)),
            "png8_pixels": png8_pixels.tolist(),
            "png16_bit_depth": png16_inspection["bit_depth"],
            "tiff16_bit_depth": tiff16_inspection["bit_depth"],
            "print_preset_count": len(PRINT_PRESETS),
        }

    return {
        "schema": "tigerstudio.painter.persistence_exchange_measurement.v1",
        "scope": "painting_only_ui_design_excluded",
        "official_sources": OFFICIAL_SOURCES,
        "claim_boundary": {
            "external_application_interoperability_certified": False,
            "power_loss_atomicity_claim": False,
            "universal_recovery_capacity_claim": False,
            "universal_print_quality_or_bleed_claim": False,
            "validated_claim": "deterministic_tiger_persistence_integrity_and_declared_exchange_math",
        },
        "measurements": measurements,
        "checks": checks,
        "checks_passed": sum(bool(value) for value in checks.values()),
        "checks_total": len(checks),
        "passed": all(bool(value) for value in checks.values()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(
            ROOT
            / "debugCapture"
            / "painter"
            / "evidence_audit"
            / "m53_persistence_exchange.json"
        ),
    )
    args = parser.parse_args(argv)
    report = run_measurement()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "path": str(output.resolve()),
                "passed": report["passed"],
                "checks_passed": report["checks_passed"],
                "checks_total": report["checks_total"],
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
