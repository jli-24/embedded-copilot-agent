export type DesignSourceType = "KICAD" | "ALTIUM" | "EASYEDA" | "UNKNOWN";
export type ProjectionStatus = "VERIFIED" | "PROJECTED" | "UNVERIFIED";
export type ComponentProjection = { reference: string; value: string | null; footprint: string | null; manufacturer: string | null; part_number: string | null; status: ProjectionStatus };
export type NetProjection = { name: string; connections: string[]; signal_type: string };
export type LayerProjection = { name: string; layer_type: string };
export type InterfaceProjection = { name: string; protocol: string; signals: string[] };
export type UnifiedHardwareModel = { project_id: string; design_id: string; design_source_type: DesignSourceType; components: ComponentProjection[]; nets: NetProjection[]; layers: LayerProjection[]; interfaces: InterfaceProjection[]; constraints: string[]; references: string[]; fingerprint: string };
export type HardwareReviewProposal = { review_id: string; project_id: string; category: "POWER" | "SIGNAL" | "GPIO" | "COMPONENT" | "LAYOUT" | "MANUFACTURING"; severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"; summary: string; evidence_reference: string; status: ProjectionStatus; fingerprint: string };
