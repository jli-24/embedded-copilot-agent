from __future__ import annotations

import hashlib


def proposal_id(project_id: str, evidence_reference: str) -> str:
    digest = hashlib.sha256(f"{project_id}:{evidence_reference}".encode()).hexdigest()[:24]
    return f"proposal:{project_id}:{digest}"


__all__ = ["proposal_id"]
