from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import fitz


class DocumentLoadError(RuntimeError):
    """Raised when a knowledge document cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    text: str
    source: str
    filename: str
    page: int | None
    checksum: str


def _source_name(path: Path, source_root: Path | None) -> str:
    resolved = path.resolve()
    if source_root is None:
        return path.name
    try:
        return resolved.relative_to(source_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_markdown(path: Path, source: str, checksum: str) -> list[LoadedDocument]:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise DocumentLoadError(f"Failed to read Markdown document: {path.name}") from exc
    if not text:
        raise DocumentLoadError(f"Document contains no readable text: {path.name}")
    return [
        LoadedDocument(
            text=text,
            source=source,
            filename=path.name,
            page=None,
            checksum=checksum,
        )
    ]


def _load_pdf(path: Path, source: str, checksum: str) -> list[LoadedDocument]:
    try:
        with fitz.open(path) as pdf:
            documents = [
                LoadedDocument(
                    text=page.get_text("text").strip(),
                    source=source,
                    filename=path.name,
                    page=page_number,
                    checksum=checksum,
                )
                for page_number, page in enumerate(pdf, start=1)
            ]
    except (OSError, RuntimeError, ValueError) as exc:
        raise DocumentLoadError(f"Failed to parse PDF document: {path.name}") from exc
    if not documents or not any(document.text for document in documents):
        raise DocumentLoadError(f"Document contains no readable text: {path.name}")
    return documents


def load_document(
    path: str | Path,
    *,
    source_root: str | Path | None = None,
) -> list[LoadedDocument]:
    document_path = Path(path)
    if not document_path.is_file():
        raise DocumentLoadError(f"Document does not exist: {document_path}")

    root = Path(source_root) if source_root is not None else None
    source = _source_name(document_path, root)
    checksum = _checksum(document_path)
    suffix = document_path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(document_path, source, checksum)
    if suffix in {".md", ".markdown"}:
        return _load_markdown(document_path, source, checksum)
    raise DocumentLoadError(f"Unsupported document type: {suffix or '<none>'}")
