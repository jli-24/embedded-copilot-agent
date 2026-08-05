export type OptimizationTargetArea = "FIRMWARE" | "HARDWARE" | "BUILD" | "CONFIGURATION" | "TEST";
export type OptimizationStatus = "PROPOSED" | "APPROVED" | "REJECTED";
export type OptimizationConfidence = "VERIFIED" | "PROJECTED" | "UNVERIFIED";
export type OptimizationProposal = { proposal_id: string; project_id: string; target_area: OptimizationTargetArea; suggested_change: string; reason: string; evidence_reference: string; risk: string; confidence: OptimizationConfidence; status: OptimizationStatus; fingerprint: string };
