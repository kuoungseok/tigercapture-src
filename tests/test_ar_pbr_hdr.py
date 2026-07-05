from pathlib import Path

import pytest

from app.ar_pbr.hdr import image_stats, load_radiance_hdr


HDRI = Path("resources/ar_pbr/hdri/wide_street_01_1k.hdr")


@pytest.mark.skipif(not HDRI.exists(), reason="local HDRI resource not present")
def test_radiance_hdr_loader_reads_polyhaven_resource():
    image = load_radiance_hdr(HDRI)
    stats = image_stats(image)

    assert image.width == 1024
    assert image.height == 512
    assert image.pixels.shape == (512, 1024, 3)
    assert image.pixels.dtype.name == "float32"
    assert stats["max_luminance"] > stats["mean_luminance"] > 0.0
