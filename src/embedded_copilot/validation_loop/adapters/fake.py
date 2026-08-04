from ..contracts import (
    FlashState,
    LoopState,
    ObservationState,
    ValidationSnapshot,
    ValidationSnapshotPort,
    VerificationState,
)


class FakeValidationSnapshotPort(ValidationSnapshotPort):
    def get_snapshot(self, project_id: str) -> ValidationSnapshot:
        return ValidationSnapshot.create(
            project_id=project_id,
            firmware_reference="artifact-1",
            device_reference="board-1",
            build_status=LoopState.BUILD_READY,
            flash_status=FlashState.PENDING,
            observation_status=ObservationState.PENDING,
            verification_status=VerificationState.REVIEW_REQUIRED,
        )


__all__ = ["FakeValidationSnapshotPort"]
