from __future__ import annotations

import copy
import hashlib

from pydantic import ValidationError

from .contracts import (
    ArtifactReference,
    BOMProposal,
    DatasheetTrustStatus,
    FirmwareArtifact,
    GenerationArtifact,
    GenerationRequest,
    GenerationType,
    HardwareDesignArtifact,
    InterfaceContract,
    SystemArchitecture,
)
from .exceptions import GenerationRequestRejected


class GenerationService:
    __slots__ = ()

    def generate(self, request: GenerationRequest) -> GenerationArtifact:
        if type(request) is not GenerationRequest:
            raise GenerationRequestRejected()
        try:
            checked = GenerationRequest.model_validate(copy.deepcopy(request))
        except (TypeError, ValidationError, ValueError):
            raise GenerationRequestRejected() from None
        if checked.generation_type is GenerationType.FIRMWARE:
            return self._firmware(checked)
        return self._hardware(checked)

    @staticmethod
    def _artifact_id(request: GenerationRequest, suffix: str) -> str:
        material = (
            request.project_id,
            request.generation_type.value,
            request.context_snapshot.context_fingerprint,
            request.recommendation.fingerprint,
            suffix,
        )
        digest = hashlib.sha256("|".join(material).encode("utf-8")).hexdigest()[:24]
        return f"artifact-{digest}"

    def _firmware(self, request: GenerationRequest) -> FirmwareArtifact:
        context = request.context_snapshot
        return FirmwareArtifact.create(
            artifact_id=self._artifact_id(request, "firmware"),
            project_id=request.project_id,
            files=("main.c", "CMakeLists.txt", "component.yaml", "README.md"),
            configuration=(
                f"project={context.project_name}",
                f"stage={context.stage.value}",
                "proposal_only=true",
            ),
            dependencies=("ESP-IDF",),
            summary="Firmware project proposal for engineering review.",
        )

    def _hardware(self, request: GenerationRequest) -> HardwareDesignArtifact:
        context = request.context_snapshot
        references = tuple(
            ArtifactReference(
                reference_id=item.reference_id,
                status=DatasheetTrustStatus.UNVERIFIED,
            )
            for item in context.datasheet_references
        )
        interface = InterfaceContract(
            name=context.decision_topic,
            protocol="UNVERIFIED",
            endpoints=(),
            notes="Interface details require verified engineering evidence.",
            status=DatasheetTrustStatus.UNVERIFIED,
        )
        bom = BOMProposal(
            component="Engineering review item",
            reason="Select from verified design evidence before procurement.",
            risk="Component specification is not verified in this projection.",
            alternative=None,
            status=DatasheetTrustStatus.UNVERIFIED,
        )
        if request.generation_type is GenerationType.INTERFACE:
            bom_items: tuple[BOMProposal, ...] = ()
        else:
            bom_items = (bom,)
        interfaces = (
            (interface,) if request.generation_type is not GenerationType.BOM else ()
        )
        return HardwareDesignArtifact.create(
            artifact_id=self._artifact_id(
                request, request.generation_type.value.lower()
            ),
            project_id=request.project_id,
            system_architecture=SystemArchitecture(
                system=context.project_name,
                components=("Engineering system",),
                constraints=context.constraints,
            ),
            interface_contracts=interfaces,
            bom=bom_items,
            references=references,
            summary="Hardware design proposal with unverified details marked for review.",
        )
