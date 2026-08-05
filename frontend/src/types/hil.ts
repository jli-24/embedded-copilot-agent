export type HardwareCapabilitySnapshot = {
  project_id: string;
  device_reference: string;
  board_type: string;
  chip_family: string;
  interfaces: string[];
  capabilities: string[];
  fingerprint: string;
};

export type MetricProjection = { name: string; value: string };
export type ObservationStatus = "READY" | "CONNECTED" | "UNAVAILABLE" | "FAILED";
export type DeviceObservationSnapshot = {
  project_id: string;
  device_reference: string;
  observation_type: string;
  status: ObservationStatus;
  metrics: MetricProjection[];
  evidence_reference: string;
  fingerprint: string;
};

export type HILTestStatus = "PASSED" | "FAILED" | "BLOCKED" | "UNAVAILABLE";
export type HILOverallStatus = HILTestStatus;
export type TestCaseProjection = { name: string; status: HILTestStatus; summary: string; fingerprint: string };
export type HILValidationResult = {
  project_id: string;
  test_reference: string;
  device_reference: string;
  firmware_reference: string;
  test_cases: TestCaseProjection[];
  overall_status: HILOverallStatus;
  evidence_reference: string;
  fingerprint: string;
};
