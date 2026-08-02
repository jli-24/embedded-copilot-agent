from __future__ import annotations

import copy

from embedded_copilot.verification_agent import VerificationSubjectType

from .context import MemoryContextEvidence, MemoryDomain
from .models import MemorySourceType, MemoryType
from .read_projection import VerifiedMemoryReadProjection

_HARDWARE_TYPES = (
    MemoryType.BOARD_PROFILE,
    MemoryType.COMPONENT,
    MemoryType.PIN_BINDING,
    MemoryType.INTERFACE_BINDING,
    MemoryType.POWER_CONSTRAINT,
)
_DECISION_TYPES = (
    MemoryType.ENGINEERING_DECISION,
    MemoryType.KNOWN_ISSUE,
)


def _ordered_domains(
    *domains: MemoryDomain,
) -> tuple[MemoryDomain, ...]:
    return tuple(domain for domain in MemoryDomain if domain in domains)


def _subject_domains(
    subject: VerificationSubjectType | None,
) -> tuple[MemoryDomain, ...]:
    if subject is VerificationSubjectType.FIRMWARE:
        return (MemoryDomain.FIRMWARE,)
    if subject is VerificationSubjectType.HARDWARE:
        return _ordered_domains(MemoryDomain.HARDWARE, MemoryDomain.PCB)
    return (MemoryDomain.GENERAL,)


def _provenance_domains(
    provenance: MemorySourceType,
) -> tuple[MemoryDomain, ...]:
    if provenance is MemorySourceType.CODING_RESULT:
        return (MemoryDomain.FIRMWARE,)
    if provenance in (
        MemorySourceType.DEBUG_SNAPSHOT,
        MemorySourceType.TELEMETRY_RESULT,
    ):
        return (MemoryDomain.DEBUG,)
    if provenance is MemorySourceType.DATASHEET_RESULT:
        return _ordered_domains(MemoryDomain.HARDWARE, MemoryDomain.PCB)
    return (MemoryDomain.GENERAL,)


def _revalidate(
    source: object,
) -> VerifiedMemoryReadProjection | MemoryContextEvidence | None:
    if isinstance(source, VerifiedMemoryReadProjection):
        return VerifiedMemoryReadProjection.model_validate(copy.deepcopy(source))
    if isinstance(source, MemoryContextEvidence):
        return MemoryContextEvidence.model_validate(copy.deepcopy(source))
    return None


def map_memory_domains(
    source: VerifiedMemoryReadProjection | MemoryContextEvidence,
) -> tuple[MemoryDomain, ...]:
    try:
        checked = _revalidate(source)
        if checked is None:
            return (MemoryDomain.GENERAL,)

        memory_type = checked.memory_type
        if memory_type in _HARDWARE_TYPES:
            return _ordered_domains(MemoryDomain.HARDWARE, MemoryDomain.PCB)
        if memory_type is MemoryType.VERIFICATION_HISTORY:
            return _subject_domains(checked.verification_subject)
        if memory_type in _DECISION_TYPES:
            if checked.verification_subject is not None:
                return _subject_domains(checked.verification_subject)
            if isinstance(checked, MemoryContextEvidence):
                return _provenance_domains(checked.provenance_source_type)
        return (MemoryDomain.GENERAL,)
    except Exception:
        return (MemoryDomain.GENERAL,)
