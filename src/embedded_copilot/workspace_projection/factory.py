from .service import WorkspaceProjectionService


def create_workspace_projection_service() -> WorkspaceProjectionService:
    return WorkspaceProjectionService()


__all__ = ["create_workspace_projection_service"]
