"""Public Product Runtime facade."""

from embedded_copilot.product.contracts import ProductWorkspacePort


class ProductRuntime:
    __slots__ = ("__port",)

    def __init__(self, port: ProductWorkspacePort) -> None:
        self.__port = port

    def product_workspace_port(self) -> ProductWorkspacePort:
        return self.__port


__all__ = ("ProductRuntime",)
