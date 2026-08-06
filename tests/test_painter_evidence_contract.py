from __future__ import annotations

import json


def test_synthetic_evidence_cannot_certify_hardware_or_native_runtime() -> None:
    from app.painter_evidence_contract import evidence_record, evaluate_release_claims

    report = evaluate_release_claims([
        evidence_record(
            "pytest-offscreen",
            "synthetic_integration",
            passed=True,
            producer="pytest",
            claims=("automated_functional_baseline",),
            environment={"QT_QPA_PLATFORM": "offscreen", "QT_SCALE_FACTOR": "1.5"},
        )
    ])
    assert report["classification"] == "automated_baseline_only"
    assert report["claims"]["automated_functional_baseline"]["passed"] is True
    assert report["claims"]["native_high_dpi"]["passed"] is False
    assert report["claims"]["physical_tablet_input"]["passed"] is False
    assert report["claims"]["basic_stroke_gpu_path"]["passed"] is False


def test_every_release_claim_requires_claim_specific_provenance() -> None:
    from app.painter_evidence_contract import (
        RELEASE_CLAIM_REQUIREMENTS,
        evidence_record,
        evaluate_release_claims,
    )

    rows = [
        evidence_record(
            f"e-{claim_id}",
            required_kinds[0],
            passed=True,
            producer="independent-qa",
            claims=(claim_id,),
        )
        for claim_id, required_kinds in RELEASE_CLAIM_REQUIREMENTS.items()
    ]
    report = evaluate_release_claims(rows)
    assert report["release_ready"] is True
    assert all(row["passed"] for row in report["claims"].values())


def test_evidence_record_rejects_unknown_kind() -> None:
    import pytest
    from app.painter_evidence_contract import evidence_record

    with pytest.raises(ValueError):
        evidence_record("bad", "looks_good", passed=True, producer="nobody")


def test_native_runtime_for_one_claim_cannot_certify_other_native_claims() -> None:
    from app.painter_evidence_contract import evidence_record, evaluate_release_claims

    report = evaluate_release_claims([
        evidence_record(
            "native-dpi-only",
            "native_runtime",
            passed=True,
            producer="native probe",
            claims=("native_high_dpi",),
        )
    ])
    assert report["claims"]["native_high_dpi"]["passed"] is True
    assert report["claims"]["basic_stroke_gpu_path"]["passed"] is False
    assert report["claims"]["crash_recovery"]["passed"] is False


def test_numeric_decision_ledger_requires_exact_frozen_row_inventory(
    monkeypatch, tmp_path
) -> None:
    from tools import audit_painter_painting_evidence as audit

    rows = [{
        "path": "app/example.py",
        "line": 10,
        "class": "Example",
        "function": "normalize",
        "text": "value = max(0, min(10, value))",
        "review_status": "candidate_explicit_ledger_example_contract",
    }]
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps({
        "contracts": {
            "example_contract": {
                "resolution": "approved",
                "decision_basis": "explicit_tiger_product_policy_no_external_parity_claim",
                "row_count": 1,
                "rows_sha256": audit._candidate_group_fingerprint(rows),
                "evidence": "explicit test contract",
            }
        }
    }), encoding="utf-8")
    monkeypatch.setattr(audit, "NUMERIC_LEDGER_PATH", ledger_path)

    status = audit._apply_decision_ledger(rows)

    assert status["accepted_contracts"] == ["example_contract"]
    assert status["stale_contracts"] == []
    assert status["candidate_inventory"] == [{
        "contract_id": "example_contract",
        "row_count": 1,
        "rows_sha256": audit._candidate_group_fingerprint(rows),
    }]
    assert rows[0]["review_status"] == "ledger_approved_example_contract"


