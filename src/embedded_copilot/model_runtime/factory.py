from __future__ import annotations

from .adapters.local import LocalModelAdapter
from .contracts import ModelRuntimePort
from .service import ModelRuntimeService


def create_model_service(port: ModelRuntimePort | None = None) -> ModelRuntimeService:
    return ModelRuntimeService(port or LocalModelAdapter())


create_model_runtime_service = create_model_service


__all__ = ["create_model_runtime_service", "create_model_service"]
