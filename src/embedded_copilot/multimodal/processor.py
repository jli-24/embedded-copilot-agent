from __future__ import annotations

import logging
from pathlib import Path

from embedded_copilot.multimodal.image import ImageAnalyzer
from embedded_copilot.multimodal.models import (
    FileDocument,
    FileType,
    MultimodalProcessingError,
)
from embedded_copilot.multimodal.pdf import PDFAnalyzer
from embedded_copilot.multimodal.router import FileRouter


logger = logging.getLogger("embedded_copilot.multimodal")


class MultimodalProcessor:
    @classmethod
    def process(
        cls,
        file_path: str | Path,
        *,
        trace_id: str | None = None,
    ) -> FileDocument:
        path = Path(file_path)
        if not path.is_file():
            raise MultimodalProcessingError(
                f"Input file does not exist or is not a file: {path.name}"
            )

        file_type = FileRouter.route(path)
        logger.info(
            "multimodal_processing_started",
            extra={
                "event_name": "multimodal_processing_started",
                "trace_id": trace_id,
                "file_type": file_type.value,
            },
        )
        metadata: dict[str, object]
        if file_type is FileType.PDF:
            pages = PDFAnalyzer.analyze(path)
            metadata = {"page_count": len(pages), "pages": pages}
        elif file_type is FileType.IMAGE:
            metadata = dict(ImageAnalyzer.analyze(path))
        elif file_type in {FileType.CODE, FileType.TEXT}:
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise MultimodalProcessingError(
                    f"Failed to read text file: {path.name}"
                ) from exc
            metadata = {"content": content, "encoding": "utf-8"}
        else:
            metadata = {}

        document = FileDocument(
            filename=path.name,
            file_type=file_type,
            path=str(path),
            metadata=metadata,
        )
        logger.info(
            "multimodal_processing_completed",
            extra={
                "event_name": "multimodal_processing_completed",
                "trace_id": trace_id,
                "file_type": file_type.value,
                "outcome": "success",
            },
        )
        return document
