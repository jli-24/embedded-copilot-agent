from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from embedded_copilot.schemas.result import ContractModel


class _GitHubRawItem(ContractModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    reference_url: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    category: str = Field(min_length=1)
    domain: Literal["firmware", "hardware", "pcb", "debug"]

    @field_validator(
        "id",
        "title",
        "repository",
        "owner",
        "summary",
        "reference_url",
        "category",
        "domain",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class GitHubRepositoryItem(_GitHubRawItem):
    language: str | None = Field(default=None, min_length=1)
    stars: int = Field(default=0, ge=0)

    @field_validator("language", mode="before")
    @classmethod
    def strip_language(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class GitHubCodeItem(_GitHubRawItem):
    path: str = Field(min_length=1)
    language: str | None = Field(default=None, min_length=1)

    @field_validator("path", "language", mode="before")
    @classmethod
    def strip_code_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class GitHubIssueItem(_GitHubRawItem):
    pass


class GitHubReleaseItem(_GitHubRawItem):
    tag: str = Field(min_length=1)

    @field_validator("tag", mode="before")
    @classmethod
    def strip_tag(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
