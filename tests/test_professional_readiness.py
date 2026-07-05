from __future__ import annotations


def test_professional_readiness_flags_long_project_parity_timeline_color_audio():
    from app.professional_readiness import build_professional_readiness_report

    doc = {
        "project_settings": {"fps": 30.0},
        "video_tracks": [{
            "clips": [
                {
                    "id": 1,
                    "timeline_in_ms": 0,
                    "source_in_ms": 0,
                    "source_out_ms": 3_700_000,
                    "linked_audio_id": 99,
                    "video_filters": {"enabled": True},
                    "chroma_key": {"enabled": True},
                    "bg_removal": {"enabled": True},
                    "masks": [{"track_object": True}],
                    "node_graph": {"color": {"grade": {"brightness": 10}}},
                },
                {
                    "id": 2,
                    "timeline_in_ms": 3_699_990,
                    "source_in_ms": 0,
                    "source_out_ms": 1000,
                },
            ],
        }],
        "audio_tracks": [
            {
                "id": 1,
                "bus_id": "master",
                "clips": [{
                    "id": 1,
                    "offset_ms": 0,
                    "duration_ms": 3000,
                    "effects": {},
                }],
            },
            {
                "id": 2,
                "bus_id": "master",
                "clips": [{
                    "id": 2,
                    "offset_ms": 4000,
                    "duration_ms": 3000,
                    "effects": {},
                }],
            },
        ],
        "spine_actor_tracks": [{"clips": [{"start_ms": 0, "duration_ms": 1000}]}],
    }

    report = build_professional_readiness_report(doc)

    assert report["ok"] is False
    assert report["issue_summary"]["high"] >= 3
    sections = report["sections"]
    assert sections["long_project_stability"]["duration_ms"] >= 3_700_000
    assert sections["gpu_preview_export_consistency"]["raw_or_cpu_features"]["background_removal"] == 1
    assert sections["timeline_edit_integrity"]["overlap_count"] == 0
    assert sections["timeline_edit_integrity"]["micro_overlap_count"] == 1
    assert sections["timeline_edit_integrity"]["auto_fixable_edge_count"] == 1
    assert sections["timeline_edit_integrity"]["missing_link_count"] == 1
    assert sections["color_workflow_depth"]["score"] < 100
    assert sections["audio_mix_readiness"]["bus_counts"]["master"] == 2


def test_professional_readiness_keeps_large_timeline_overlap_high_risk():
    from app.professional_readiness import build_professional_readiness_report

    doc = {
        "project_settings": {"fps": 30.0},
        "video_tracks": [{
            "clips": [
                {
                    "id": 1,
                    "timeline_in_ms": 0,
                    "source_in_ms": 0,
                    "source_out_ms": 1000,
                },
                {
                    "id": 2,
                    "timeline_in_ms": 900,
                    "source_in_ms": 0,
                    "source_out_ms": 1000,
                },
            ],
        }],
    }

    report = build_professional_readiness_report(doc)
    timeline = report["sections"]["timeline_edit_integrity"]

    assert timeline["overlap_count"] == 1
    assert timeline["micro_overlap_count"] == 0
    assert any(
        issue["severity"] == "high"
        and issue["message"] == "Timeline contains overlapping clips on the same lane."
        for issue in timeline["issues"]
    )


def test_professional_readiness_accepts_prepared_color_audio_project():
    from app.audio_workflow import dialogue_cleanup_effects, loudness_target
    from app.professional_readiness import build_professional_readiness_report

    doc = {
        "project_settings": {
            "fps": 30.0,
            "color_management": {
                "output_space": "Rec.709",
                "output_transfer": "bt709",
            },
        },
        "video_tracks": [{
            "clips": [{
                "id": 1,
                "timeline_in_ms": 0,
                "source_in_ms": 0,
                "source_out_ms": 3000,
                "linked_audio_id": 10,
                "color_workflow": {
                    "enabled": True,
                    "qualifier": {
                        "enabled": True,
                        "clean_black": 0.2,
                        "clean_white": 0.2,
                    },
                    "window": {
                        "enabled": True,
                        "track_object": True,
                    },
                },
            }],
        }],
        "audio_tracks": [{
            "id": 1,
            "bus_id": "dialogue",
            "automation_points": [(0.0, 1.0), (1.0, 0.8)],
            "clips": [{
                "id": 10,
                "offset_ms": 0,
                "duration_ms": 3000,
                "effects": {
                    **dialogue_cleanup_effects(strength=0.7),
                    "loudness": loudness_target("podcast").to_effect_payload(),
                },
            }],
        }],
    }

    report = build_professional_readiness_report(doc)

    assert report["ok"] is True
    assert report["score"] >= 95
    assert report["sections"]["timeline_edit_integrity"]["missing_link_count"] == 0
    assert report["sections"]["color_workflow_depth"]["counts"]["tracked_windows"] == 1
    assert report["sections"]["color_workflow_depth"]["scope_accuracy"]["ok"] is True
    assert report["sections"]["audio_mix_readiness"]["counts"]["loudness"] == 1
    assert report["sections"]["preset_template_ecosystem"]["score"] == 100
    assert report["sections"]["preset_template_ecosystem"]["template_reference_issues"] == []


