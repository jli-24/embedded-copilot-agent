from .contracts import ValidationSnapshotPort
from .service import ValidationLoopService


def create_validation_loop(
    port: ValidationSnapshotPort | None = None,
) -> ValidationLoopService | None:
    return ValidationLoopService(port) if port is not None else None


__all__ = ["create_validation_loop"]
