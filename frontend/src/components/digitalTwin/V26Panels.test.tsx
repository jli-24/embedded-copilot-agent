import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DigitalTwinPanel } from "./DigitalTwinPanel";
import { OptimizationAnalysisPanel } from "../optimization/OptimizationAnalysisPanel";

describe("v2.6 projection panels", () => {
  it("renders metrics and findings without execution controls", () => {
    const markup = renderToStaticMarkup(<>
      <DigitalTwinPanel loading={false} error={null} snapshot={{ project_id: "demo", hardware_reference: "hardware:demo", firmware_reference: "firmware:demo", device_reference: "device:demo", validation_reference: "validation:demo", metrics: { cpu_usage: "12%", memory_usage: "34%", flash_usage: "42%", ram_usage: "28%", latency: "5ms", power_estimate: "120mW", communication_quality: "GOOD", fingerprint: "hidden" }, constraints: [{ constraint_type: "POWER", reference: "constraint:demo", status: "PROJECTED", fingerprint: "hidden" }], fingerprint: "hidden" }} />
      <OptimizationAnalysisPanel loading={false} error={null} analysis={{ project_id: "demo", fingerprint: "hidden", findings: [{ finding_id: "finding:demo:1", category: "PERFORMANCE", target: "TEST", current_state: "Projected metrics are available.", suggested_direction: "Review measured latency.", risk: "Human review required.", confidence: "PROJECTED", evidence_reference: "evidence:demo", status: "REVIEW_REQUIRED", fingerprint: "hidden" }] }} />
    </>);
    expect(markup).toContain("12%");
    expect(markup).toContain("PERFORMANCE");
    expect(markup).not.toContain("Apply Optimization");
    expect(markup).not.toContain("Modify Firmware");
    expect(markup).not.toContain("Generate Patch");
  });
});
