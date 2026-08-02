"""Metadata-only Datasheet Runtime projection adapter."""

from __future__ import annotations

from datetime import datetime

from embedded_copilot.datasheet_runtime import DatasheetResponse

from embedded_copilot.engineering_intelligence.exceptions import (
    EngineeringIntelligenceRejected,
)
from embedded_copilot.engineering_intelligence.models import (
    DatasheetKnowledgeCategory,
    DatasheetKnowledgeProjection,
    EngineeringKnowledgeEvidence,
    EngineeringKnowledgeSourceType,
    EvidenceStatus,
    datasheet_projection_fingerprint,
    engineering_evidence_fingerprint,
)


def project_datasheet_knowledge(
    value: object,
    *,
    observed_at: datetime,
) -> DatasheetKnowledgeProjection:
    try:
        if type(value) is not DatasheetResponse:
            raise TypeError("typed datasheet response is required")
        copied = value.model_copy(deep=True)
        checked = DatasheetResponse.model_validate(copied)
        facts: list[EngineeringKnowledgeEvidence] = []
        source_id = checked.summary.file_id
        component = checked.summary.component_candidate
        if component is not None:
            facts.append(
                _evidence(
                    evidence_id=f"{source_id}:component",
                    fact_type=DatasheetKnowledgeCategory.MCU_CAPABILITY.value,
                    key="component",
                    value=component.model or component.family,
                    summary="Datasheet component candidate.",
                    reference_ids=(source_id,),
                    observed_at=observed_at,
                )
            )
        for item in checked.summary.interface_candidates:
            facts.append(
                _evidence(
                    evidence_id=f"{source_id}:interface:{item.name.casefold()}",
                    fact_type=DatasheetKnowledgeCategory.INTERFACE.value,
                    key="interface",
                    value=item.name,
                    summary="Datasheet interface candidate.",
                    reference_ids=(source_id,),
                    observed_at=observed_at,
                )
            )
        for index, item in enumerate(checked.summary.electrical_candidates, start=1):
            bounds = f"{item.minimum}:{item.maximum}:{item.unit}"
            facts.append(
                _evidence(
                    evidence_id=f"{source_id}:power:{index}",
                    fact_type=DatasheetKnowledgeCategory.POWER.value,
                    key=item.kind,
                    value=bounds,
                    summary="Datasheet electrical candidate.",
                    reference_ids=(source_id,),
                    observed_at=observed_at,
                )
            )
        for item in checked.summary.section_candidates:
            facts.append(
                _evidence(
                    evidence_id=f"{source_id}:section:{len(facts) + 1}",
                    fact_type=DatasheetKnowledgeCategory.LIMITATION.value,
                    key="section",
                    value=item.name,
                    summary="Datasheet section candidate.",
                    reference_ids=(source_id,),
                    observed_at=observed_at,
                )
            )
        ordered = tuple(sorted(facts, key=lambda item: item.evidence_id))
        values = dict(
            source_id=source_id,
            categories=tuple(DatasheetKnowledgeCategory),
            facts=ordered,
            review_required=True,
        )
        return DatasheetKnowledgeProjection(
            **values,
            fingerprint=datasheet_projection_fingerprint(**values),
        )
    except Exception:
        raise EngineeringIntelligenceRejected("intelligence request rejected") from None


def _evidence(
    *,
    evidence_id: str,
    fact_type: str,
    key: str,
    value: str,
    summary: str,
    reference_ids: tuple[str, ...],
    observed_at: datetime,
) -> EngineeringKnowledgeEvidence:
    values = dict(
        evidence_id=evidence_id,
        source_type=EngineeringKnowledgeSourceType.DATASHEET,
        fact_type=fact_type,
        key=key,
        value=value,
        summary=summary,
        status=EvidenceStatus.CANDIDATE,
        confidence=0.0,
        reference_ids=reference_ids,
        observed_at=observed_at,
    )
    return EngineeringKnowledgeEvidence(
        **values,
        fingerprint=engineering_evidence_fingerprint(**values),
    )
