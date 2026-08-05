import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DebugPanel } from "./DebugPanel";
import { OptimizationPanel } from "../optimization/OptimizationPanel";

describe("v2.3 panels", () => {
  it("renders findings and confidence without execution controls", () => {
    const markup = renderToStaticMarkup(<><DebugPanel loading={false} error={null} snapshot={{ project_id: "demo", failure_reference: "failure:demo", findings: [{ finding_id: "f1", project_id: "demo", source_type: "VALIDATION", category: "UNKNOWN", severity: "MEDIUM", summary: "Review", evidence_reference: "evidence:demo", status: "PROJECTED", fingerprint: "hidden" }] , fingerprint: "hidden" }} /><OptimizationPanel loading={false} error={null} proposal={{ proposal_id: "proposal:demo:1", project_id: "demo", target_area: "TEST", suggested_change: "Review", reason: "Evidence", evidence_reference: "evidence:demo", risk: "Review", confidence: "PROJECTED", status: "PROPOSED", fingerprint: "hidden" }} /></>);
    expect(markup).toContain("DEBUGGING");
    expect(markup).toContain("OPTIMIZATION_REVIEW");
    expect(markup).toContain("PROJECTED");
    expect(markup).not.toContain("Apply Patch");
    expect(markup).not.toContain("Auto Fix");
    expect(markup).not.toContain("Flash");
  });
});
