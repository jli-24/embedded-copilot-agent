import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ToolStatusPanel } from "./ToolStatusPanel";
import { BuildExecutionPanel } from "./BuildExecutionPanel";
import { FlashExecutionPanel } from "./FlashExecutionPanel";
import { DeviceObservationPanel } from "./DeviceObservationPanel";

describe("v2.1 tool adapter panels", () => {
  it("renders capability and safe execution projections only", () => {
    const markup = renderToStaticMarkup(<>
      <ToolStatusPanel loading={false} error={null} snapshot={{ tool_name: "ESP-IDF", version: "5.2", capabilities: ["build"], status: "AVAILABLE", fingerprint: "hidden" }} />
      <BuildExecutionPanel loading={false} error={null} result={{ status: "SUCCESS", tool_type: "ESP-IDF", operation: "build", artifact_reference: "a1", summary: "Approved projection", fingerprint: "hidden" }} />
      <FlashExecutionPanel loading={false} error="FLASH_APPROVAL_REQUIRED" result={null} />
      <DeviceObservationPanel loading={false} error={null} snapshot={{ device_id: "d1", boot_status: "BOOTED", firmware_version: "PROJECTED", health_status: "HEALTHY", error_summary: "", fingerprint: "hidden" }} />
    </>);
    expect(markup).toContain("ESP-IDF");
    expect(markup).toContain("AVAILABLE");
    expect(markup).not.toContain("Auto Flash");
    expect(markup).not.toContain("Execute");
    expect(markup).not.toContain("command");
    expect(markup).not.toContain("stdout");
  });
});
