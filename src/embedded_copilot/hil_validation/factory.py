from .contracts import HILAdapterPort
from .service import HILValidationService


def create_hil_validation_service(
    adapter: HILAdapterPort | None = None,
) -> HILValidationService:
    return HILValidationService(adapter)


__all__ = ["create_hil_validation_service"]
