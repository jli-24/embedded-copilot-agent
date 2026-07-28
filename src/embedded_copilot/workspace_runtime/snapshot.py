from __future__ import annotations

import hashlib
import json

from embedded_copilot.workspace_runtime.models import (
    FrozenWorkspaceSnapshot,
    WorkspaceFileSummary,
)


def snapshot_fingerprint(
    *, schema_version: str, workspace_id: str, files: tuple[WorkspaceFileSummary, ...]
) -> str:
    payload = {
        "files": [item.model_dump(mode="json") for item in files],
        "schema_version": schema_version,
        "workspace_id": workspace_id,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_snapshot(
    *, workspace_id: str, files: tuple[WorkspaceFileSummary, ...]
) -> FrozenWorkspaceSnapshot:
    fingerprint = snapshot_fingerprint(
        schema_version="1.0", workspace_id=workspace_id, files=files
    )
    return FrozenWorkspaceSnapshot(
        workspace_id=workspace_id,
        files=files,
        snapshot_fingerprint=fingerprint,
    )
