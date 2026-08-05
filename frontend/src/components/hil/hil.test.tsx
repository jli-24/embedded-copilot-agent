import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { HardwareCapabilityPanel } from "./HardwareCapabilityPanel";
import { DeviceObservationPanel } from "./DeviceObservationPanel";
import { HILValidationPanel } from "./HILValidationPanel";

describe("v2.5 HIL panels", () => {
  it("renders safe capability, observation, and validation projections", () => {
    const markup = renderToStaticMarkup(<>
      <HardwareCapabilityPanel loading={false} error={null} snapshot={{ project_id: "demo", device_reference: "device:demo", board_type: "ESP32-S3", chip_family: "ESP32", interfaces: ["UART", "JTAG"], capabilities: ["WIFI"], fingerprint: "hidden" }} />
      <DeviceObservationPanel loading={false} error={null} snapshot={{ project_id: "demo", device_reference: "device:demo", observation_type: "BOOT_HEALTH", status: "CONNECTED", metrics: [{ name: "boot_count", value: "1" }], evidence_reference: "evidence:demo", fingerprint: "hidden" }} />
      <HILValidationPanel loading={false} error={null} result={{ project_id: "demo", test_reference: "test:demo", device_reference: "device:demo", firmware_reference: "firmware:demo", test_cases: [{ name: "device_boot", status: "PASSED", summary: "Boot available", fingerprint: "hidden" }], overall_status: "PASSED", evidence_reference: "evidence:demo", fingerprint: "hidden" }} />
    </>);
    expect(markup).toContain("ESP32-S3");
    expect(markup).toContain("CONNECTED");
    expect(markup).toContain("PASSED");
    expect(markup).not.toContain("Run Test");
    expect(markup).not.toContain("Flash Device");
    expect(markup).not.toContain("Control Device");
    expect(markup).not.toContain("Apply Fix");
  });
});
