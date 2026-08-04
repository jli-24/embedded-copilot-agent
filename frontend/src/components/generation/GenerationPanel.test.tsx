import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { GenerationPanel } from "./GenerationPanel";
import type { GenerationSnapshot } from "../../types/generation";

const snapshot: GenerationSnapshot = {
  project_id: "demo", status: "REVIEW_REQUIRED", fingerprint: "sha256:" + "0".repeat(64),
  artifacts: [{ artifact_id: "a-1", project_id: "demo", artifact_type: "FIRMWARE", files: ["main.c"], configuration: ["proposal_only=true"], dependencies: ["ESP-IDF"], summary: "Proposal", fingerprint: "sha256:" + "1".repeat(64) }],
};

describe("GenerationPanel", () => {
  it("renders projection fields and no source body controls", () => {
    const html = renderToStaticMarkup(<GenerationPanel snapshot={snapshot} error={null} loading={false} />);
    expect(html).toContain("main.c");
    expect(html).toContain("Firmware proposal");
    expect(html).not.toContain("textarea");
    expect(html).not.toContain("download");
    expect(html).not.toContain("prompt");
  });
});
