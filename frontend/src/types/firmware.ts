export type FirmwareFramework = "ESP_IDF" | "PLATFORMIO" | "UNKNOWN";
export type FirmwareBuildStatus = "READY" | "SUCCESS" | "FAILED" | "UNAVAILABLE";
export type SourceProjection = { source_count: number; header_count: number; entry_points: string[]; interfaces: string[]; fingerprint: string };
export type BuildConfigurationProjection = { target: string; profile: string; configuration_reference: string };
export type FirmwareProjectSnapshot = { project_id: string; firmware_reference: string; framework: FirmwareFramework; targets: string[]; source_projection: SourceProjection; build_configuration: BuildConfigurationProjection; fingerprint: string };
export type FirmwareBuildResult = { status: FirmwareBuildStatus; artifact_reference: string; build_status: FirmwareBuildStatus; summary: string; fingerprint: string };
