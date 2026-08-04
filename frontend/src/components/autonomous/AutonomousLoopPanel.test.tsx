import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AutonomousLoopPanel } from "./AutonomousLoopPanel";
import type { AutonomousLoopSnapshot } from "../../types/autonomous";

const snapshot: AutonomousLoopSnapshot = {
  project_id: "demo", status: "EXECUTING", progress: 40, tasks: ["build"], current_task: "build", next_task: "verification",
  timeline: [{ stage: "REQUIREMENT", status: "COMPLETED", label: "Requirement" }],
  task_graph: { nodes: [{ node_id: "build", label: "Build", status: "RUNNING" }], edges: [] }, agents: [],
  approval: { status: "APPROVED", reviewer: "reviewer" }, verification: { status: "PENDING", review_required: true },
  repair: { status: "NOT_REQUIRED", iteration: 0, max_iterations: 3 }, updated_at: "2026-08-01T00:00:00Z", fingerprint: "sha256:" + "0".repeat(64),
};

describe("AutonomousLoopPanel", () => {
  it("renders read-only safe fields only", () => {
    const html = renderToStaticMarkup(<AutonomousLoopPanel snapshot={snapshot} />);
    expect(html).toContain("demo");
    expect(html).toContain("Requirement");
    expect(html).not.toContain("source_code");
    expect(html).not.toContain("prompt");
    expect(html).not.toContain("token");
    expect(html).not.toContain("fingerprint");
  });
});
