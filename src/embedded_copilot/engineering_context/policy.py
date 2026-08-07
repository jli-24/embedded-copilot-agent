from __future__ import annotations

from enum import StrEnum


class ContextCategory(StrEnum):
    REQUIREMENT = "REQUIREMENT"
    DECISION = "DECISION"
    CONSTRAINT = "CONSTRAINT"
    HISTORICAL_PROBLEM = "HISTORICAL_PROBLEM"
    SOLUTION = "SOLUTION"
    COMPONENT = "COMPONENT"
    INTERFACE = "INTERFACE"


class ContextVerificationStatus(StrEnum):
    APPROVED = "APPROVED"
    VERIFIED = "VERIFIED"
    PROJECTED = "PROJECTED"
    SOURCE_METADATA = "SOURCE_METADATA"


class ContextSourceType(StrEnum):
    ENGINEERING_MEMORY = "ENGINEERING_MEMORY"
    KNOWLEDGE_GRAPH = "KNOWLEDGE_GRAPH"
    KNOWLEDGE_EVOLUTION = "KNOWLEDGE_EVOLUTION"
    DATASHEET_METADATA = "DATASHEET_METADATA"


class ContextPolicy:
    """Immutable policy functions for evidence-backed context projection."""

    allow_memory_types = (
        "REQUIREMENT",
        "DECISION",
        "ARCHITECTURE",
        "INTERFACE",
        "DEBUG_EXPERIENCE",
        "OPTIMIZATION",
    )
    allow_graph_types = (
        "REQUIREMENT",
        "DECISION",
        "CONSTRAINT",
        "PROBLEM",
        "SOLUTION",
        "COMPONENT",
        "INTERFACE",
    )

    @staticmethod
    def category_for_memory_type(value: str) -> ContextCategory | None:
        mapping = (
            ("REQUIREMENT", ContextCategory.REQUIREMENT),
            ("DECISION", ContextCategory.DECISION),
            ("ARCHITECTURE", ContextCategory.CONSTRAINT),
            ("INTERFACE", ContextCategory.INTERFACE),
            ("DEBUG_EXPERIENCE", ContextCategory.HISTORICAL_PROBLEM),
            ("OPTIMIZATION", ContextCategory.SOLUTION),
        )
        if value not in ContextPolicy.allow_memory_types:
            return None
        return next((category for name, category in mapping if name == value), None)

    @staticmethod
    def category_for_graph_type(value: str) -> ContextCategory | None:
        mapping = (
            ("REQUIREMENT", ContextCategory.REQUIREMENT),
            ("DECISION", ContextCategory.DECISION),
            ("CONSTRAINT", ContextCategory.CONSTRAINT),
            ("PROBLEM", ContextCategory.HISTORICAL_PROBLEM),
            ("SOLUTION", ContextCategory.SOLUTION),
            ("COMPONENT", ContextCategory.COMPONENT),
            ("INTERFACE", ContextCategory.INTERFACE),
        )
        if value not in ContextPolicy.allow_graph_types:
            return None
        return next((category for name, category in mapping if name == value), None)

    @staticmethod
    def status_is_usable(value: str) -> bool:
        return value in {
            ContextVerificationStatus.APPROVED.value,
            ContextVerificationStatus.VERIFIED.value,
            ContextVerificationStatus.PROJECTED.value,
            ContextVerificationStatus.SOURCE_METADATA.value,
        }


__all__ = (
    "ContextCategory",
    "ContextPolicy",
    "ContextSourceType",
    "ContextVerificationStatus",
)
