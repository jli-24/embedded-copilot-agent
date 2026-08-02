"""Stateless Hardware Validation orchestration."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.engineering_validation.contracts import DeviceEvidencePort
from embedded_copilot.engineering_validation.exceptions import (
    HardwareValidationRejected,
)
from embedded_copilot.engineering_validation.integration.inputs import (
    HardwareValidationRequest,
    project_validation_input,
)
from embedded_copilot.engineering_validation.models import (
    DeviceEvidenceCollectionResult,
    HardwareValidationReport,
)
from embedded_copilot.engineering_validation.projection import (
    build_collection_request,
    build_report,
    build_test_plan,
    merge_evidence,
)


class _HardwareValidationAgent:
    __slots__ = ("__evidence_port",)

    def __init__(self, evidence_port: DeviceEvidencePort) -> None:
        self.__evidence_port = evidence_port

    def validate(self, request: HardwareValidationRequest) -> HardwareValidationReport:
        try:
            source = project_validation_input(request)
            plan = build_test_plan(source)
            collection_request = build_collection_request(source, plan)
        except (TypeError, ValueError, ValidationError):
            raise HardwareValidationRejected(
                "hardware validation request rejected"
            ) from None

        collection = self._collect(collection_request)
        records = None if collection is None else collection.records
        return build_report(
            source,
            plan,
            merge_evidence(source.baseline.records, records),
        )

    def _collect(self, request):
        try:
            result = self.__evidence_port.collect(request.model_copy(deep=True))
            if type(result) is not DeviceEvidenceCollectionResult:
                return None
            checked = DeviceEvidenceCollectionResult.model_validate(
                result.model_copy(deep=True)
            )
            if (
                checked.proposal_id != request.proposal_id
                or checked.project_id != request.project_id
                or checked.test_plan_fingerprint != request.test_plan.fingerprint
            ):
                return None
            return checked
        except Exception:
            return None