def test_numeric_decision_ledger_returns_changed_source_to_unresolved(
    monkeypatch, tmp_path
) -> None:
    from tools import audit_painter_painting_evidence as audit

    original = [{
        "path": "app/example.py",
        "line": 10,
        "class": "Example",
        "function": "normalize",
        "text": "value = max(0, min(10, value))",
        "review_status": "candidate_explicit_ledger_example_contract",
    }]
    changed = [dict(original[0], line=44, text="value = max(0, min(11, value))")]
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps({
        "contracts": {
            "example_contract": {
                "resolution": "approved",
                "decision_basis": "explicit_tiger_product_policy_no_external_parity_claim",
                "row_count": 1,
                "rows_sha256": audit._candidate_group_fingerprint(original),
                "evidence": "explicit test contract",
            }
        }
    }), encoding="utf-8")
    monkeypatch.setattr(audit, "NUMERIC_LEDGER_PATH", ledger_path)

    status = audit._apply_decision_ledger(changed)

    assert status["accepted_contracts"] == []
    assert status["stale_contracts"][0]["contract_id"] == "example_contract"
    assert changed[0]["review_status"].startswith("candidate_explicit_ledger_")


def test_painting_numeric_audit_excludes_ui_design_functions_before_generic_rules() -> None:
    from tools import audit_painter_painting_evidence as audit

    row = {
        "path": "app/drawing.py",
        "class": "PaintDialog",
        "function": "_align_painter_ui_object",
        "text": "if len(selected) >= 3:",
    }
    assert audit._classify_numeric_control(row) == (
        "ui_design_mode_numeric_control_excluded_from_painting_scope"
    )


def test_qt_normalized_color_api_is_split_from_generic_unit_clamps() -> None:
    from tools import audit_painter_painting_evidence as audit

    qt_row = {
        "path": "app/painter_brush_dynamics.py",
        "class": "",
        "function": "paint_dynamic_stroke",
        "text": "dab_color.setAlphaF(max(0.0, min(1.0, opacity)))",
    }
    authored_row = {
        "path": "app/painter_brush_dynamics.py",
        "class": "",
        "function": "paint_dynamic_stroke",
        "text": "pressure = max(0.0, min(1.0, pressure))",
    }

    assert audit._classify_numeric_control(qt_row) == (
        "reviewed_qt_normalized_color_or_opacity_contract"
    )
    assert audit._classify_numeric_control(authored_row) == (
        "reviewed_normalized_painting_geometry_sensor_and_channel_contract"
    )


def test_smudge_rgba_fallback_stays_reachable_after_legacy_geometry_routing() -> None:
    from tools import audit_painter_painting_evidence as audit

    row = {
        "path": "app/painter_brush_dynamics.py",
        "class": "",
        "function": "paint_dynamic_stroke",
        "text": "QColor(*row[:4]) if len(row) >= 4 else QColor(*row[:3])",
    }

    assert audit._classify_numeric_control(row) == (
        "reviewed_smudge_sampling_geometry_and_workload_contract"
    )


def test_legacy_renderer_ast_literals_route_to_explicit_m51_contracts() -> None:
    from tools import audit_painter_painting_evidence as audit

    renderer = {
        "path": "app/drawing.py",
        "function": "_paint_textured_stroke",
        "text": "value_scale=0.78 if style == 'impasto_oil' else 0.90",
    }
    geometry = {
        "path": "app/painter_legacy_brush.py",
        "function": "deterministic_unit",
        "text": "digest_size=8",
    }

    assert audit._classify_numeric_literal_coverage(renderer) == (
        "candidate_explicit_ledger_authored_legacy_brush_renderer_literal_contract"
    )
    assert audit._classify_numeric_literal_coverage(geometry) == (
        "candidate_explicit_ledger_authored_legacy_brush_geometry_literal_contract"
    )


def test_v2_bristle_and_material_ast_literals_route_to_explicit_m52_contracts() -> None:
    from tools import audit_painter_painting_evidence as audit

    bristle = {
        "path": "app/painter_brush_engine_v2.py",
        "function": "bristle_lane_paths",
        "text": 'jitter = noise * base_width * 0.025',
    }
    material = {
        "path": "app/painter_material_paint.py",
        "function": "rasterize_material_channels",
        "text": 'ridge *= 0.38',
    }

    assert audit._classify_numeric_literal_coverage(bristle) == (
        "candidate_explicit_ledger_authored_bristle_stylization_literal_contract"
    )
    assert audit._classify_numeric_literal_coverage(material) == (
        "candidate_explicit_ledger_authored_stylized_material_model_literal_contract"
    )


