import json
from pathlib import Path
import pytest

from PIL import Image

from tools import build_full_product_catalog_decks as catalog


def test_full_product_catalog_locked_slide_order_includes_ppt_maker():
    assert len(catalog.PAGES) == 22
    assert catalog.PAGES[0].key == "studio_overview"
    assert catalog.PAGES[2].key == "ai_workflow"
    assert catalog.PAGES[3].key == "ppt_maker"
    assert catalog.PAGES[4].key == "media_pool"
    assert catalog.PAGES[-1].key == "closing"


def test_ppt_maker_page_requires_current_capture_assets():
    names = catalog._page_asset_names()

    assert "ppt_maker_editor" in names
    assert "debugCapture" not in str(catalog._asset("ppt_maker_editor"))
    ppt_page = next(page for page in catalog.PAGES if page.key == "ppt_maker")
    assert not ppt_page.uses_ipad()


def test_spec_closing_page_uses_locked_blue_pot_contract(tmp_path):
    assert catalog.PAGES[-1].key == "closing"
    assert catalog.SPEC_CLOSING_BONSAI.name == "bonsai_blue_pot_cutout_v1.png"
    assert catalog.SPEC_CLOSING_SHADOW_MODE == "pot_contact_only"
    assert catalog.SPEC_INDEX_SOURCE.name == "spec_index_groups.json"

    out_path = tmp_path / "spec_closing.png"
    catalog._make_spec_closing_slide(catalog.PAGES[-1], "en", 22, 22, out_path)

    assert out_path.exists()
    with Image.open(out_path) as img:
        assert img.size == (catalog.SLIDE_W, catalog.SLIDE_H)


def test_spec_index_source_covers_current_major_product_axes():
    groups = catalog._spec_index_groups("en")
    flattened = "\n".join([heading for heading, _ in groups] + [item for _, items in groups for item in items])

    assert len(groups) >= 12
    for term in [
        "PPT Maker",
        ".tgppt",
        "Music Lab",
        "Sound Editor",
        "Python Action",
        "MCP",
        "Local AI",
        "VTuber Studio",
        "AR/PBR",
        "Depth-aware",
        "PPTX",
        "MP4",
    ]:
        assert term in flattened


def test_spec_index_source_excludes_removed_or_report_terms():
    data = catalog._load_spec_index_payload()
    catalog._validate_spec_index_payload(data)
    groups = catalog._spec_index_groups("en")
    flattened = "\n".join([heading for heading, _ in groups] + [item for _, items in groups for item in items]).lower()

    for forbidden in ["mrq", "unreal bridge", "marmoset", "qa readiness", "release_ready", "pass/fail"]:
        assert forbidden not in flattened


def _color_page_spec() -> catalog.PageSpec:
    return catalog.PageSpec(
        key="color",
        section_en="FINISHING",
        title_en="Color Grading Workspace",
        body_en="Color controls.",
        section_ko="",
        title_ko="",
        body_ko="",
        ipad_contract="color_controls_only",
    )


