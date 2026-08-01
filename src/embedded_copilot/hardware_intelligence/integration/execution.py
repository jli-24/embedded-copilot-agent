"""Safe projection from a successful controlled execution snapshot."""

from datetime import datetime

from pydantic import ValidationError

from embedded_copilot.execution_runtime import (
    ExecutionResultStatus,
    ExecutionSnapshot,
    ExecutionState,
    ExecutionVerificationStatus,
)
from embedded_copilot.hardware_intelligence.exceptions import (
    HardwareIntelligenceRejected,
)
from embedded_copilot.hardware_intelligence.models import (
    HardwareAnalysisRequest,
    HardwareContextProjection,
    HardwareMetadata,
    hardware_context_fingerprint,
)


def project_execution_snapshot(
    snapshot: ExecutionSnapshot,
    *,
    hardware_id: str,
    device_type: str,
    board_reference: str,
    scenario_id: str,
    timestamp: datetime,
) -> HardwareAnalysisRequest:
    """Project safe references without reading any artifact body."""
    if type(snapshot) is not ExecutionSnapshot:
        raise HardwareIntelligenceRejected("execution projection rejected")
    try:
        snapshot = ExecutionSnapshot.model_validate(snapshot.model_copy(deep=True))
    except (TypeError, ValueError, ValidationError):
        raise HardwareIntelligenceRejected("execution projection rejected") from None
    if (
        snapshot.state is not ExecutionState.SUCCESS
        or snapshot.result is None
        or snapshot.result.status is not ExecutionResultStatus.SUCCESS
        or snapshot.verification is None
        or snapshot.verification.status is not ExecutionVerificationStatus.VALID
    ):
        raise HardwareIntelligenceRejected("execution projection rejected")

    references = tuple(sorted(item.reference_id for item in snapshot.result.artifacts))
    metadata = [
        HardwareMetadata(key="execution_id", value=snapshot.plan.execution_id),
        HardwareMetadata(key="execution_snapshot", value=snapshot.fingerprint),
    ]
    metadata.extend(
        HardwareMetadata(key=f"reference_{index:03d}", value=reference)
        for index, reference in enumerate(references)
    )
    safe_metadata = tuple(sorted(metadata, key=lambda item: item.key))
    context = HardwareContextProjection(
        hardware_id=hardware_id,
        device_type=device_type,
        board_reference=board_reference,
        safe_metadata=safe_metadata,
        fingerprint=hardware_context_fingerprint(
            hardware_id=hardware_id,
            device_type=device_type,
            board_reference=board_reference,
            safe_metadata=safe_metadata,
        ),
    )
    return HardwareAnalysisRequest(
        hardware_id=hardware_id,
        scenario_id=scenario_id,
        context=context,
        timestamp=timestamp,
    )
