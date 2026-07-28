class VSCodeCapabilityUnavailable(RuntimeError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("vscode capability unavailable")

    def __repr__(self) -> str:
        return "VSCodeCapabilityUnavailable()"
