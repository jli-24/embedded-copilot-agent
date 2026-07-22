from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict

from PIL import Image

from embedded_copilot.multimodal.models import MultimodalProcessingError


class ImageMetadata(TypedDict):
    width: int
    height: int
    format: str
    path: str
    analysis_mode: Literal["offline_metadata"]


class ImageAnalyzer:
    _SUPPORTED_FORMATS = {"PNG", "JPEG", "WEBP"}

    @staticmethod
    def analyze(file_path: str | Path) -> ImageMetadata:
        path = Path(file_path)
        if not path.is_file():
            raise MultimodalProcessingError(
                f"Image file does not exist or is not a file: {path.name}"
            )

        try:
            with Image.open(path) as image:
                width, height = image.size
                image_format = image.format
                image.verify()
        except (
            OSError,
            SyntaxError,
            ValueError,
            Image.DecompressionBombError,
        ) as exc:
            raise MultimodalProcessingError(
                f"Failed to parse image file: {path.name}"
            ) from exc

        if image_format not in ImageAnalyzer._SUPPORTED_FORMATS:
            raise MultimodalProcessingError(
                f"Unsupported image format: {path.name}"
            )
        return {
            "width": width,
            "height": height,
            "format": image_format,
            "path": str(path),
            "analysis_mode": "offline_metadata",
        }
