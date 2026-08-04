import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DevicePanel } from "./DevicePanel";
import { FlashPanel } from "./FlashPanel";
import { ObservationPanel } from "./ObservationPanel";
import { ValidationLoopPanel } from "./ValidationLoopPanel";

describe("v1.9 validation panels", () => {
  it("renders status projections without mutation controls or sensitive fields", () => {
    const html = [
      renderToStaticMarkup(<DevicePanel loading={false} error={null} snapshot={{ project_id: "demo", device_id: "board-1", device_type: "ESP32", connection_status: "CONNECTED", fingerprint: "hidden" }} />),
      renderToStaticMarkup(<FlashPanel loading={false} error={null} />),
      renderToStaticMarkup(<ObservationPanel loading={false} error={null} snapshot={{ device_id: "board-1", boot_status: "BOOTED", firmware_version: "1.0", health_status: "HEALTHY", error_summary: "", fingerprint: "hidden" }} />),
      renderToStaticMarkup(<ValidationLoopPanel loading={false} error={null} snapshot={{ project_id: "demo", firmware_reference: "a", device_reference: "b", build_status: "BUILD_READY", flash_status: "PENDING", observation_status: "PENDING", verification_status: "REVIEW_REQUIRED", fingerprint: "hidden" }} />),
    ].join("");
    expect(html).toContain("CONNECTED");
    expect(html).toContain("REVIEW_REQUIRED");
    expect(html).not.toContain("Flash Now");
    expect(html).not.toContain("Execute");
    expect(html).not.toContain("fingerprint");
    expect(html).not.toContain("command");
  });
});
