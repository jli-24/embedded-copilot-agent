from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_memory.context import (
    MemoryContextEvidence,
    MemoryDomain,
    MemoryRankingBreakdown,
    MemoryTrustBasis,
)
from embedded_copilot.engineering_memory.domain import map_memory_domains
from embedded_copilot.engineering_memory.models import (
    MemorySourceType,
    MemoryType,
)
from embedded_copilot.engineering_memory.read_projection import (
    VerifiedMemoryReadProjection,
)
from embedded_copilot.verification_agent import VerificationSubjectType

OBSERVED_AT = datetime(2026, 7, 30, 3, 0, tzinfo=UTC)


def _projection(
    memory_type: MemoryType,
    *,
    subject: VerificationSubjectType | None = VerificationSubjectType.HARDWARE,
    logical_key: str = "memory-record",
) -> VerifiedMemoryReadProjection:
    trust_basis = (
        MemoryTrustBasis.VERIFICATION
        if subject is not None
        else MemoryTrustBasis.HUMAN_APPROVAL
    )
    return VerifiedMemoryReadProjection(
        record_id="record-1",
        logical_key=logical_key,
        memory_type=memory_type,
        trust_basis=trust_basis,
        verification_subject=subject,
        confidence=1.0 if subject is not None else 0.5,
        last_transition_at=OBSERVED_AT,
    )


def _evidence(
    memory_type: MemoryType,
    *,
    provenance: MemorySourceType,
    subject: VerificationSubjectType | None = None,
    provenance_reference: str = "source-1",
) -> MemoryContextEvidence:
    trust_basis = (
        MemoryTrustBasis.VERIFICATION
        if subject is not None
        else MemoryTrustBasis.HUMAN_APPROVAL
    )
    return MemoryContextEvidence(
        record_id="record-1",
        memory_type=memory_type,
        logical_key="memory-record",
        trust_basis=trust_basis,
        verification_subject=subject,
        verification_confidence=1.0 if subject is not None else None,
        provenance_source_type=provenance,
        provenance_reference=provenance_reference,
        last_transition_at=OBSERVED_AT,
        ranking=MemoryRankingBreakdown(
            verification_millis=0,
            domain_millis=0,
            usage_millis=0,
            recency_millis=0,
            total_millis=0,
            relevance_score=0.0,
        ),
    )


@pytest.mark.parametrize(
    "memory_type",
    (
        MemoryType.BOARD_PROFILE,
        MemoryType.COMPONENT,
        MemoryType.PIN_BINDING,
        MemoryType.INTERFACE_BINDING,
        MemoryType.POWER_CONSTRAINT,
    ),
)
def test_hardware_records_map_to_hardware_and_pcb_in_enum_order(
    memory_type: MemoryType,
) -> None:
    assert map_memory_domains(_projection(memory_type)) == (
        MemoryDomain.HARDWARE,
        MemoryDomain.PCB,
    )


@pytest.mark.parametrize(
    ("subject", "expected"),
    (
        (VerificationSubjectType.FIRMWARE, (MemoryDomain.FIRMWARE,)),
        (
            VerificationSubjectType.HARDWARE,
            (MemoryDomain.HARDWARE, MemoryDomain.PCB),
        ),
        (VerificationSubjectType.TOOL_RESULT, (MemoryDomain.GENERAL,)),
    ),
)
def test_verification_history_uses_typed_subject_mapping(
    subject: VerificationSubjectType,
    expected: tuple[MemoryDomain, ...],
) -> None:
    assert (
        map_memory_domains(
            _projection(MemoryType.VERIFICATION_HISTORY, subject=subject)
        )
        == expected
    )


@pytest.mark.parametrize(
    ("provenance", "expected"),
    (
        (MemorySourceType.CODING_RESULT, (MemoryDomain.FIRMWARE,)),
        (MemorySourceType.DEBUG_SNAPSHOT, (MemoryDomain.DEBUG,)),
        (MemorySourceType.TELEMETRY_RESULT, (MemoryDomain.DEBUG,)),
        (
            MemorySourceType.DATASHEET_RESULT,
            (MemoryDomain.HARDWARE, MemoryDomain.PCB),
        ),
        (MemorySourceType.TOOL_RESULT, (MemoryDomain.GENERAL,)),
        (MemorySourceType.USER_INPUT, (MemoryDomain.GENERAL,)),
        (MemorySourceType.VERIFICATION_RESULT, (MemoryDomain.GENERAL,)),
        (MemorySourceType.MANUAL_DECISION, (MemoryDomain.GENERAL,)),
    ),
)
@pytest.mark.parametrize(
    "memory_type",
    (MemoryType.ENGINEERING_DECISION, MemoryType.KNOWN_ISSUE),
)
def test_decision_and_issue_use_provenance_without_verification_subject(
    memory_type: MemoryType,
    provenance: MemorySourceType,
    expected: tuple[MemoryDomain, ...],
) -> None:
    assert (
        map_memory_domains(
            _evidence(memory_type, provenance=provenance)
        )
        == expected
    )


@pytest.mark.parametrize(
    "memory_type",
    (MemoryType.ENGINEERING_DECISION, MemoryType.KNOWN_ISSUE),
)
def test_final_verification_subject_takes_priority_over_provenance(
    memory_type: MemoryType,
) -> None:
    source = _evidence(
        memory_type,
        provenance=MemorySourceType.DATASHEET_RESULT,
        subject=VerificationSubjectType.FIRMWARE,
    )
    assert map_memory_domains(source) == (MemoryDomain.FIRMWARE,)


def test_projection_without_provenance_and_unknown_input_safely_use_general() -> None:
    projection = _projection(
        MemoryType.ENGINEERING_DECISION,
        subject=None,
        logical_key="pcb-routing-power",
    )
    assert map_memory_domains(projection) == (MemoryDomain.GENERAL,)
    assert map_memory_domains(object()) == (MemoryDomain.GENERAL,)


def test_free_text_does_not_override_typed_general_mapping() -> None:
    source = _evidence(
        MemoryType.KNOWN_ISSUE,
        provenance=MemorySourceType.MANUAL_DECISION,
        provenance_reference="pcb-routing-power",
    )
    assert map_memory_domains(source) == (MemoryDomain.GENERAL,)


def test_tampered_input_fails_closed_to_general_without_mutation() -> None:
    source = _projection(MemoryType.COMPONENT)
    object.__setattr__(source, "memory_type", "not-a-memory-type")
    before = source.memory_type
    assert map_memory_domains(source) == (MemoryDomain.GENERAL,)
    assert source.memory_type == before


def test_mapping_is_repeatable_and_does_not_mutate_valid_input() -> None:
    source = _evidence(
        MemoryType.ENGINEERING_DECISION,
        provenance=MemorySourceType.DATASHEET_RESULT,
    )
    before = source.model_dump_json()
    first = map_memory_domains(source)
    second = map_memory_domains(source)
    assert first == second == (MemoryDomain.HARDWARE, MemoryDomain.PCB)
    assert source.model_dump_json() == before
