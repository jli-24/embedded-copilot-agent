export type ToolCapabilitySnapshot = {
  tool_name: string;
  version: string;
  capabilities: string[];
  status: "AVAILABLE" | "UNAVAILABLE";
  fingerprint: string;
};

export type ToolExecutionResult = {
  status: "SUCCESS" | "FAILED" | "UNAVAILABLE" | "APPROVAL_REQUIRED";
  tool_type: string;
  operation: string;
  artifact_reference: string | null;
  summary: string;
  fingerprint: string;
};

export type ObservationSnapshot = {
  device_id: string;
  boot_status: string;
  firmware_version: string;
  health_status: string;
  error_summary: string;
  fingerprint: string;
};
