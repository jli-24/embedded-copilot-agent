from __future__ import annotations

from embedded_copilot.model_runtime.contracts import (
    ModelRequest,
    ModelResponse,
    ModelRuntimePort,
)


class FakeModelRuntimePort(ModelRuntimePort):
    def generate(self, request: ModelRequest) -> ModelResponse:
        checked = ModelRequest.model_validate(request.model_dump(mode="python"))
        return ModelResponse.create(
            artifact_projection=(
                f"artifact_type:{checked.artifact_type.value}",
                "proposal_only:true",
            ),
            summary="Deterministic model proposal for engineering review.",
            confidence=0.5,
        )


__all__ = ["FakeModelRuntimePort"]
