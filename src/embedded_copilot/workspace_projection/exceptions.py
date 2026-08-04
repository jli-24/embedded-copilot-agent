class WorkspaceProjectionError(RuntimeError):
    code = "WORKSPACE_PROJECTION_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class WorkspaceProjectionRejected(WorkspaceProjectionError):
    code = "WORKSPACE_PROJECTION_REJECTED"