def test_professional_readiness_tracks_deep_color_audio_export_parity():
    from app.audio_workflow import dialogue_cleanup_effects, loudness_target
    from app.professional_readiness import build_professional_readiness_report

    doc = {
        "project_settings": {
            "fps": 24.0,
            "color_management": {
                "input_space": "sRGB",
                "working_space": "ACEScg",
                "output_space": "Rec.2020",
                "output_transfer": "PQ",
                "view_transform": "aces-1.3",
                "preview_transform_enabled": True,
                "input_lut": {"path": "show_input.cube", "strength": 1.0, "enabled": True},
                "creative_lut": {"path": "look.cube", "strength": 0.6, "enabled": True},
            },
        },
        "video_tracks": [{
            "clips": [{
                "id": 1,
                "timeline_in_ms": 0,
                "source_in_ms": 0,
                "source_out_ms": 3000,
                "linked_audio_id": 10,
                "color_grade": {
                    "brightness": 8,
                    "creative_lut_path": "clip_look.cube",
                    "creative_lut_strength": 0.75,
                    "color_workflow": {
                        "enabled": True,
                        "qualifier": {
                            "enabled": True,
                            "softness": 0.18,
                            "clean_black": 0.1,
                        },
                        "window": {
                            "enabled": True,
                            "track_object": True,
                        },
                        "curves": {
                            "master": [[0, 0], [255, 245]],
                        },
                    },
                },
            }],
        }],
        "audio_tracks": [
            {
                "id": 1,
                "bus_id": "dialogue",
                "automation_points": [(0.0, 1.0), (2.0, 0.85)],
                "clips": [{
                    "id": 10,
                    "offset_ms": 0,
                    "duration_ms": 3000,
                    "effects": {
                        **dialogue_cleanup_effects(strength=0.75),
                        "loudness": loudness_target("podcast").to_effect_payload(),
                    },
                }],
            },
            {
                "id": 2,
                "bus_id": "music",
                "clips": [{
                    "id": 11,
                    "offset_ms": 0,
                    "duration_ms": 3000,
                    "effects": {
                        "eq": {"enabled": True},
                        "comp": {"enabled": True},
                        "loudness": loudness_target("shortform").to_effect_payload(),
                    },
                }],
            },
        ],
    }

    report = build_professional_readiness_report(doc)
    gpu = report["sections"]["gpu_preview_export_consistency"]
    color = report["sections"]["color_workflow_depth"]
    audio = report["sections"]["audio_mix_readiness"]

    assert color["counts"]["hdr_color_management"] == 1
    assert color["counts"]["project_luts"] == 2
    assert color["counts"]["grade_luts"] == 1
    assert color["counts"]["tracked_windows"] == 1
    assert color["counts"]["curves"] == 1
    assert color["color_management"]["working_space"] == "acescg"
    assert any("ACES" in warning for warning in color["color_management"]["warnings"])
    assert gpu["color_parity_features"]["hdr_metadata"] == 1
    assert gpu["color_parity_features"]["project_luts"] == 2
    assert gpu["color_parity_features"]["grade_luts"] == 1
    assert gpu["audio_parity_features"]["audio_effect_graph"] >= 5
    assert gpu["audio_parity_features"]["audio_automation"] == 1
    assert any(
        check["feature"] == "project_luts"
        and check["check"] == "preview/export LUT bake sample"
        for check in gpu["parity_checks"]
    )
    assert audio["role_counts"]["dialogue"] == 1
    assert audio["role_counts"]["music"] == 1
    assert audio["counts"]["deesser"] == 1
    assert audio["counts"]["compression"] == 1


