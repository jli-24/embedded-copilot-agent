export type OptimizationCategory = "POWER" | "PERFORMANCE" | "MEMORY" | "LATENCY" | "COMMUNICATION" | "RELIABILITY";
export type OptimizationConfidence = "VERIFIED" | "PROJECTED" | "UNVERIFIED";
export type OptimizationStatus = "IDENTIFIED" | "REVIEW_REQUIRED" | "APPROVED" | "REJECTED";
export type OptimizationTarget = "FIRMWARE" | "HARDWARE" | "BUILD" | "CONFIGURATION" | "TEST";
export type OptimizationFinding = { finding_id: string; category: OptimizationCategory; target: OptimizationTarget; current_state: string; suggested_direction: string; risk: string; confidence: OptimizationConfidence; evidence_reference: string; status: OptimizationStatus; fingerprint: string };
export type OptimizationAnalysis = { project_id: string; findings: OptimizationFinding[]; fingerprint: string };
