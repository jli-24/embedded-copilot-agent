from .contracts import ApprovalGatePort
from .service import ApprovalGateService


def create_approval_gate(port: ApprovalGatePort) -> ApprovalGateService:
    return ApprovalGateService(port)


__all__ = ["create_approval_gate"]