def test_resolve_parity_reads_project_level_workflow_payloads():
    from app.professional_readiness import audit_resolve_post_pipeline_parity

    doc = {
        "project_settings": {},
        "audio_routing_matrix": {
            "buses": [{"id": "dialogue", "name": "Dialogue"}, {"id": "master", "name": "Master"}],
            "track_routes": {"1": "dialogue"},
            "sends": [{"source_bus": "dialogue", "target_bus": "master"}],
        },
        "vfx_repair_plans": [{"clean_plate": {"enabled": True}}],
        "proxy_render_cache": {"render_cache": True, "optimized_media": True},
        "deliver_jobs": [{"id": "web_1080p"}],
        "ingest_clone_manifest": {"verified_clone": True, "item_count": 1},
        "video_tracks": [{"clips": [{"id": 1, "chroma_key": {"enabled": True}}]}],
    }

    report = audit_resolve_post_pipeline_parity(doc)

    def status(category: str, feature_id: str) -> str:
        for feature in report["categories"][category]["features"]:
            if feature["id"] == feature_id:
                return feature["status"]
        raise AssertionError(feature_id)

    assert status("audio", "flexbus_routing") == "supported"
    assert status("vfx_fusion", "keying_roto") == "supported"
    assert status("performance", "proxy_render_cache") == "supported"
    assert status("post_pipeline", "media_ingest_clone") == "supported"
    assert status("post_pipeline", "deliver_page") == "supported"


def test_resolve_fairlight_fusion_depth_cards_surface_product_roadmaps():
    from app.professional_readiness import audit_resolve_post_pipeline_parity

    report = audit_resolve_post_pipeline_parity({
        "project_settings": {
            "color_management": {
                "input_space": "sRGB",
                "working_space": "Rec.709",
                "output_space": "Rec.709",
                "preview_transform_enabled": True,
            },
        },
        "mini_vfx_node_graphs": [{
            "nodes": [
                {"id": "media_in", "kind": "media_in"},
                {"id": "out", "kind": "output", "inputs": ["media_in"]},
            ],
            "output_node": "out",
        }],
    })

    cards = {card["id"]: card for card in report["professional_depth_cards"]}

    assert set(cards) == {
        "resolve_color_depth",
        "fairlight_audio_depth",
        "fusion_vfx_depth",
    }
    assert cards["resolve_color_depth"]["competitor"] == "DaVinci Resolve Color"
    assert cards["fairlight_audio_depth"]["competitor"] == "DaVinci Resolve Fairlight"
    assert cards["fusion_vfx_depth"]["competitor"] == "DaVinci Resolve Fusion"
    assert "RAW/HDR/ACES" in cards["resolve_color_depth"]["target"]
    assert "ADR" in cards["fairlight_audio_depth"]["target"]
    assert "2D/3D graph" in cards["fusion_vfx_depth"]["target"]
    assert len(cards["resolve_color_depth"]["phases"]) == 3
    assert len(cards["resolve_color_depth"]["daily_use_checks"]) == 4
    assert cards["resolve_color_depth"]["daily_use_blocking_count"] >= 1
    assert cards["fairlight_audio_depth"]["daily_use_checks"][0]["id"] == "mixer_routing_latency"
    assert cards["fusion_vfx_depth"]["daily_use_checks"][0]["id"] == "graph_cache"
    assert cards["resolve_color_depth"]["next_depth_action"]
    assert any(
        "Color corpus" in str(phase.get("qa_gate", ""))
        for phase in cards["resolve_color_depth"]["phases"]
    )
    assert report["professional_depth_actions"]
    assert cards["resolve_color_depth"]["why_not_100"]
    assert report["vfx_graph_qa"]["ok"] is True
    assert report["vfx_graph_qa"]["graph_count"] == 1
    vfx_features = {
        row["id"]: row["status"]
        for row in report["categories"]["vfx_fusion"]["features"]
    }
    assert vfx_features["node_2d_3d_compositing"] == "supported"


