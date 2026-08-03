from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from typing import Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_FP = re.compile(r"^sha256:[a-f0-9]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")


class WebResearchContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


def _safe(value: object, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    text = unicodedata.normalize("NFC", value).strip()
    if not text or len(text) > maximum or any(c in text for c in ("\x00", "\r", "\n")):
        raise ValueError(f"{field} is invalid")
    return text


def _id(value: object, field: str) -> str:
    text = _safe(value, field, 160)
    if not _ID.fullmatch(text):
        raise ValueError(f"{field} is invalid")
    return text


class WebResearchRequest(WebResearchContract):
    query: str

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, value: object) -> str:
        return _safe(value, "query")


class WebEvidenceProjection(WebResearchContract):
    source: str
    summary: str
    reference: str
    confidence: float
    fingerprint: str

    @field_validator("source", "reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return _id(value, info.field_name)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _safe(value, "summary")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        if type(value) is not float or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("confidence is invalid")
        return value

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        if not isinstance(value, str) or not _FP.fullmatch(value):
            raise ValueError("fingerprint is invalid")
        return value

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "WebEvidenceProjection":
        payload = self.model_dump(mode="json", exclude={"fingerprint"})
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
        if expected != self.fingerprint:
            raise ValueError("web evidence fingerprint mismatch")
        return self


class WebResearchUnavailable(RuntimeError):
    pass


class WebResearchPort(Protocol):
    async def research(
        self, request: WebResearchRequest
    ) -> tuple[WebEvidenceProjection, ...]: ...


class UnavailableWebResearchPort:
    async def research(
        self, request: WebResearchRequest
    ) -> tuple[WebEvidenceProjection, ...]:
        raise WebResearchUnavailable("web research is not configured")


__all__ = [
    "UnavailableWebResearchPort",
    "WebEvidenceProjection",
    "WebResearchPort",
    "WebResearchRequest",
    "WebResearchUnavailable",
]
