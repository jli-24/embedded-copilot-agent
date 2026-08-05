export type DebugSourceType = "BUILD" | "FLASH" | "RUNTIME" | "VALIDATION" | "HARDWARE";
export type DebugCategory = "COMPILE" | "LINK" | "MEMORY" | "PERIPHERAL" | "COMMUNICATION" | "POWER" | "TIMING" | "UNKNOWN";
export type DebugSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type DebugStatus = "VERIFIED" | "PROJECTED" | "UNVERIFIED";
export type DebugFinding = { finding_id: string; project_id: string; source_type: DebugSourceType; category: DebugCategory; severity: DebugSeverity; summary: string; evidence_reference: string; status: DebugStatus; fingerprint: string };
export type DebugAnalysisSnapshot = { project_id: string; failure_reference: string; findings: DebugFinding[]; fingerprint: string };
