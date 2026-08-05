import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { HardwareDesignPanel } from "./HardwareDesignPanel";
import { HardwareReviewPanel } from "./HardwareReviewPanel";

describe("v2.2 hardware panels", () => {
  it("renders safe design and review projections without mutation controls", () => {
    const markup = renderToStaticMarkup(<>
      <HardwareDesignPanel loading={false} error={null} model={{ project_id: "demo", design_id: "d1", design_source_type: "KICAD", components: [{ reference: "U1", value: "ESP32", footprint: null, manufacturer: null, part_number: null, status: "PROJECTED" }], nets: [{ name: "GND", connections: ["U1.1"], signal_type: "POWER" }], layers: [{ name: "F.Cu", layer_type: "SIGNAL" }], interfaces: [{ name: "UART", protocol: "UART", signals: ["TX", "RX"] }], constraints: ["Review required"], references: ["design:d1"], fingerprint: "hidden" }} />
      <HardwareReviewPanel loading={false} error={null} findings={[{ review_id: "r1", project_id: "demo", category: "COMPONENT", severity: "MEDIUM", summary: "Review required", evidence_reference: "design:d1", status: "PROJECTED", fingerprint: "hidden" }]} />
    </>);
    expect(markup).toContain("KICAD");
    expect(markup).toContain("COMPONENT");
    expect(markup).not.toContain("Edit");
    expect(markup).not.toContain("Download");
    expect(markup).not.toContain("Generate");
    expect(markup).not.toContain(".kicad_pcb");
  });
});
