from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from embedded_copilot.knowledge.models import DocumentMetadata


class MetadataError(RuntimeError):
    """Raised when a document metadata sidecar cannot be loaded safely."""


def metadata_sidecar_path(document_path: str | Path) -> Path:
    path = Path(document_path)
    return path.with_name(f"{path.name}.metadata.json")


def load_document_metadata(document_path: str | Path) -> DocumentMetadata:
    sidecar = metadata_sidecar_path(document_path)
    if not sidecar.exists():
        return DocumentMetadata()
    if not sidecar.is_file():
        raise MetadataError(f"Metadata sidecar is not a file: {sidecar.name}")
    try:
        payload = sidecar.read_text(encoding="utf-8")
        return DocumentMetadata.model_validate_json(payload)
    except (OSError, UnicodeError, ValidationError) as exc:
        raise MetadataError(f"Failed to load metadata sidecar: {sidecar.name}") from exc