def test_material_float_blur_fallback_routes_to_explicit_m52_exception_contract() -> None:
    from tools import audit_painter_painting_evidence as audit

    row = {
        "path": "app/painter_material_paint.py",
        "class": "",
        "function": "_blur",
        "text": "except Exception as exc:",
    }

    assert audit._classify_suppressed_exception(row) == (
        "candidate_explicit_ledger_exception_"
        "declared_optional_opencv_to_numpy_gaussian_blur_fallback"
    )


def test_icc_header_lengths_are_split_before_generic_cardinality_rules() -> None:
    from tools import audit_painter_painting_evidence as audit

    row = {
        "path": "app/painter_color_management.py",
        "class": "",
        "function": "inspect_icc_profile",
        "text": '"device_class": data[12:16] if len(data) >= 16 else "",',
    }

    assert audit._classify_numeric_control(row) == (
        "reviewed_icc_profile_header_field_boundary_contract"
    )


def test_ast_numeric_literal_coverage_finds_unrouted_assignment_and_excludes_ui(
    tmp_path
) -> None:
    from tools import audit_painter_painting_evidence as audit

    source = tmp_path / "painter_coverage_fixture.py"
    source.write_text(
        "LIMIT = 17\n"
        "FLAG = True\n"
        "def paint_sample():\n"
        "    return 23\n"
        "def paint_ui_sample():\n"
        "    return 99\n",
        encoding="utf-8",
    )

    rows = audit._scan_uncovered_numeric_literal_sites(
        [source],
        {(source.as_posix(), 1)},
    )

    assert [(row["line"], row["text"]) for row in rows] == [(4, "return 23")]


def test_psd_signature_and_version_literals_are_routed_from_ast_coverage() -> None:
    from tools import audit_painter_painting_evidence as audit

    signature = {
        "path": "app/painter_file_exchange.py",
        "function": "inspect_layered_psd",
        "text": 'if raw[:4] != b"8BPS":',
    }
    unrelated = {
        "path": "app/painter_file_exchange.py",
        "function": "inspect_layered_psd",
        "text": 'layers: list[str] = []',
    }

    assert audit._classify_numeric_literal_coverage(signature) == (
        "candidate_explicit_ledger_psd_header_signature_or_version_contract"
    )
    assert audit._classify_numeric_literal_coverage(unrelated) == (
        "candidate_numeric_literal_site_requires_routing"
    )


def test_psd_header_length_guards_are_split_before_generic_cardinality() -> None:
    from tools import audit_painter_painting_evidence as audit

    row = {
        "path": "app/painter_file_exchange.py",
        "class": "",
        "function": "inspect_layered_psd",
        "text": '"width": struct.unpack(">I", raw[18:22])[0] if len(raw) >= 22 else 0,',
    }

    assert audit._classify_numeric_control(row) == (
        "reviewed_psd_header_length_and_field_extent_contract"
    )


def test_png_chunk_parser_literals_are_routed_from_ast_coverage() -> None:
    from tools import audit_painter_painting_evidence as audit

    row = {
        "path": "app/painter_file_exchange.py",
        "function": "_png_integrity",
        "text": "end = offset + 12 + length",
    }

    assert audit._classify_numeric_literal_coverage(row) == (
        "candidate_explicit_ledger_png_chunk_structure_and_crc_contract"
    )


def test_tiff_header_and_ifd_literals_are_routed_from_ast_coverage() -> None:
    from tools import audit_painter_painting_evidence as audit

    row = {
        "path": "app/painter_file_exchange.py",
        "function": "_tiff_integrity",
        "text": "ifd_end = ifd_offset + 2 + entry_count * 12 + 4",
    }

    assert audit._classify_numeric_literal_coverage(row) == (
        "candidate_explicit_ledger_tiff_header_and_ifd_structure_contract"
    )


def test_tiff_icc_tag_byte_type_is_an_explicit_defect_not_a_format_contract() -> None:
    from tools import audit_painter_painting_evidence as audit

    row = {
        "path": "app/painter_file_exchange.py",
        "function": "_write_tiff16",
        "text": "tags.append((34675, 1, len(icc), icc))",
    }

    assert audit._classify_numeric_literal_coverage(row) == (
        "unreviewed_tiff_icc_profile_tag_uses_byte_instead_of_undefined_type"
    )


