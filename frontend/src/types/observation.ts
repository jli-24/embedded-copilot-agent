export type ObservationSnapshot = {
  device_id: string;
  boot_status: "BOOTED" | "NOT_BOOTED" | "UNKNOWN";
  firmware_version: string;
  health_status: "HEALTHY" | "DEGRADED" | "FAILED" | "UNKNOWN";
  error_summary: string;
  fingerprint: string;
};
