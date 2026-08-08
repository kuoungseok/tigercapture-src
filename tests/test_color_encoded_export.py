from __future__ import annotations

from tools.qa_color_encoded_export import run_encoded_color_qa


def test_real_h265_pq_color_chart_round_trip(tmp_path) -> None:
    report = run_encoded_color_qa(tmp_path)
    assert report["ok"]
    assert report["preview_engine"] == "ocio"
    assert report["metadata"]["ok"]
    assert report["metadata"]["comparison"]["actual"] == {
        "colorspace": "bt2020nc",
        "color_primaries": "bt2020",
        "color_trc": "smpte2084",
    }
    assert report["mean_abs_patch_byte_delta"] <= 3.0
    assert report["max_abs_patch_byte_delta"] <= 18.0
    assert report["mean_patch_delta_e76"] <= 1.5
    assert report["max_patch_delta_e76"] <= 2.5