def test_tiff_writer_baseline_tag_rows_are_routed_separately_from_icc_defect() -> None:
    from tools import audit_painter_painting_evidence as audit

    row = {
        "path": "app/painter_file_exchange.py",
        "function": "_write_tiff16",
        "text": "tags.extend([(256, 4, 1, width), (257, 4, 1, height)])",
    }

    assert audit._classify_numeric_literal_coverage(row) == (
        "candidate_explicit_ledger_tiff_writer_ifd_and_baseline_tag_contract"
    )


def test_png16_ihdr_and_phys_rows_do_not_inherit_compression_policy() -> None:
    from tools import audit_painter_painting_evidence as audit

    ihdr = {
        "path": "app/painter_file_exchange.py",
        "function": "_write_png16",
        "text": 'payload += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 16, 6, 0, 0, 0))',
    }
    compression = {
        "path": "app/painter_file_exchange.py",
        "function": "_write_png16",
        "text": 'payload += _png_chunk(b"IDAT", zlib.compress(raw, 6))',
    }

    assert audit._classify_numeric_literal_coverage(ihdr) == (
        "candidate_explicit_ledger_png16_ihdr_and_physical_pixel_contract"
    )
    assert audit._classify_numeric_literal_coverage(compression) == (
        "candidate_explicit_ledger_png16_zlib_encoding_policy_contract"
    )


def test_flat_image_bit_depth_offsets_are_routed_as_format_metadata() -> None:
    from tools import audit_painter_painting_evidence as audit

    png = {
        "path": "app/painter_file_exchange.py",
        "function": "inspect_flat_image",
        "text": "bits = int(header[24])",
    }
    tiff = {
        "path": "app/painter_file_exchange.py",
        "function": "inspect_flat_image",
        "text": 'tag_bits = image.tag_v2.get(258)',
    }

    expected = "candidate_explicit_ledger_flat_image_bit_depth_metadata_contract"
    assert audit._classify_numeric_literal_coverage(png) == expected
    assert audit._classify_numeric_literal_coverage(tiff) == expected


def test_exact_inch_and_icc_version_rows_have_separate_external_contracts() -> None:
    from tools import audit_painter_painting_evidence as audit

    inch = {
        "path": "app/painter_output.py",
        "function": "",
        "text": "MM_PER_INCH = 25.4",
    }
    icc = {
        "path": "app/painter_color_management.py",
        "function": "inspect_icc_profile",
        "text": "if version_major not in {2, 4}:",
    }

    assert audit._classify_numeric_literal_coverage(inch) == (
        "candidate_explicit_ledger_exact_international_inch_conversion_contract"
    )
    assert audit._classify_numeric_literal_coverage(icc) == (
        "candidate_explicit_ledger_icc_v2_v4_profile_version_contract"
    )


def test_tspaint_versions_route_to_a_tiger_contract_not_an_external_standard() -> None:
    from tools import audit_painter_painting_evidence as audit

    row = {
        "path": "app/painter_document_io.py",
        "function": "",
        "text": "PAINTER_DOCUMENT_VERSION = 5",
    }

    assert audit._classify_numeric_literal_coverage(row) == (
        "candidate_explicit_ledger_tspaint_v1_v2_v3_v4_v5_migration_contract"
    )


def test_uint16_conversion_rows_are_routed_without_png_compression_policy() -> None:
    from tools import audit_painter_painting_evidence as audit

    conversion = {
        "path": "app/painter_file_exchange.py",
        "function": "_rgba16_values",
        "text": 'return np.asarray(image.convert("RGBA"), dtype=np.uint16) * 257',
    }
    compression = {
        "path": "app/painter_file_exchange.py",
        "function": "_write_png16_gray",
        "text": 'payload += _png_chunk(b"IDAT", zlib.compress(raw, 6))',
    }
    integer_array = {
        "path": "app/painter_file_exchange.py",
        "function": "_rgba16_values",
        "text": "values = np.uint16(np.clip(values, 0, 65535))",
    }

    assert audit._classify_numeric_literal_coverage(conversion) == (
        "candidate_explicit_ledger_uint16_channel_conversion_and_shape_contract"
    )
    assert audit._classify_numeric_literal_coverage(compression) == (
        "candidate_explicit_ledger_png16_zlib_encoding_policy_contract"
    )
    assert audit._classify_numeric_literal_coverage(integer_array) == (
        "unreviewed_uint8_ndarray_is_not_scaled_to_uint16_full_range"
    )