def test_resolve_post_pipeline_parity_is_advisory_and_tracks_feature_depth():
    from app.audio_workflow import loudness_target
    from app.professional_readiness import (
        audit_resolve_post_pipeline_parity,
        build_professional_readiness_report,
    )

    doc = {
        "project_settings": {
            "fps": 120.0,
            "preview_export_parity_lock": True,
            "color_management": {
                "input_space": "sRGB",
                "working_space": "ACEScg",
                "output_space": "Rec.2020",
                "output_transfer": "PQ",
                "preview_transform_enabled": True,
                "processing_bits": 32,
            },
            "audio": {"sample_rate": 48000, "channel_layout": "5.1"},
        },
        "product_capabilities": {
            "color": {
                "float_processing_bits": 32,
                "hdr_wheels": True,
                "zone_tone_controls": True,
                "st2084_tonemap": True,
                "log_wheels": True,
                "color_warper": True,
                "waveform": True,
                "parade": True,
                "vectorscope": True,
                "histogram": True,
                "gallery_stills": True,
                "shot_match": True,
                "split_screen": True,
                "lightbox": True,
            },
            "audio": {
                "max_tracks": 2000,
                "flexbus": True,
                "routing_matrix": True,
                "sample_accurate_editing": True,
                "sync_scroller": True,
                "vo_recording": True,
                "adr_cues": True,
                "elastic_wave": True,
                "track_layers": True,
                "foley_library": True,
                "surround_5_1": True,
                "voice_isolation": True,
                "vst_plugins": True,
            },
            "vfx": {
                "fusion_graph": True,
                "true_3d_workspace": True,
                "camera_3d": True,
                "lights_3d": True,
                "fbx_import": True,
                "alembic_import": True,
                "planar_tracker": True,
                "clean_plate": True,
                "b_spline_roto": True,
                "point_feathering": True,
                "vector_paint": True,
                "particles_3d": True,
                "spline_editor": True,
                "expressions": True,
                "macros": True,
                "fusion_node_count": 6,
            },
            "performance": {
                "gpu_fx": True,
                "preview_export_parity": True,
                "object_detection": True,
                "smart_reframe": True,
                "ten_bit_export": True,
                "fps_120": True,
                "above_4k_export": True,
                "render_cache": True,
                "optimized_media": True,
                "remote_render": True,
                "decklink": True,
                "openfx": True,
            },
            "post_pipeline": {
                "media_ingest": True,
                "camera_card_clone": True,
                "auto_av_sync": True,
                "smart_metadata": True,
                "multicam": True,
                "dual_timeline": True,
                "source_tape": True,
                "page_integration": True,
                "deliver_page": True,
                "multi_user": True,
                "timeline_locking": True,
                "shared_markers": True,
                "encoding_matrix": True,
            },
            "hardware": {
                "decklink": True,
                "external_monitoring": True,
                "micro_panel": True,
                "fairlight_console": True,
                "madi_interface": True,
            },
        },
        "video_tracks": [{
            "clips": [{
                "id": 1,
                "timeline_in_ms": 0,
                "source_in_ms": 0,
                "source_out_ms": 3000,
                "linked_audio_id": 10,
                "proxy_path": "clip_proxy.mp4",
                "camera_raw": {"enabled": True},
                "video_filters": {"enabled": True, "denoise": 0.2},
                "chroma_key": {"enabled": True},
                "bg_removal": {"enabled": True},
                "masks": [{"track_object": True}],
                "node_graph": {"color": {"grade": {"brightness": 4}}},
                "color_grade": {
                    "brightness": 8,
                    "hue_vs_hue": [[0, 0], [180, 190]],
                    "color_workflow": {
                        "enabled": True,
                        "qualifier": {
                            "enabled": True,
                            "softness": 0.2,
                            "clean_black": 0.1,
                            "clean_white": 0.1,
                        },
                        "window": {"enabled": True, "track_object": True},
                        "curves": {"master": [[0, 0], [255, 245]]},
                    },
                },
            }],
        }],
        "audio_tracks": [
            {
                "id": 1,
                "bus_id": "dialogue",
                "automation_points": [(0.0, 1.0)],
                "effects": {"eq": {"enabled": True}, "comp": {"enabled": True}, "loudness": {"enabled": True}},
                "clips": [{
                    "id": 10,
                    "offset_ms": 0,
                    "duration_ms": 3000,
                    "effects": {
                        "dialogue_cleanup": {"enabled": True},
                        "deesser": {"enabled": True},
                        "eq": {"enabled": True},
                        "comp": {"enabled": True},
                        "loudness": loudness_target("broadcast").to_effect_payload(),
                    },
                }],
            },
            {"id": 2, "bus_id": "music", "clips": []},
        ],
        "render_queue_jobs": [{"id": "a"}, {"id": "b"}],
        "media_bins": [{"name": "A roll"}],
        "markers": [{"time_ms": 1000}],
    }

    parity = audit_resolve_post_pipeline_parity(doc)
    full_report = build_professional_readiness_report(doc)

    assert parity["advisory"] is True
    assert full_report["sections"]["resolve_post_pipeline_parity"]["advisory"] is True
    assert full_report["issue_summary"]["high"] == 0

    color_features = {
        row["id"]: row["status"]
        for row in parity["categories"]["color"]["features"]
    }
    audio_features = {
        row["id"]: row["status"]
        for row in parity["categories"]["audio"]["features"]
    }
    vfx_features = {
        row["id"]: row["status"]
        for row in parity["categories"]["vfx_fusion"]["features"]
    }
    performance_features = {
        row["id"]: row["status"]
        for row in parity["categories"]["performance"]["features"]
    }

    assert color_features["float_yrgb_wide_gamut"] == "supported"
    assert color_features["hdr_grading_tonemap"] == "supported"
    assert color_features["resolve_color_management_aces"] == "supported"
    assert color_features["secondary_tracking"] == "supported"
    assert audio_features["daw_scale"] == "supported"
    assert audio_features["flexbus_routing"] == "supported"
    assert audio_features["loudness_delivery"] in {"partial", "supported"}
    assert vfx_features["node_2d_3d_compositing"] == "supported"
    assert vfx_features["tracking"] == "supported"
    assert performance_features["proxy_render_cache"] == "supported"
    assert parity["category_scores"]["post_pipeline"] == 100
    assert parity["category_scores"]["hardware_ecosystem"] == 100


