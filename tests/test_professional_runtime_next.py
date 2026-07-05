def test_professional_runtime_depth_samples_cover_color_audio_vfx():
    from app.post_pipeline_workflow import professional_post_pipeline_report
    from app.professional_runtime import (
        run_fairlight_latency_runtime_sample,
        run_professional_color_precision_sample,
        run_vfx_expression_macro_runtime_sample,
    )

    color = run_professional_color_precision_sample()
    post = professional_post_pipeline_report()
    vfx = run_vfx_expression_macro_runtime_sample(post["vfx_graph"])
    audio = run_fairlight_latency_runtime_sample()

    assert color["ok"] is True
    assert color["checks"]["thirty_two_bit_or_better"] is True
    assert color["checks"]["scope_accuracy_ok"] is True
    assert post["checks"]["has_expression_modifier_macro"] is True
    assert post["checks"]["has_deep_volumetric_nodes"] is True
    assert post["summary"]["expression_modifier_nodes"] >= 4
    assert vfx["ok"] is True
    assert vfx["checks"]["deep_volumetric_branch"] is True
    assert audio["ok"] is True
    assert audio["checks"]["large_track_contract"] is True
    assert audio["summary"]["stress_tracks"] >= 2000
