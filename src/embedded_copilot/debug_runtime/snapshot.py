from __future__ import annotations

import hashlib
import json

from pydantic import ValidationError

from embedded_copilot.debug_runtime.exceptions import DebugObservationRejected
from embedded_copilot.debug_runtime.models import (
    DebugSourceType,
    FrozenDebugSnapshot,
    RegisterObservation,
    StackFrameObservation,
    TargetIdentity,
    TelemetrySnapshot,
    UARTObservation,
)


def snapshot_fingerprint(
    *,
    schema_version: str,
    snapshot_id: str,
    target_identity: TargetIdentity,
    observations: tuple[
        UARTObservation | RegisterObservation | StackFrameObservation, ...
    ],
    telemetry: TelemetrySnapshot,
    source_type: DebugSourceType,
) -> str:
    payload = {
        "observations": [
            item.model_dump(mode="json", by_alias=True) for item in observations
        ],
        "schema_version": schema_version,
        "snapshot_id": snapshot_id,
        "source_type": source_type.value,
        "target_identity": target_identity.model_dump(mode="json"),
        "telemetry": telemetry.model_dump(mode="json"),
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_snapshot(
    *,
    snapshot_id: str,
    target_identity: TargetIdentity,
    observations: tuple[
        UARTObservation | RegisterObservation | StackFrameObservation, ...
    ],
    telemetry: TelemetrySnapshot,
    source_type: DebugSourceType,
) -> FrozenDebugSnapshot:
    fingerprint = snapshot_fingerprint(
        schema_version="1.0",
        snapshot_id=snapshot_id,
        target_identity=target_identity,
        observations=observations,
        telemetry=telemetry,
        source_type=source_type,
    )
    try:
        return FrozenDebugSnapshot(
            snapshot_id=snapshot_id,
            target_identity=target_identity,
            observations=observations,
            telemetry=telemetry,
            source_type=source_type,
            fingerprint=fingerprint,
        )
    except ValidationError:
        raise DebugObservationRejected from None
