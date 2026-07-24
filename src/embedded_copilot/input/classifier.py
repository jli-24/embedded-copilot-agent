from __future__ import annotations

from pathlib import PurePath

from embedded_copilot.input.exceptions import InputValidationError
from embedded_copilot.input.models import AttachmentType


_DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_EXTENSIONS: dict[str, tuple[AttachmentType, str, frozenset[str]]] = {
    ".png": (AttachmentType.IMAGE, "image/png", frozenset({"image/png"})),
    ".jpg": (AttachmentType.IMAGE, "image/jpeg", frozenset({"image/jpeg"})),
    ".jpeg": (AttachmentType.IMAGE, "image/jpeg", frozenset({"image/jpeg"})),
    ".c": (
        AttachmentType.SOURCE_CODE,
        "text/x-c",
        frozenset({"text/x-c", "text/plain"}),
    ),
    ".cpp": (
        AttachmentType.SOURCE_CODE,
        "text/x-c++",
        frozenset({"text/x-c++", "text/plain"}),
    ),
    ".h": (
        AttachmentType.SOURCE_CODE,
        "text/x-c",
        frozenset({"text/x-c", "text/plain"}),
    ),
    ".hpp": (
        AttachmentType.SOURCE_CODE,
        "text/x-c++",
        frozenset({"text/x-c++", "text/plain"}),
    ),
    ".py": (
        AttachmentType.SOURCE_CODE,
        "text/x-python",
        frozenset({"text/x-python", "text/plain"}),
    ),
    ".log": (AttachmentType.LOG, "text/plain", frozenset({"text/plain"})),
    ".txt": (AttachmentType.LOG, "text/plain", frozenset({"text/plain"})),
    ".kicad_pcb": (
        AttachmentType.EDA,
        "application/x-kicad-pcb",
        frozenset({"application/x-kicad-pcb", "text/plain"}),
    ),
    ".kicad_sch": (
        AttachmentType.EDA,
        "application/x-kicad-schematic",
        frozenset({"application/x-kicad-schematic", "text/plain"}),
    ),
    ".brd": (
        AttachmentType.EDA,
        "application/x-eda-board",
        frozenset({"application/x-eda-board", "text/plain"}),
    ),
    ".pdf": (
        AttachmentType.DOCUMENT,
        "application/pdf",
        frozenset({"application/pdf"}),
    ),
    ".docx": (
        AttachmentType.DOCUMENT,
        _DOCX_CONTENT_TYPE,
        frozenset({_DOCX_CONTENT_TYPE}),
    ),
    ".md": (
        AttachmentType.DOCUMENT,
        "text/markdown",
        frozenset({"text/markdown", "text/plain"}),
    ),
}


def _contract(filename: str) -> tuple[AttachmentType, str, frozenset[str]]:
    if (
        not isinstance(filename, str)
        or not filename.strip()
        or "/" in filename
        or "\\" in filename
    ):
        raise InputValidationError("attachment type is invalid")
    suffix = PurePath(filename.strip()).suffix.casefold()
    try:
        return _EXTENSIONS[suffix]
    except KeyError:
        raise InputValidationError("attachment type is invalid") from None


class AttachmentClassifier:
    @classmethod
    def classify(
        cls,
        filename: str,
        content_type: str | None = None,
    ) -> AttachmentType:
        attachment_type, _, allowed_content_types = _contract(filename)
        if content_type is not None:
            if not isinstance(content_type, str):
                raise InputValidationError("attachment type is invalid")
            normalized = content_type.split(";", maxsplit=1)[0].strip().casefold()
            if normalized not in allowed_content_types:
                raise InputValidationError("attachment type is invalid")
        return attachment_type

    @staticmethod
    def canonical_content_type(filename: str) -> str:
        return _contract(filename)[1]
