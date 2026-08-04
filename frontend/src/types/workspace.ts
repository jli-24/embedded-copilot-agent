export type WorkspaceSnapshotStatus = "UNAVAILABLE" | "PROJECTED" | "WAITING_APPROVAL" | "APPROVED";
export interface WorkspaceArtifactView {
  artifact_id: string;
  artifact_type: string;
  status: "PROPOSED" | "WAITING_APPROVAL";
  filenames: string[];
}
export interface WorkspaceSnapshot {
  project_id: string;
  artifacts: WorkspaceArtifactView[];
  status: WorkspaceSnapshotStatus;
  fingerprint: string;
}
