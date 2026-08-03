from __future__ import annotations

from embedded_copilot.datasheet_runtime.contracts import DatasheetRequest

from embedded_copilot.engineering_intelligence.contracts import (
    EvidenceSourceType,
    EvidenceTrustBasis,
)
from embedded_copilot.engineering_intelligence.evidence import build_evidence
from embedded_copilot.engineering_intelligence.contracts import EngineeringEvidence

DatasheetEvidence = EngineeringEvidence


async def project_datasheet_evidence(
    port: object,
    *,
    session_id: str,
    file_id: str,
    reference_id: str,
) -> tuple[object, ...]:
    request = DatasheetRequest(
        session_id=session_id,
        file_id=file_id,
        instruction_summary="Project existing datasheet candidates",
    )
    response = await port.analyze(request)
    summary = response.summary
    values: list[object] = []
    rank = 0
    if summary.component_candidate is not None:
        component = summary.component_candidate
        value = component.model or component.family
        values.append(
            build_evidence(
                evidence_id=f"{reference_id}-component",
                source_type=EvidenceSourceType.DATASHEET,
                trust_basis=EvidenceTrustBasis.PROJECTED,
                summary=f"Component candidate {value}",
                reference_id=reference_id,
                confidence=0.5,
                source_rank=rank,
                claim={
                    "subject": "component",
                    "parameter": "family",
                    "value": value,
                    "unit": "",
                },
            )
        )
        rank += 1
    for candidate in summary.interface_candidates:
        values.append(
            build_evidence(
                evidence_id=f"{reference_id}-interface-{candidate.name}",
                source_type=EvidenceSourceType.DATASHEET,
                trust_basis=EvidenceTrustBasis.PROJECTED,
                summary=f"Interface candidate {candidate.name}",
                reference_id=reference_id,
                confidence=0.5,
                source_rank=rank,
                claim={
                    "subject": "interface",
                    "parameter": "name",
                    "value": candidate.name,
                    "unit": "",
                },
            )
        )
        rank += 1
    for candidate in summary.electrical_candidates:
        bounds = f"{candidate.minimum}:{candidate.maximum}"
        values.append(
            build_evidence(
                evidence_id=f"{reference_id}-electrical-{candidate.kind}",
                source_type=EvidenceSourceType.DATASHEET,
                trust_basis=EvidenceTrustBasis.PROJECTED,
                summary=f"Electrical candidate {candidate.kind} {bounds} {candidate.unit}",
                reference_id=reference_id,
                confidence=0.5,
                source_rank=rank,
                claim={
                    "subject": "electrical",
                    "parameter": candidate.kind,
                    "value": bounds,
                    "unit": candidate.unit,
                },
            )
        )
        rank += 1
    for candidate in summary.section_candidates:
        values.append(
            build_evidence(
                evidence_id=f"{reference_id}-section-{candidate.name}",
                source_type=EvidenceSourceType.DATASHEET,
                trust_basis=EvidenceTrustBasis.PROJECTED,
                summary=f"Section candidate {candidate.name}",
                reference_id=reference_id,
                confidence=0.5,
                source_rank=rank,
            )
        )
        rank += 1
    return tuple(values)


__all__ = ["DatasheetEvidence", "project_datasheet_evidence"]