def test_m53_persistence_exchange_rows_have_separate_evidence_contracts() -> None:
    from tools import audit_painter_painting_evidence as audit

    cases = (
        (
            {"path": "app/painter_file_exchange.py", "function": "_rgba16_to_rgba8", "text": "255"},
            "uint16_to_uint8_linear_rescaling_contract",
        ),
        (
            {"path": "app/painter_output.py", "function": "pixels_for_print", "text": "300"},
            "print_output_model_literal_contract",
        ),
        (
            {"path": "app/painter_autosave.py", "function": "_file_sha256", "text": "1024"},
            "recovery_snapshot_integrity_and_retention_literal_contract",
        ),
        (
            {"path": "app/painter_document_io.py", "function": "load_painter_document", "text": "64"},
            "tspaint_archive_integrity_and_asset_literal_contract",
        ),
        (
            {"path": "app/painter_recovery_dialog.py", "function": "_format_age", "text": "60"},
            "recovery_dialog_product_policy_literal_contract",
        ),
        (
            {"path": "app/painter_file_exchange.py", "function": "export_layered_psd", "text": "4"},
            "psd_exchange_policy_literal_contract",
        ),
        (
            {"path": "app/painter_file_exchange.py", "function": "inspect_flat_image", "text": "24"},
            "flat_export_and_inspection_policy_literal_contract",
        ),
    )

    for row, contract in cases:
        assert audit._classify_numeric_literal_coverage(row) == (
            f"candidate_explicit_ledger_{contract}"
        )


def test_action_schema_numeric_audit_links_action_ids_and_excludes_ui_design() -> None:
    from tools import audit_painter_painting_evidence as audit

    rows = audit._scan_paint_action_schema_numeric_domains(
        audit.ROOT / "app" / "actions" / "paint_namespace.py"
    )
    assert rows
    assert not any(str(row["action_id"]).startswith("paint.ui.") for row in rows)
    assert any(
        row["action_id"] == "paint.brush.set"
        and "PAINT_ACTION_MAX_BRUSH_WIDTH_PX" in row["text"]
        for row in rows
    )


def test_evidence_audit_source_inventory_hash_changes_with_input(tmp_path) -> None:
    from tools import audit_painter_painting_evidence as audit

    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")
    first = audit._source_inventory_provenance([source])
    source.write_text("value = 2\n", encoding="utf-8")
    second = audit._source_inventory_provenance([source])

    assert first["file_count"] == 1
    assert first["inventory_sha256"] != second["inventory_sha256"]
    assert first["files"][0]["sha256"] != second["files"][0]["sha256"]


def test_exception_function_name_cannot_auto_approve_suppression_contract() -> None:
    from tools import audit_painter_painting_evidence as audit

    row = {
        "path": "app/painter_opengl.py",
        "class": "",
        "function": "render_canvas_strokes_opengl_qimage",
        "text": "except Exception:",
    }
    status = audit._classify_suppressed_exception(row)
    assert status.startswith("candidate_explicit_ledger_exception_")
    assert audit._decision_basis(status) == "unresolved"


def test_gl_cleanup_audit_freezes_delegates_and_rejects_direct_teardown(
    tmp_path,
) -> None:
    from tools import audit_painter_painting_evidence as audit

    source = tmp_path / "painter_opengl.py"
    source.write_text(
        "def cleanup(surface):\n"
        "    _best_effort_gl_cleanup('surface', surface.destroy)\n",
        encoding="utf-8",
    )
    delegated, direct = audit._scan_gl_cleanup_contract([source])
    assert len(delegated) == 1
    assert direct == []

    source.write_text(
        "def cleanup(surface):\n"
        "    surface.destroy()\n",
        encoding="utf-8",
    )
    delegated, direct = audit._scan_gl_cleanup_contract([source])
    assert delegated == []
    assert len(direct) == 1
    assert direct[0]["review_status"] == "unreviewed_direct_gl_cleanup_call"

    source.write_text(
        "def cleanup(GL):\n"
        "    GL.glDeleteBuffers(1, [7])\n"
        "class Other:\n"
        "    def delete(self, surface):\n"
        "        surface.destroy()\n",
        encoding="utf-8",
    )
    delegated, direct = audit._scan_gl_cleanup_contract([source])
    assert delegated == []
    assert len(direct) == 2
    assert {row["function"] for row in direct} == {"cleanup", "delete"}


