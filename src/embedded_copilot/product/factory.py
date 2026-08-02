"""Product Runtime composition entry point."""

from embedded_copilot.product.facade import ProductRuntime
from embedded_copilot.product.runtime import _create_product_workspace_service


def create_product_runtime() -> ProductRuntime:
    return ProductRuntime(_create_product_workspace_service())


__all__ = ("create_product_runtime",)
