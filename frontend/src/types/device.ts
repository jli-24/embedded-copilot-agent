export type DeviceSnapshot = {
  project_id: string;
  device_id: string;
  device_type: "ESP32" | "STM32" | "UNKNOWN";
  connection_status: "CONNECTED" | "DISCONNECTED" | "UNAVAILABLE";
  fingerprint: string;
};