def test_project_qa_professional_readiness_summary_aggregates_scores():
    from tools.qa_project_audit import _professional_readiness_summary

    rows = [
        {
            "professional_readiness": {
                "score": 90,
                "issue_summary": {"high": 0, "medium": 1},
                "sections": {
                    "resolve_post_pipeline_parity": {
                        "score": 40,
                        "category_scores": {"color": 50, "audio": 30},
                    },
                },
            }
        },
        {
            "professional_readiness": {
                "score": 60,
                "issue_summary": {"high": 2, "medium": 3},
                "sections": {
                    "resolve_post_pipeline_parity": {
                        "score": 20,
                        "category_scores": {"color": 20, "audio": 10},
                    },
                },
            }
        },
    ]

    summary = _professional_readiness_summary(rows)

    assert summary["count"] == 2
    assert summary["avg_score"] == 75.0
    assert summary["min_score"] == 60.0
    assert summary["high_issues"] == 2
    assert summary["medium_issues"] == 4
    assert summary["resolve_parity"]["avg_score"] == 30.0
    assert summary["resolve_parity"]["min_score"] == 20.0
    assert summary["resolve_parity"]["category_min_scores"] == {"audio": 10.0, "color": 20.0}


def test_media_health_formats_professional_readiness_for_ui():
    from app.media_health_dialog import (
        professional_readiness_detail_lines,
        professional_readiness_summary_text,
        timeline_edge_cleanup_actionable_count,
        timeline_edge_cleanup_button_text,
        timeline_edge_cleanup_detail_lines,
        timeline_edge_cleanup_locked_auto_count,
        timeline_edge_cleanup_summary_text,
    )

    report = {
        "timeline_edge_cleanup": {
            "frame_ms": 17,
            "issue_count": 3,
            "auto_fixable_count": 2,
            "tracks": [{
                "track_id": 2,
                "locked": 0,
                "micro_gap_count": 1,
                "micro_overlap_count": 1,
                "gap_count": 1,
                "overlap_count": 0,
                "issues": [
                    {
                        "kind": "micro_gap",
                        "left_clip_id": 10,
                        "right_clip_id": 11,
                        "start_ms": 1000,
                        "end_ms": 1016,
                        "duration_ms": 16,
                        "auto_fixable": 1,
                    },
                    {
                        "kind": "gap",
                        "left_clip_id": 11,
                        "right_clip_id": 12,
                        "start_ms": 2000,
                        "end_ms": 2400,
                        "duration_ms": 400,
                        "auto_fixable": 0,
                    },
                ],
            }],
        },
        "professional_readiness": {
            "score": 72,
            "issue_summary": {"high": 1, "medium": 2, "low": 3},
            "sections": {
                "long_project_stability": {"score": 80},
                "gpu_preview_export_consistency": {"score": 65},
                "timeline_edit_integrity": {"score": 90},
                "color_workflow_depth": {
                    "score": 70,
                    "scope_accuracy": {
                        "ok": True,
                        "luma_span": 0.92,
                        "saturation_mean": 0.58,
                        "warnings": [],
                    },
                },
                "audio_mix_readiness": {"score": 55},
                "resolve_post_pipeline_parity": {
                    "advisory": True,
                    "score": 22,
                    "categories": {
                        "color": {"label": "Color / 색보정", "score": 30, "supported": 1, "partial": 2, "missing": 9},
                        "audio": {"label": "Audio / Fairlight", "score": 20, "supported": 0, "partial": 4, "missing": 6},
                    },
                    "professional_depth_cards": [{
                        "id": "resolve_color_depth",
                        "competitor": "DaVinci Resolve Color",
                        "score": 30,
                        "current_level": "foundation / gap-tracking workflow",
                        "why_not_100": ["Camera RAW non-destructive controls"],
                        "next_actions": ["Add RAW sidecar controls."],
                        "phases": [{"qa_gate": "Color corpus compares preview/export pixels."}],
                    }],
                    "vfx_graph_qa": {
                        "ok": False,
                        "graph_count": 1,
                        "node_count": 2,
                        "warnings": ["graph 1: output node missing: out"],
                    },
                    "implementation_backlog": [{
                        "category_label": "Color / 색보정",
                        "label": "HDR wheels, zone tone controls, ST.2084/HLG tone mapping",
                        "status": "missing",
                        "action": "Implement HDR wheels/zone controls and ST.2084/HLG preview/export parity samples.",
                    }],
                    "supported_highlights": [{
                        "category_label": "Color / 색보정",
                        "label": "Resolve Color Management, ACES, OCIO",
                    }],
                },
            },
            "top_actions": [
                "Run project QA baseline before final export.",
                "Assign dialogue and music buses.",
            ],
        }
    }

    summary = professional_readiness_summary_text(report)
    details = "\n".join(professional_readiness_detail_lines(report))
    edge_summary = timeline_edge_cleanup_summary_text(report)
    edge_details = "\n".join(timeline_edge_cleanup_detail_lines(report))

    assert "readiness 72" in summary
    assert "H1 M2" in summary
    assert "Professional readiness" in details
    assert "gpu preview export consistency: 65" in details
    assert "Color scope QA: OK" in details
    assert "resolve post pipeline parity: 22 advisory" in details
    assert "Resolve / Fairlight / Fusion parity" in details
    assert "DaVinci Resolve Color: 30" in details
    assert "Add RAW sidecar controls" in details
    assert "VFX graph QA: Review" in details
    assert "output node missing" in details
    assert "Color / 색보정: 30" in details
    assert "Implement HDR wheels/zone controls" in details
    assert "Assign dialogue and music buses" in details
    assert edge_summary == "timeline edges 2 auto-fixable/3"
    assert timeline_edge_cleanup_actionable_count(report) == 2
    assert timeline_edge_cleanup_locked_auto_count(report) == 0
    assert timeline_edge_cleanup_button_text(report) == "Clean 2 Timeline Edges"
    assert "Timeline micro-edge cleanup" in edge_details
    assert "Action: Clean 2 Timeline Edges" in edge_details
    assert "Track 2" in edge_details
    assert "micro overlaps 1" in edge_details
    assert "micro gap 16 ms (auto) clips 10->11 at 1000-1016 ms" in edge_details
    assert "gap 400 ms (manual) clips 11->12 at 2000-2400 ms" in edge_details

    report["timeline_edge_cleanup"]["tracks"][0]["locked"] = 1
    assert timeline_edge_cleanup_actionable_count(report) == 0
    assert timeline_edge_cleanup_locked_auto_count(report) == 2
    assert timeline_edge_cleanup_button_text(report) == "Clean Timeline Edges"


