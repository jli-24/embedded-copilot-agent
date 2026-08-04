export type BuildStatus = "PENDING" | "BUILDING" | "SUCCESS" | "FAILED";
export interface ToolchainArtifactReference {
  reference_id: string;
  artifact_type: string;
}
export interface ToolchainSnapshot {
  build_status: BuildStatus;
  artifact: ToolchainArtifactReference | null;
  workspace_status: string;
  fingerprint: string;
}
