from .contracts import LoopStatePort
from .service import LoopCoordinatorService


def create_loop_coordinator(
    state_port: LoopStatePort,
    *,
    approval_gate: object | None = None,
    generation_port: object | None = None,
    build_port: object | None = None,
    validation_port: object | None = None,
    reasoning_port: object | None = None,
    memory_port: object | None = None,
) -> LoopCoordinatorService:
    return LoopCoordinatorService(
        state_port,
        approval_gate=approval_gate,
        generation_port=generation_port,
        build_port=build_port,
        validation_port=validation_port,
        reasoning_port=reasoning_port,
        memory_port=memory_port,
    )


__all__ = ["create_loop_coordinator"]
