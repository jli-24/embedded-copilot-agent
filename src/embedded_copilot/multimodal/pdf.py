from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import fitz

from embedded_copilot.multimodal.models import MultimodalProcessingError


class PDFPage(TypedDict):
    page: int
    content: str


class PDFAnalyzer:
    @staticmethod
    def analyze(file_path: str | Path) -> list[PDFPage]:
        path = Path(file_path)
        if not path.is_file():
            raise MultimodalProcessingError(
                f"PDF file does not exist or is not a file: {path.name}"
            )

        try:
            with fitz.open(path) as pdf:
                return [
                    {
                        "page": page_number,
                        "content": page.get_text("text").strip(),
                    }
                    for page_number, page in enumerate(pdf, start=1)
                ]
        except (OSError, RuntimeError, ValueError) as exc:
            raise MultimodalProcessingError(
                f"Failed to parse PDF file: {path.name}"
            ) from exc
