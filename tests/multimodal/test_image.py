from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from embedded_copilot.multimodal.image import ImageAnalyzer
from embedded_copilot.multimodal.models import MultimodalProcessingError


@pytest.mark.parametrize(
    ("suffix", "expected_format"),
    [(".png", "PNG"), (".jpg", "JPEG"), (".webp", "WEBP")],
)
def test_image_analyzer_reads_offline_metadata(
    tmp_path: Path,
    suffix: str,
    expected_format: str,
) -> None:
    path = tmp_path / f"diagram{suffix}"
    Image.new("RGB", (16, 9), color="navy").save(path)

    metadata = ImageAnalyzer.analyze(path)

    assert metadata == {
        "width": 16,
        "height": 9,
        "format": expected_format,
        "path": str(path),
        "analysis_mode": "offline_metadata",
    }


@pytest.mark.parametrize("kind", ["missing", "directory", "corrupt"])
def test_image_analyzer_maps_invalid_inputs_to_multimodal_error(
    tmp_path: Path,
    kind: str,
) -> None:
    path = tmp_path / "input.png"
    if kind == "directory":
        path.mkdir()
    elif kind == "corrupt":
        path.write_bytes(b"not an image")

    with pytest.raises(MultimodalProcessingError):
        ImageAnalyzer.analyze(path)


def test_image_analyzer_rejects_unsupported_actual_format(tmp_path: Path) -> None:
    path = tmp_path / "disguised.png"
    Image.new("RGB", (8, 6), color="black").save(path, format="BMP")

    with pytest.raises(MultimodalProcessingError):
        ImageAnalyzer.analyze(path)


@pytest.mark.parametrize(
    "library_error",
    [SyntaxError("broken image structure"), Image.DecompressionBombError("too large")],
)
def test_image_analyzer_maps_pillow_validation_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    library_error: Exception,
) -> None:
    path = tmp_path / "input.png"
    path.write_bytes(b"image placeholder")

    def raise_library_error(*args: object, **kwargs: object) -> None:
        raise library_error

    monkeypatch.setattr(Image, "open", raise_library_error)

    with pytest.raises(MultimodalProcessingError):
        ImageAnalyzer.analyze(path)
