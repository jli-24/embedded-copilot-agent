export type GenerationStatus = "PROPOSED" | "REVIEW_REQUIRED" | "READY";
export type ArtifactType = "FIRMWARE" | "HARDWARE";
export type DatasheetTrustStatus = "VERIFIED" | "PROJECTED" | "UNVERIFIED";

export interface FirmwareArtifact {
  artifact_id: string;
  project_id: string;
  artifact_type: "FIRMWARE";
  files: string[];
  configuration: string[];
  dependencies: string[];
  summary: string;
  fingerprint: string;
}
export interface SystemArchitecture {
  system: string;
  components: string[];
  constraints: string[];
}
export interface InterfaceContract {
  name: string;
  protocol: string;
  endpoints: string[];
  notes: string;
  status: DatasheetTrustStatus;
}
export interface BOMProposal {
  component: string;
  reason: string;
  risk: string;
  alternative: string | null;
  status: DatasheetTrustStatus;
}
export interface HardwareArtifact {
  artifact_id: string;
  project_id: string;
  artifact_type: "HARDWARE";
  system_architecture: SystemArchitecture;
  interface_contracts: InterfaceContract[];
  bom: BOMProposal[];
  references: { reference_id: string; status: DatasheetTrustStatus }[];
  summary: string;
  fingerprint: string;
}
export type GenerationArtifact = FirmwareArtifact | HardwareArtifact;
export interface GenerationSnapshot {
  project_id: string;
  status: GenerationStatus;
  artifacts: GenerationArtifact[];
  fingerprint: string;
}