def test_professional_readiness_export_diagnostics_format():
    from app.professional_readiness import format_professional_readiness_diagnostics

    text = format_professional_readiness_diagnostics({
        "ok": False,
        "score": 68,
        "issue_summary": {"high": 1, "medium": 2, "low": 0},
        "sections": {
            "long_project_stability": {"score": 70},
            "gpu_preview_export_consistency": {"score": 55},
            "timeline_edit_integrity": {"score": 90},
            "color_workflow_depth": {
                "score": 65,
                "scope_accuracy": {
                    "ok": True,
                    "luma_span": 0.92,
                    "saturation_mean": 0.58,
                },
            },
            "audio_mix_readiness": {"score": 60},
            "resolve_post_pipeline_parity": {
                "score": 25,
                "advisory": True,
                "vfx_graph_qa": {
                    "ok": False,
                    "graph_count": 1,
                    "node_count": 2,
                    "warnings": ["graph 1: output node missing: out"],
                },
                "categories": {
                    "vfx_fusion": {
                        "features": [{
                            "id": "node_2d_3d_compositing",
                            "status": "partial",
                            "evidence": "node_graph_clips=0, vfx_graphs=1, fusion_nodes=1",
                        }],
                    },
                },
            },
        },
        "top_actions": [
            "Run project QA baseline before final export.",
            "Apply a loudness target before export.",
        ],
    })

    assert "Professional Readiness: Review score=68 high=1 medium=2 low=0" in text
    assert "gpu_preview_export_consistency=55" in text
    assert "resolve_post_pipeline_parity=25 advisory" in text
    assert "Color Scope QA: OK" in text
    assert "VFX Graph QA: Review graphs=1 nodes=2 warnings=1" in text
    assert "Run project QA baseline before final export" in text


