from __future__ import annotations

import copy
import hashlib
import json

from embedded_copilot.engineering_memory import (
    CreateCandidateRequest,
    KnownIssueMemory,
    KnownIssueSeverity,
    MemoryProvenance,
    MemorySourceType,
)
from embedded_copilot.knowledge.intelligence.exceptions import (
    KnowledgeMemoryBridgeRejected,
)
from embedded_copilot.knowledge.intelligence.models import (
    KnowledgeEntityType,
    MemoryBridgeProjection,
    MemoryBridgeRequest,
)


def _evidence_revision(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class KnowledgeMemoryBridge:
    __slots__ = ()

    def project(self, request: MemoryBridgeRequest) -> MemoryBridgeProjection:
        try:
            checked = MemoryBridgeRequest.model_validate(copy.deepcopy(request))
            evidence = checked.evidence
            if (
                evidence.entity_type is not KnowledgeEntityType.FAILURE_RULE
                or evidence.failure_rule is None
            ):
                raise KnowledgeMemoryBridgeRejected()
            rule = evidence.failure_rule
            candidate = KnownIssueMemory(
                issue_key=rule.issue_key,
                title=rule.title,
                severity=KnownIssueSeverity(rule.severity.value),
                description_summary=rule.description_summary,
                mitigation_summary=rule.mitigation_summary,
            )
            provenance = MemoryProvenance(
                source_type=MemorySourceType.VERIFICATION_RESULT,
                source_reference=evidence.evidence_id,
                source_revision=_evidence_revision(
                    evidence.model_dump(mode="json")
                ),
                created_by=checked.caller,
                observed_at=checked.requested_at,
            )
            create_request = CreateCandidateRequest(
                request_id=checked.request_id,
                operation_id=checked.operation_id,
                project_id=checked.project_id,
                memory_id=checked.memory_id,
                record_id=checked.record_id,
                expected_revision=checked.expected_revision,
                caller=checked.caller,
                requested_at=checked.requested_at,
                payload=candidate,
                provenance=provenance,
            )
            return MemoryBridgeProjection(
                evidence_id=evidence.evidence_id,
                candidate=candidate,
                create_request=create_request,
            )
        except KnowledgeMemoryBridgeRejected:
            raise
        except Exception:
            raise KnowledgeMemoryBridgeRejected() from None
