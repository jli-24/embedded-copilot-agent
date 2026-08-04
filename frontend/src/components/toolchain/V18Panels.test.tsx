import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { WorkspacePanel } from "./WorkspacePanel";
import { BuildPanel } from "./BuildPanel";
import { ComponentRecommendationPanel } from "../components/ComponentRecommendationPanel";

describe("v1.8 panels", () => {
  it("renders safe read-only projection fields", () => {
    const workspace = renderToStaticMarkup(<WorkspacePanel loading={false} error={null} snapshot={{ project_id: "demo", artifacts: [{ artifact_id: "a1", artifact_type: "FIRMWARE", status: "WAITING_APPROVAL", filenames: ["main.c"] }], status: "WAITING_APPROVAL", fingerprint: "hidden" }} />);
    const build = renderToStaticMarkup(<BuildPanel loading={false} error={null} snapshot={{ build_status: "SUCCESS", artifact: { reference_id: "b1", artifact_type: "FIRMWARE" }, workspace_status: "APPROVED", fingerprint: "hidden" }} />);
    const components = renderToStaticMarkup(<ComponentRecommendationPanel loading={false} error={null} items={[{ part_number: "ESP32-S3", manufacturer: "Espressif", reason: "fit", datasheet_reference: "datasheet:1", supplier_links: ["https://supplier.example"], alternatives: ["STM32F4"] }]} />);
    expect(workspace + build + components).toContain("FIRMWARE");
    expect(workspace + build + components).not.toContain("prompt");
    expect(workspace + build + components).not.toContain("command");
    expect(workspace + build + components).not.toContain("fingerprint");
    expect(workspace + build + components).not.toContain("Purchase");
  });
});