def test_qa_dashboard_summarizes_project_readiness_and_resolve_parity():
    from app.qa_dashboard import _summary_for

    ok, summary, lines = _summary_for("project_qa", {
        "ok": True,
        "project_count": 2,
        "professional_readiness_summary": {
            "avg_score": 75.0,
            "resolve_parity": {
                "avg_score": 30.0,
                "min_score": 20.0,
                "category_min_scores": {"audio": 10.0, "color": 20.0},
            },
        },
        "projects": [{
            "project": "E:/qa/a.tgp",
            "professional_readiness": {
                "score": 80,
                "sections": {
                    "resolve_post_pipeline_parity": {
                        "score": 35,
                        "category_scores": {"color": 50, "audio": 20},
                        "top_actions": ["Finish Color Page advanced controls."],
                        "professional_depth_cards": [{
                            "id": "fairlight_audio_depth",
                            "competitor": "DaVinci Resolve Fairlight",
                            "score": 20,
                            "current_level": "foundation / gap-tracking workflow",
                        }],
                        "vfx_graph_qa": {"ok": True, "graph_count": 1, "node_count": 4, "warnings": []},
                    },
                },
            },
        }],
    })

    assert ok is True
    assert "readiness avg 75.0" in summary
    assert "resolve parity avg 30.0" in summary
    assert any("a.tgp" in line and "resolve-parity=35" in line for line in lines)
    assert any("DaVinci Resolve Fairlight" in line for line in lines)
    assert any("vfx-graph: OK graphs=1 nodes=4 warnings=0" in line for line in lines)
    assert any("Resolve category mins" in line for line in lines)
    assert any("Finish Color Page advanced controls" in line for line in lines)


def test_professional_readiness_surfaces_actor_corpus_status():
    from app.professional_readiness import build_professional_readiness_report

    doc = {
        "spine_actor_tracks": [{"clips": [{"start_ms": 0, "duration_ms": 1000}]}],
        "actor_corpus_status": {
            "ok": False,
            "coverage": {
                "total": 20,
                "render_failure_categories": {"animation_sweep_blank": 1},
            },
            "issues": [{"code": "render_failures", "severity": "high"}],
        },
    }

    report = build_professional_readiness_report(doc)
    gpu = report["sections"]["gpu_preview_export_consistency"]

    assert report["ok"] is False
    assert gpu["actor_corpus_status"]["ok"] is False
    assert any(
        issue["message"] == "Live2D/Spine corpus QA status is not passing."
        for issue in gpu["issues"]
    )