def test_advanced_brush_primitives_require_non_test_product_references(
    tmp_path,
) -> None:
    from tools import audit_painter_painting_evidence as audit

    orphan = tmp_path / "painter_advanced_brush.py"
    orphan.write_text("def dual_brush_intersection(): pass\n", encoding="utf-8")
    product = tmp_path / "drawing.py"
    product.write_text("value = 1\n", encoding="utf-8")
    missing = audit._advanced_brush_product_reference_matrix([orphan, product])
    assert not any(row["product_paths"] for row in missing)

    product.write_text(
        "from app.painter_advanced_brush import (\n"
        + "\n".join(f"    {symbol}," for symbol in audit.ADVANCED_BRUSH_PRODUCT_SYMBOLS)
        + "\n)\n"
        + "\n".join(f"{symbol}()" for symbol in audit.ADVANCED_BRUSH_PRODUCT_SYMBOLS),
        encoding="utf-8",
    )
    integrated = audit._advanced_brush_product_reference_matrix([orphan, product])
    assert all(row["product_paths"] for row in integrated)

    integrated_module = tmp_path / "painter_advanced_brush.py"
    integrated_module.write_text(
        "\n".join(
            f"def {symbol}(): pass" for symbol in audit.ADVANCED_BRUSH_PRODUCT_SYMBOLS
        )
        + "\n\ndef advanced_dab_alphas():\n"
        + "\n".join(
            f"    {symbol}()\n" for symbol in audit.ADVANCED_BRUSH_PRODUCT_SYMBOLS
        ),
        encoding="utf-8",
    )
    product.write_text(
        "from app.painter_advanced_brush import advanced_dab_alphas\n"
        "advanced_dab_alphas()\n",
        encoding="utf-8",
    )
    transitive = audit._advanced_brush_product_reference_matrix(
        [integrated_module, product]
    )
    assert all(row["product_paths"] for row in transitive)
    assert all(
        row["via_entry_points"] == ["advanced_dab_alphas"]
        for row in transitive
    )

    product.write_text(
        "from app.painter_advanced_brush import advanced_dab_alphas\n"
        "# advanced_dab_alphas()\n"
        "description = 'advanced_dab_alphas()'\n"
        "reference = advanced_dab_alphas\n",
        encoding="utf-8",
    )
    import_only = audit._advanced_brush_product_reference_matrix(
        [integrated_module, product]
    )
    assert not any(row["product_paths"] for row in import_only)

    for false_product in (
        "from unrelated import advanced_dab_alphas\nadvanced_dab_alphas()\n",
        "def advanced_dab_alphas(): pass\nadvanced_dab_alphas()\n",
        "class Other:\n    def advanced_dab_alphas(self): pass\nOther().advanced_dab_alphas()\n",
        "from app.painter_advanced_brush import advanced_dab_alphas\n"
        "def consume(advanced_dab_alphas):\n    advanced_dab_alphas()\n",
        "from app.painter_advanced_brush import advanced_dab_alphas\n"
        "def consume():\n    advanced_dab_alphas = lambda: None\n"
        "    advanced_dab_alphas()\n",
        "from app.painter_advanced_brush import advanced_dab_alphas\n"
        "def outer(advanced_dab_alphas):\n"
        "    def inner():\n"
        "        advanced_dab_alphas()\n",
        "from app.painter_advanced_brush import advanced_dab_alphas\n"
        "def consume():\n"
        "    advanced_dab_alphas, other = (lambda: None, 1)\n"
        "    advanced_dab_alphas()\n",
    ):
        product.write_text(false_product, encoding="utf-8")
        wrong_provenance = audit._advanced_brush_product_reference_matrix(
            [integrated_module, product]
        )
        assert not any(row["product_paths"] for row in wrong_provenance)

    product.write_text(
        "from app.painter_advanced_brush import advanced_dab_alphas as apply_advanced\n"
        "apply_advanced()\n",
        encoding="utf-8",
    )
    aliased = audit._advanced_brush_product_reference_matrix(
        [integrated_module, product]
    )
    assert all(row["product_paths"] for row in aliased)