def _write_image(path: Path, size: tuple[int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (20, 24, 28)).save(path)
    return path


def _write_semantic_sidecar(
    image_path: Path,
    *,
    asset_name: str,
    contract: str,
    tags: list[str],
    **fields: object,
) -> Path:
    path = catalog._contract_path_for_capture(image_path)
    data: dict[str, object] = {
        "schema": "tigercapture.product_catalog.semantic_capture_contract.v1",
        "semantic_contract": contract,
        "asset_name": asset_name,
        "evidence_tags": tags,
        "substituted_from_other_feature": False,
    }
    data.update(fields)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_vtuber_contract(
    path: Path,
    *,
    visual_source: str = "internal_vrm_fallback_render",
    product: bool = True,
    visible: list[str] | None = None,
    renderer_family: str = "vtuber_vrm",
    render_profile: str = "vrm_mtoon",
    renderer: str = "vrm_mtoon_gpu",
    gpu_renderer_used: bool = True,
    ar_pbr: bool = False,
    pbr: bool = False,
    source_exposure: str = "chest_up",
    framing_preset: str = "bust_up",
    selected_avatar_visibility: str = "head_to_mid_chest",
    fit_crop_mode: str = "bust_up",
    fit_crop_height_ratio: float | None = 0.38,
    program_avatar_height_ratio: float | None = 0.48,
    program_avatar_bottom_gap_ratio: float | None = 0.014,
    program_avatar_grounded: bool = True,
    inputs: dict[str, str] | None = None,
    catalog_outputs: dict[str, str] | None = None,
    catalog_output_sha256: dict[str, str] | None = None,
) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema": "tigercapture.review_vtuber_studio_capture.v1",
                "inputs": inputs or {},
                "avatar_evidence": {
                    "schema": "tigercapture.review_vtuber.avatar_evidence_contract.v1",
                    "source_mapping_subject": "trump_chest_up_performance_source",
                    "source_exposure": source_exposure,
                    "framing_preset": framing_preset,
                    "selected_avatar_visibility": selected_avatar_visibility,
                    "visibility_policy": {
                        "ai_rule": "match_source_person_exposure_to_vrm_visibility",
                        "source_exposure": source_exposure,
                        "minimum_framing_preset": "bust_up",
                        "selected_framing_preset": framing_preset,
                        "selected_avatar_visibility": selected_avatar_visibility,
                    },
                    "minimum_visible_parts": ["head", "neck", "shoulders", "upper_torso"],
                    "visible_parts": visible if visible is not None else ["head", "neck", "shoulders", "upper_torso"],
                    "review_product_evidence": product,
                    "framing_contract": "trump_chest_up_source_requires_bust_up_vrm",
                    "visual_source": visual_source,
                    "renderer": renderer,
                    "renderer_backend": renderer,
                    "renderer_family": renderer_family,
                    "render_profile": render_profile,
                    "gpu_renderer_required": True,
                    "gpu_renderer_used": gpu_renderer_used,
                    "fit_crop_mode": fit_crop_mode,
                    "fit_crop_height_ratio": fit_crop_height_ratio,
                    "program_avatar_height_ratio": program_avatar_height_ratio,
                    "program_avatar_bottom_gap_ratio": program_avatar_bottom_gap_ratio,
                    "program_avatar_grounded": program_avatar_grounded,
                    "program_avatar_fit_rule": "trim_alpha_then_large_bottom_anchor",
                    "ar_pbr_used": ar_pbr,
                    "pbr_used": pbr,
                },
                "catalog_outputs": catalog_outputs or {},
                "catalog_output_sha256": catalog_output_sha256 or {},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_color_ipad_detail_contract_accepts_controls_crop(tmp_path):
    path = _write_image(tmp_path / "color_controls_detail_action.png", (760, 420))

    ok, reason = catalog._ipad_detail_contract_is_ready(_color_page_spec(), path)

    assert ok, reason


def test_color_ipad_detail_contract_rejects_full_editor_size(tmp_path):
    path = _write_image(tmp_path / "color_controls_detail_action.png", (1480, 920))

    ok, reason = catalog._ipad_detail_contract_is_ready(_color_page_spec(), path)

    assert not ok
    assert "full editor" in reason
    assert "video viewer" in reason
    assert "timeline" in reason


def test_color_ipad_detail_contract_rejects_editor_named_source(tmp_path):
    path = _write_image(tmp_path / "editor_color_controls_detail_action.png", (760, 420))

    ok, reason = catalog._ipad_detail_contract_is_ready(_color_page_spec(), path)

    assert not ok
    assert "must not be a full editor" in reason


def test_vtuber_contract_accepts_upper_body_product_evidence(tmp_path):
    path = _write_vtuber_contract(tmp_path / "vtuber_capture_contract.json")

    ok, reason = catalog._vtuber_capture_contract_is_ready(path)

    assert ok, reason


def test_vtuber_contract_rejects_face_thumbnail(tmp_path):
    path = _write_vtuber_contract(
        tmp_path / "vtuber_capture_contract.json",
        visual_source="vrm_meta_thumbnail_texture",
        product=False,
        visible=["head"],
    )

    ok, reason = catalog._vtuber_capture_contract_is_ready(path)

    assert not ok
    assert "thumbnail" in reason


def test_vtuber_contract_rejects_missing_upper_torso(tmp_path):
    path = _write_vtuber_contract(
        tmp_path / "vtuber_capture_contract.json",
        visible=["head", "neck", "shoulders"],
    )

    ok, reason = catalog._vtuber_capture_contract_is_ready(path)

    assert not ok
    assert "upper_torso" in reason


def test_vtuber_contract_rejects_non_vtuber_renderer(tmp_path):
    path = _write_vtuber_contract(
        tmp_path / "vtuber_capture_contract.json",
        renderer_family="ar_pbr",
        render_profile="marmoset_pbr",
    )

    ok, reason = catalog._vtuber_capture_contract_is_ready(path)

    assert not ok
    assert "renderer boundary" in reason


def test_vtuber_contract_rejects_software_vrm_renderer(tmp_path):
    path = _write_vtuber_contract(
        tmp_path / "vtuber_capture_contract.json",
        renderer="vrm_mtoon_software",
        gpu_renderer_used=False,
    )

    ok, reason = catalog._vtuber_capture_contract_is_ready(path)

    assert not ok
    assert "GPU renderer" in reason


def test_vtuber_contract_rejects_trump_half_body_framing(tmp_path):
    path = _write_vtuber_contract(
        tmp_path / "vtuber_capture_contract.json",
        source_exposure="upper_body",
        framing_preset="half_body",
        selected_avatar_visibility="head_to_waist",
        fit_crop_mode="half_body",
        fit_crop_height_ratio=0.82,
    )

    ok, reason = catalog._vtuber_capture_contract_is_ready(path)

    assert not ok
    assert "chest-up" in reason or "bust_up" in reason


def test_vtuber_contract_rejects_trump_bust_label_with_wide_crop(tmp_path):
    path = _write_vtuber_contract(
        tmp_path / "vtuber_capture_contract.json",
        fit_crop_mode="bust_up",
        fit_crop_height_ratio=0.68,
    )

    ok, reason = catalog._vtuber_capture_contract_is_ready(path)

    assert not ok
    assert "actual bust_up crop" in reason


def test_vtuber_contract_rejects_trump_small_or_floating_program_avatar(tmp_path):
    path = _write_vtuber_contract(
        tmp_path / "vtuber_capture_contract.json",
        program_avatar_height_ratio=0.25,
        program_avatar_bottom_gap_ratio=0.11,
        program_avatar_grounded=False,
    )

    ok, reason = catalog._vtuber_capture_contract_is_ready(path)

    assert not ok
    assert "large and bottom-anchored" in reason


def _vtuber_required_inputs() -> dict[str, str]:
    return {
        "trump_performance_source": r"C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\trump_oval_office_live_GnzWEo_HfE0.mp4",
        "program_output_background": r"C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\South Korea 4K Drone Video ｜ Seoul, Busan, Songdo Cinematic Aerials [AA-sv3ilNBE].mp4",
        "vrm_avatar_target": r"E:\ClaudeCodeApp\GifCam\external\assets\vtuber\booth_milica\Milica1.3free\Milica_v1.3.vrm",
    }


def test_vtuber_asset_contract_accepts_bound_program_output(tmp_path):
    image_path = _write_image(tmp_path / "vtuber_program_output_action.png", (820, 460))
    contract_path = _write_vtuber_contract(
        tmp_path / "vtuber_capture_contract.json",
        inputs=_vtuber_required_inputs(),
        catalog_outputs={"vtuber_studio_program_output": str(image_path)},
        catalog_output_sha256={"vtuber_studio_program_output": catalog._image_sha256(image_path)},
    )

    ok, reason = catalog._vtuber_asset_contract_is_ready(
        "vtuber_studio_program_output",
        image_path,
        contract_path=contract_path,
    )

    assert ok, reason


def test_vtuber_asset_contract_rejects_unbound_substitution(tmp_path):
    contract_image = _write_image(tmp_path / "vtuber_program_output_action.png", (820, 460))
    slide_image = _write_image(tmp_path / "other_program_output_action.png", (820, 460))
    contract_path = _write_vtuber_contract(
        tmp_path / "vtuber_capture_contract.json",
        inputs=_vtuber_required_inputs(),
        catalog_outputs={"vtuber_studio_program_output": str(contract_image)},
        catalog_output_sha256={"vtuber_studio_program_output": catalog._image_sha256(contract_image)},
    )

    ok, reason = catalog._vtuber_asset_contract_is_ready(
        "vtuber_studio_program_output",
        slide_image,
        contract_path=contract_path,
    )

    assert not ok
    assert "not the slide source" in reason


def test_vtuber_asset_contract_rejects_ar_pbr_camera_contamination(tmp_path):
    image_path = _write_image(tmp_path / "polyhaven_pbr_camera_scene" / "Camera_01_1k.png", (820, 460))
    contract_path = _write_vtuber_contract(
        tmp_path / "vtuber_capture_contract.json",
        inputs=_vtuber_required_inputs(),
        catalog_outputs={"vtuber_studio_program_output": str(image_path)},
        catalog_output_sha256={"vtuber_studio_program_output": catalog._image_sha256(image_path)},
    )

    ok, reason = catalog._vtuber_asset_contract_is_ready(
        "vtuber_studio_program_output",
        image_path,
        contract_path=contract_path,
    )

    assert not ok
    assert "forbidden non-VTuber" in reason


def test_vtuber_asset_contract_rejects_missing_hash_binding(tmp_path):
    image_path = _write_image(tmp_path / "vtuber_program_output_action.png", (820, 460))
    contract_path = _write_vtuber_contract(
        tmp_path / "vtuber_capture_contract.json",
        inputs=_vtuber_required_inputs(),
        catalog_outputs={"vtuber_studio_program_output": str(image_path)},
    )

    ok, reason = catalog._vtuber_asset_contract_is_ready(
        "vtuber_studio_program_output",
        image_path,
        contract_path=contract_path,
    )

    assert not ok
    assert "catalog_output_sha256" in reason


def test_multi_monitor_center_rejects_weak_autostamped_contract(tmp_path):
    image_path = _write_image(tmp_path / "center_monitor_editor_action.png", (1480, 920))
    _write_semantic_sidecar(
        image_path,
        asset_name="overview_center_editor",
        contract="multi_monitor_center_editor_v1",
        tags=["main_video_preview", "timeline", "ai_command"],
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("overview_center_editor", image_path)

    assert not ok
    assert "monitor_role" in reason


def test_multi_monitor_center_accepts_locked_lamborghini_editor_contract(tmp_path):
    image_path = _write_image(tmp_path / "center_monitor_editor_action.png", (1480, 920))
    _write_semantic_sidecar(
        image_path,
        asset_name="overview_center_editor",
        contract="multi_monitor_center_editor_v1",
        tags=[
            "center_monitor",
            "main_video_preview",
            "timeline",
            "ai_command",
            "real_tigercapture_capture",
            "lamborghini_clip",
            "long_timeline",
            "multi_track_timeline",
            "ai_command_secondary",
        ],
        monitor_role="center",
        visible_track_count=4,
        source_media="Lamborghini Revuelto - From Now On.mp4",
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("overview_center_editor", image_path)

    assert ok, reason


def test_multi_monitor_left_requires_actor_asset_and_neutral_3d_context(tmp_path):
    image_path = _write_image(tmp_path / "left_monitor_actor_3d_vtuber_action.png", (1480, 920))
    _write_semantic_sidecar(
        image_path,
        asset_name="overview_left_workspace",
        contract="multi_monitor_left_workspace_v1",
        tags=["left_monitor", "live2d_viewer", "ar_pbr_viewer", "real_tigercapture_capture"],
        monitor_role="left",
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("overview_left_workspace", image_path)

    assert not ok
    assert "MMD/VRM/VTuber" in reason


def test_multi_monitor_left_accepts_actor_asset_3d_support_contract(tmp_path):
    image_path = _write_image(tmp_path / "left_monitor_actor_3d_vtuber_action.png", (1480, 920))
    _write_semantic_sidecar(
        image_path,
        asset_name="overview_left_workspace",
        contract="multi_monitor_left_workspace_v1",
        tags=[
            "left_monitor",
            "live2d_viewer",
            "ar_pbr_viewer",
            "mmd_viewer",
            "asset_preset_support",
            "cubemap_hidden",
            "real_tigercapture_capture",
        ],
        monitor_role="left",
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("overview_left_workspace", image_path)

    assert ok, reason


def test_multi_monitor_right_requires_node_dominant_audio_contract(tmp_path):
    image_path = _write_image(tmp_path / "right_monitor_node_audio_action.png", (1480, 920))
    _write_semantic_sidecar(
        image_path,
        asset_name="overview_right_workspace",
        contract="multi_monitor_right_workspace_v1",
        tags=["right_monitor", "node_graph", "sound_editor", "real_tigercapture_capture"],
        monitor_role="right",
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("overview_right_workspace", image_path)

    assert not ok
    assert "dominant" in reason


def test_multi_monitor_right_accepts_node_dominant_audio_contract(tmp_path):
    image_path = _write_image(tmp_path / "right_monitor_node_audio_action.png", (1480, 920))
    _write_semantic_sidecar(
        image_path,
        asset_name="overview_right_workspace",
        contract="multi_monitor_right_workspace_v1",
        tags=[
            "right_monitor",
            "node_graph",
            "node_graph_dominant",
            "sound_editor",
            "audio_scopes",
            "real_tigercapture_capture",
        ],
        monitor_role="right",
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("overview_right_workspace", image_path)

    assert ok, reason


def _write_audio_report(path: Path) -> Path:
    required: set[str] = set()
    for name in ("sound_editor", "sound_workbench", "sound_graphs"):
        required.update(catalog._audio_contract_required_checks(name))
    path.write_text(
        json.dumps(
            {
                "scenario": "ui_renewal_sound_editor",
                "sound_editor_ui_contract_version": catalog.SOUND_EDITOR_CURRENT_UI_CONTRACT_VERSION,
                "checks": {key: True for key in sorted(required)},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def test_sound_editor_contract_rejects_stale_audio_capture(tmp_path):
    image_path = _write_image(tmp_path / "editor_sound_editor_action.png", (1480, 920))
    report_path = _write_audio_report(tmp_path / "sound_editor_qa.json")
    _write_semantic_sidecar(
        image_path,
        asset_name="sound_editor",
        contract="sound_editor_current_ui_v1",
        tags=[
            "sound_editor",
            "current_sound_editor_ui",
            "real_tigercapture_capture",
            "audio_waveform",
            "sound_jog_shuttle",
            "audio_mixer",
            "workbench_sound_editor",
        ],
        current_sound_editor_ui=True,
        source_report=str(report_path),
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("sound_editor", image_path)

    assert not ok
    assert "stale" in reason.lower()


def test_sound_editor_contract_accepts_current_workbench_audio_ui(tmp_path):
    image_path = _write_image(tmp_path / "editor_sound_editor_action.png", (1480, 920))
    report_path = _write_audio_report(tmp_path / "sound_editor_qa.json")
    _write_semantic_sidecar(
        image_path,
        asset_name="sound_editor",
        contract="sound_editor_current_ui_v1",
        tags=[
            "sound_editor",
            "current_sound_editor_ui",
            "real_tigercapture_capture",
            "audio_waveform",
            "sound_jog_shuttle",
            "audio_mixer",
            "workbench_sound_editor",
        ],
        sound_editor_ui_contract_version=catalog.SOUND_EDITOR_CURRENT_UI_CONTRACT_VERSION,
        current_sound_editor_ui=True,
        source_report=str(report_path),
        legacy_sound_editor_window_only=False,
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("sound_editor", image_path)

    assert ok, reason


def test_compare_capture_contract_requires_non_neutral_sidecar(tmp_path):
    image_path = _write_image(tmp_path / "editor_color_before_after_action.png", (1480, 920))

    ok, reason = catalog._compare_capture_contract_is_ready("color_before_after_editor", image_path)

    assert not ok
    assert "sidecar" in reason


def test_compare_capture_contract_rejects_missing_action_execution_proof(tmp_path):
    image_path = _write_image(tmp_path / "editor_color_before_after_action.png", (1480, 920))
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.review.compare_capture_contract.v1",
                "viewer_compare_mode": "split",
                "visible_delta": True,
                "neutral_identity": False,
                "changed_params": {
                    "contrast": {"before": 0.0, "after": 18.0, "neutral": 0.0},
                    "saturation": {"before": 0.0, "after": 12.0, "neutral": 0.0},
                },
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._compare_capture_contract_is_ready("color_before_after_editor", image_path)

    assert not ok
    assert "action execution log" in reason


def test_compare_capture_contract_accepts_visible_non_neutral_delta_with_actions(tmp_path):
    image_path = _write_image(tmp_path / "editor_color_before_after_action.png", (1480, 920))
    source_report = tmp_path / "color_capture_report.json"
    source_report.write_text(
        json.dumps(
            {
                "ok": True,
                "checks": {
                    "viewer_frame_visible": True,
                    "color_dock_viewer_reforced": True,
                    "viewer_compare_split": True,
                    "color_before_after_visual_delta": True,
                },
                "before_after_visual_delta_scores": {"color": 8.5},
                "steps": [
                    {"action": "media.import_to_timeline", "ok": True},
                    {"action": "clip.set_color_grade", "ok": True},
                    {"action": "ui.viewer.compare.set", "ok": True},
                    {"action": "capture.screenshot", "ok": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.review.compare_capture_contract.v1",
                "viewer_compare_mode": "split",
                "visible_delta": True,
                "neutral_identity": False,
                "source_report": str(source_report),
                "changed_params": {
                    "contrast": {"before": 0.0, "after": 18.0, "neutral": 0.0},
                    "saturation": {"before": 0.0, "after": 12.0, "neutral": 0.0},
                },
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._compare_capture_contract_is_ready("color_before_after_editor", image_path)

    assert ok, reason


def test_compare_capture_contract_accepts_required_checks_when_nonessential_report_check_fails(tmp_path):
    image_path = _write_image(tmp_path / "editor_color_before_after_action.png", (1480, 920))
    source_report = tmp_path / "color_capture_report.json"
    source_report.write_text(
        json.dumps(
            {
                "ok": False,
                "checks": {
                    "viewer_frame_visible": True,
                    "color_dock_viewer_reforced": True,
                    "viewer_compare_split": True,
                    "color_before_after_visual_delta": True,
                    "ai_command_open_screenshot": False,
                },
                "before_after_visual_delta_scores": {"color": 8.5},
                "steps": [
                    {"action": "clip.set_color_grade", "ok": True},
                    {"action": "ui.viewer.compare.set", "ok": True},
                    {"action": "capture.screenshot", "ok": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.review.compare_capture_contract.v1",
                "viewer_compare_mode": "split",
                "visible_delta": True,
                "neutral_identity": False,
                "source_report": str(source_report),
                "changed_params": {
                    "temperature": {"before": 0.0, "after": 2.1, "neutral": 0.0},
                    "contrast": {"before": 1.0, "after": 1.18, "neutral": 1.0},
                },
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._compare_capture_contract_is_ready("color_before_after_editor", image_path)

    assert ok, reason


def test_compare_capture_contract_rejects_missing_visual_delta_score(tmp_path):
    image_path = _write_image(tmp_path / "editor_color_before_after_action.png", (1480, 920))
    source_report = tmp_path / "color_capture_report.json"
    source_report.write_text(
        json.dumps(
            {
                "ok": True,
                "checks": {
                    "viewer_frame_visible": True,
                    "color_dock_viewer_reforced": True,
                    "viewer_compare_split": True,
                    "color_before_after_visual_delta": True,
                },
                "steps": [
                    {"action": "clip.set_color_grade", "ok": True},
                    {"action": "ui.viewer.compare.set", "ok": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.review.compare_capture_contract.v1",
                "viewer_compare_mode": "split",
                "visible_delta": True,
                "neutral_identity": False,
                "source_report": str(source_report),
                "changed_params": {
                    "temperature": {"before": 0.0, "after": 2.1, "neutral": 0.0},
                    "contrast": {"before": 1.0, "after": 1.18, "neutral": 1.0},
                },
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._compare_capture_contract_is_ready("color_before_after_editor", image_path)

    assert not ok
    assert "visual-delta score" in reason


def test_compare_capture_contract_rejects_low_visual_delta_score(tmp_path):
    image_path = _write_image(tmp_path / "editor_color_before_after_action.png", (1480, 920))
    source_report = tmp_path / "color_capture_report.json"
    source_report.write_text(
        json.dumps(
            {
                "ok": True,
                "checks": {
                    "viewer_frame_visible": True,
                    "color_dock_viewer_reforced": True,
                    "viewer_compare_split": True,
                    "color_before_after_visual_delta": True,
                },
                "before_after_visual_delta_scores": {"color": 0.7},
                "steps": [
                    {"action": "clip.set_color_grade", "ok": True},
                    {"action": "ui.viewer.compare.set", "ok": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.review.compare_capture_contract.v1",
                "viewer_compare_mode": "split",
                "visible_delta": True,
                "neutral_identity": False,
                "source_report": str(source_report),
                "before_after_visual_delta_score": 0.7,
                "changed_params": {
                    "temperature": {"before": 0.0, "after": 2.1, "neutral": 0.0},
                    "contrast": {"before": 1.0, "after": 1.18, "neutral": 1.0},
                },
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._compare_capture_contract_is_ready("color_before_after_editor", image_path)

    assert not ok
    assert "insufficient visual delta" in reason


def test_color_compare_contract_rejects_failed_viewer_checks(tmp_path):
    image_path = _write_image(tmp_path / "editor_color_before_after_action.png", (1480, 920))
    source_report = tmp_path / "color_capture_report.json"
    source_report.write_text(
        json.dumps(
            {
                "ok": True,
                "checks": {
                    "viewer_frame_visible": True,
                    "color_dock_viewer_reforced": False,
                    "viewer_compare_split": True,
                    "color_before_after_visual_delta": True,
                },
                "before_after_visual_delta_scores": {"color": 8.5},
                "steps": [
                    {"action": "clip.set_color_grade", "ok": True},
                    {"action": "ui.viewer.compare.set", "ok": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.review.compare_capture_contract.v1",
                "viewer_compare_mode": "split",
                "visible_delta": True,
                "neutral_identity": False,
                "source_report": str(source_report),
                "changed_params": {
                    "contrast": {"before": 0.0, "after": 18.0, "neutral": 0.0},
                },
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._compare_capture_contract_is_ready("color_before_after_editor", image_path)

    assert not ok
    assert "color_dock_viewer_reforced" in reason


def test_node_compare_contract_rejects_missing_compare_action(tmp_path):
    image_path = _write_image(tmp_path / "editor_node_before_after_action.png", (1480, 920))
    source_report = tmp_path / "node_capture_report.json"
    source_report.write_text(
        json.dumps(
            {
                "ok": True,
                "checks": {
                    "node_graph_action_ok": True,
                    "viewer_frame_visible": True,
                    "viewer_compare_split": True,
                    "workbench_screenshot": True,
                    "visible_node_count": True,
                    "node_before_after_visual_delta": True,
                },
                "before_after_visual_delta_scores": {"node_effect": 8.5},
                "steps": [{"action": "node.graph.set", "ok": True}],
            }
        ),
        encoding="utf-8",
    )
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.review.compare_capture_contract.v1",
                "viewer_compare_mode": "split",
                "visible_delta": True,
                "neutral_identity": False,
                "source_report": str(source_report),
                "changed_params": {
                    "blur_node.size": {"before": 0.0, "after": 18.7},
                },
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._compare_capture_contract_is_ready("node_before_after_editor", image_path)

    assert not ok
    assert "ui.viewer.compare.set" in reason


def test_live2d_composite_contract_requires_main_viewer_actor_visibility(tmp_path):
    image_path = _write_image(tmp_path / "editor_live2d_actor_composite_action.png", (1480, 920))
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.product_catalog.semantic_capture_contract.v1",
                "semantic_contract": "live2d_composite_editor_v1",
                "asset_name": "live2d_composite_editor",
                "evidence_tags": ["actor_lane", "live2d_actor"],
                "substituted_from_other_feature": False,
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("live2d_composite_editor", image_path)

    assert not ok
    assert "main editor viewer" in reason


def test_live2d_composite_contract_accepts_main_viewer_actor_visibility(tmp_path):
    image_path = _write_image(tmp_path / "editor_live2d_actor_composite_action.png", (1480, 920))
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.product_catalog.semantic_capture_contract.v1",
                "semantic_contract": "live2d_composite_editor_v1",
                "asset_name": "live2d_composite_editor",
                "evidence_tags": ["actor_lane", "live2d_actor"],
                "substituted_from_other_feature": False,
                "main_viewer_actor_visible": True,
                "viewer_actor_overlay_visible": True,
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("live2d_composite_editor", image_path)

    assert ok, reason


def test_mmd_contract_rejects_first_frame_capture(tmp_path):
    image_path = _write_image(tmp_path / "editor_mmd_character_composite_action.png", (1480, 920))
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.product_catalog.semantic_capture_contract.v1",
                "semantic_contract": "mmd_composite_editor_v1",
                "asset_name": "mmd_composite_editor",
                "evidence_tags": ["actor_lane", "mmd_character"],
                "substituted_from_other_feature": False,
                "main_viewer_actor_visible": True,
                "viewer_actor_overlay_visible": True,
                "first_frame_used": True,
                "capture_frame_position": "first_frame",
                "capture_time_ms": 0,
                "mmd_motion_active": False,
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("mmd_composite_editor", image_path)

    assert not ok
    assert "frame 0" in reason or "first_frame" in reason


def test_mmd_contract_accepts_middle_motion_frame_capture(tmp_path):
    image_path = _write_image(tmp_path / "mmd_character_detail_action.png", (760, 420))
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.product_catalog.semantic_capture_contract.v1",
                "semantic_contract": "mmd_viewer_detail_v1",
                "asset_name": "mmd_character_detail",
                "evidence_tags": ["mmd_viewer", "mmd_character"],
                "substituted_from_other_feature": False,
                "first_frame_used": False,
                "capture_frame_position": "mid_motion",
                "capture_time_ms": 2600,
                "capture_progress": 0.5,
                "mmd_motion_active": True,
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("mmd_character_detail", image_path)

    assert ok, reason


def test_typography_detail_contract_rejects_single_caption(tmp_path):
    image_path = _write_image(tmp_path / "title_animation_detail_action.png", (760, 420))
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.product_catalog.semantic_capture_contract.v1",
                "semantic_contract": "typography_detail_v1",
                "asset_name": "typography_detail",
                "evidence_tags": ["typography_controls", "multiple_text_styles"],
                "substituted_from_other_feature": False,
                "visible_text_layer_count": 1,
                "large_headline_visible": True,
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("typography_detail", image_path)

    assert not ok
    assert "four visible typography layers" in reason


def test_typography_detail_contract_accepts_rich_multilayer_text(tmp_path):
    image_path = _write_image(tmp_path / "title_animation_detail_action.png", (760, 420))
    catalog._contract_path_for_capture(image_path).write_text(
        json.dumps(
            {
                "schema": "tigercapture.product_catalog.semantic_capture_contract.v1",
                "semantic_contract": "typography_detail_v1",
                "asset_name": "typography_detail",
                "evidence_tags": ["typography_controls", "multiple_text_styles"],
                "substituted_from_other_feature": False,
                "visible_text_layer_count": 4,
                "large_headline_visible": True,
                "secondary_text_visible": True,
                "multilingual_text_visible": True,
                "small_caption_text_visible": True,
            }
        ),
        encoding="utf-8",
    )

    ok, reason = catalog._semantic_capture_contract_is_ready("typography_detail", image_path)

    assert ok, reason


def test_semantic_visual_contract_rejects_black_capture(tmp_path):
    image_path = _write_image(tmp_path / "live2d_actor_detail_action.png", (760, 420))

    ok, reason = catalog._semantic_capture_visual_is_ready("live2d_actor_detail", image_path)

    assert not ok
    assert "black" in reason or "flat" in reason


def test_semantic_visual_contract_rejects_timeline_strip_fragment(tmp_path):
    image_path = tmp_path / "transition_timeline_detail_action.png"
    img = Image.new("RGB", (900, 600), (8, 8, 8))
    for y in range(520, 560):
        for x in range(80, 840):
            img.putpixel((x, y), (70 + (x % 40), 75 + (x % 30), 80 + (x % 20)))
    img.save(image_path)

    ok, reason = catalog._semantic_capture_visual_is_ready("transition_detail", image_path)

    assert not ok
    assert "thin strip" in reason or "too little visible content" in reason


def test_screen_region_quality_rejects_blank_template_area():
    blank = Image.new("RGB", (640, 360), (18, 18, 18))

    ok, reason = catalog._screen_region_is_catalog_ready(blank, label="test.laptop_screen")

    assert not ok
    assert "black" in reason or "flat" in reason


def test_screen_region_quality_accepts_realistic_editor_area():
    img = Image.new("RGB", (640, 360), (15, 18, 22))
    for y in range(30, 320):
        for x in range(45, 600):
            if (x // 18 + y // 12) % 3 == 0:
                img.putpixel((x, y), (52 + x % 70, 65 + y % 80, 86 + (x + y) % 90))

    ok, reason = catalog._screen_region_is_catalog_ready(img, label="test.laptop_screen")

    assert ok, reason


def test_color_editor_viewer_region_rejects_black_viewer_even_when_workbench_is_busy(tmp_path):
    image_path = tmp_path / "editor_color_before_after_action.png"
    img = Image.new("RGB", (1480, 920), (18, 22, 28))
    # Real color-grading failure mode: the left viewer is black, but the right
    # color workbench is visually busy enough to fool the generic wide box.
    for y in range(126, 503):
        for x in range(206, 592):
            img.putpixel((x, y), (0, 0, 0))
    for y in range(126, 503):
        for x in range(620, 890):
            if (x + y) % 7 == 0:
                img.putpixel((x, y), (130, 155, 185))
            else:
                img.putpixel((x, y), (42, 50, 62))
    img.save(image_path)

    ok, reason = catalog._editor_viewer_region_is_catalog_ready(
        image_path,
        asset_name="color_before_after_editor",
    )

    assert not ok
    assert "Viewer region appears blank/black" in reason


def test_validate_pptx_rejects_non_zip_file(tmp_path):
    bad = tmp_path / "broken.pptx"
    bad.write_bytes(b"not a pptx")

    with pytest.raises(RuntimeError, match="valid PPTX"):
        catalog.validate_pptx(bad, expected_slides=1)


def test_cross_feature_duplicate_errors_rejects_reused_actor_images(tmp_path, monkeypatch):
    img_path = _write_image(tmp_path / "actor.png", (760, 420))
    original_asset = catalog._asset

    def fake_asset(name: str) -> Path:
        if name in {"live2d_actor_detail", "mmd_character_detail"}:
            return img_path
        return original_asset(name)

    monkeypatch.setattr(catalog, "_asset", fake_asset)

    errors = catalog._cross_feature_duplicate_errors({"live2d_actor_detail", "mmd_character_detail"})

    assert errors
    assert "Cross-feature duplicate evidence" in errors[0]
