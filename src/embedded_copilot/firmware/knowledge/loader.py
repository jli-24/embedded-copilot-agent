from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import Field, ValidationError, field_validator

from embedded_copilot.firmware.exceptions import FirmwareKnowledgeError
from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.schemas.result import ContractModel


class _FirmwareDocumentSidecar(ContractModel):
    title: str | None = Field(default=None, min_length=1)
    platform: str | None = Field(default=None, min_length=1)
    framework: str | None = Field(default=None, min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("title", "platform", "framework", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def _infer_title(path: Path, content: str) -> str:
    if path.suffix.lower() in {".md", ".markdown"}:
        for line in content.splitlines():
            match = re.match(r"^\s*#+\s+(.+?)\s*$", line)
            if match is not None:
                return match.group(1)
    return path.stem


def _infer_platform(text: str) -> str | None:
    if re.search(r"esp32", text, re.IGNORECASE):
        return "ESP32"
    if re.search(r"stm32", text, re.IGNORECASE):
        return "STM32"
    return None


def _infer_framework(text: str) -> str | None:
    if re.search(r"esp[-_ ]?idf", text, re.IGNORECASE):
        return "ESP-IDF"
    if re.search(r"freertos", text, re.IGNORECASE):
        return "FreeRTOS"
    if re.search(r"(?<![A-Za-z0-9])hal(?![A-Za-z0-9])", text, re.IGNORECASE):
        return "HAL"
    return None


def _load_sidecar(path: Path) -> _FirmwareDocumentSidecar:
    sidecar_path = path.with_name(f"{path.name}.metadata.json")
    if not sidecar_path.exists():
        return _FirmwareDocumentSidecar()
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        return _FirmwareDocumentSidecar.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise FirmwareKnowledgeError(
            f"invalid firmware document sidecar: {sidecar_path.name}"
        ) from exc


class FirmwareDocumentLoader:
    _SUFFIXES = {".md", ".markdown", ".txt"}

    def load(self, path: str | Path) -> list[FirmwareDocument]:
        input_path = Path(path)
        if input_path.is_file():
            root = input_path.parent
            candidates = [input_path] if input_path.suffix.lower() in self._SUFFIXES else []
        elif input_path.is_dir():
            root = input_path
            candidates = sorted(
                candidate
                for candidate in input_path.rglob("*")
                if candidate.is_file() and candidate.suffix.lower() in self._SUFFIXES
            )
        else:
            raise FirmwareKnowledgeError(f"firmware knowledge path does not exist: {input_path.name}")

        documents: list[FirmwareDocument] = []
        for candidate in candidates:
            try:
                content = candidate.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError) as exc:
                raise FirmwareKnowledgeError(
                    f"failed to read firmware document: {candidate.name}"
                ) from exc
            if not content:
                raise FirmwareKnowledgeError(
                    f"firmware document is empty: {candidate.name}"
                )

            source = candidate.relative_to(root).as_posix()
            sidecar = _load_sidecar(candidate)
            inference_text = f"{source}\n{content}"
            platform = sidecar.platform or _infer_platform(inference_text)
            framework = sidecar.framework or _infer_framework(inference_text)
            if platform is None or framework is None:
                raise FirmwareKnowledgeError(
                    f"firmware document metadata is incomplete: {candidate.name}"
                )
            metadata = {
                **sidecar.metadata,
                "source": source,
                "file_type": candidate.suffix.lower().lstrip("."),
            }
            document_id = hashlib.sha256(
                f"{source}\0{content}".encode("utf-8")
            ).hexdigest()
            try:
                document = FirmwareDocument(
                    id=document_id,
                    title=sidecar.title or _infer_title(candidate, content),
                    platform=platform,
                    framework=framework,
                    content=content,
                    metadata=metadata,
                )
            except ValidationError as exc:
                raise FirmwareKnowledgeError(
                    f"invalid firmware document: {candidate.name}"
                ) from exc
            documents.append(document)
        return documents
