export type MetricsProjection = { cpu_usage: string; memory_usage: string; flash_usage: string; ram_usage: string; latency: string; power_estimate: string; communication_quality: string; fingerprint: string };
export type ConstraintProjection = { constraint_type: string; reference: string; status: string; fingerprint: string };
export type DigitalTwinSnapshot = { project_id: string; hardware_reference: string; firmware_reference: string; device_reference: string; validation_reference: string; metrics: MetricsProjection; constraints: ConstraintProjection[]; fingerprint: string };
