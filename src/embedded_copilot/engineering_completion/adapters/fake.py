from __future__ import annotations

from ..contracts import (
    EngineeringArchitectureSnapshot,
    EngineeringCompletionPort,
    EngineeringCompletionSnapshot,
    EngineeringConfidence,
    EngineeringInterfaceContract,
    EngineeringRequirementProjection,
    EngineeringReviewCategory,
    EngineeringReviewSnapshot,
    EngineeringReviewStatus,
)


def _snapshot(project_id: str) -> EngineeringCompletionSnapshot:
    requirement = EngineeringRequirementProjection.create(
        project_id=project_id,
        title="Embedded camera engineering definition",
        description="Structured read-only engineering requirement projection.",
        functional_requirements=("camera capture", "event recording"),
        non_functional_requirements=("low power",),
        constraints=("ESP32 class MCU",),
        interfaces=("SPI", "WiFi"),
        confidence=EngineeringConfidence.PROJECTED,
    )
    architecture = EngineeringArchitectureSnapshot.create(
        project_id=project_id,
        components=("camera", "controller"),
        interfaces=("SPI", "WiFi"),
        constraints=("low power",),
        decision_references=(f"decision:{project_id}:1",),
        confidence=EngineeringConfidence.PROJECTED,
    )
    interface = EngineeringInterfaceContract.create(
        interface_id=f"interface:{project_id}:spi",
        project_id=project_id,
        producer="camera",
        consumer="controller",
        protocol="SPI",
        data_reference=f"data:{project_id}:camera-frame",
        constraints=("bounded frame size",),
    )
    review = EngineeringReviewSnapshot.create(
        review_id=f"review:{project_id}:1",
        project_id=project_id,
        category=EngineeringReviewCategory.INTERFACE,
        status=EngineeringReviewStatus.UNVERIFIED,
        finding_reference=f"finding:{project_id}:interface",
        confidence=EngineeringConfidence.PROJECTED,
    )
    return EngineeringCompletionSnapshot.create(
        project_id=project_id,
        requirement=requirement,
        architecture=architecture,
        interfaces=(interface,),
        reviews=(review,),
    )


class FakeEngineeringCompletionPort(EngineeringCompletionPort):
    def get_snapshot(self, project_id: str) -> EngineeringCompletionSnapshot:
        return _snapshot(project_id)


__all__ = ["FakeEngineeringCompletionPort"]
