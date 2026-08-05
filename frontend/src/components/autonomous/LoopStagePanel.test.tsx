import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LoopStagePanel } from "./LoopStagePanel";
import { ApprovalPanel } from "./ApprovalPanel";
import type { AutonomousLoopSnapshotV20 } from "../../types/autonomousV20";

const snapshot: AutonomousLoopSnapshotV20 = { project_id: "demo", loop_id: "loop-1", current_stage: "WAITING_APPROVAL", completed_stages: ["INITIALIZING"], pending_action: { action_id: "a1", loop_id: "loop-1", action_type: "FLASH", action_fingerprint: "sha256:" + "1".repeat(64), approval_status: "PENDING" }, approval_status: "PENDING", iteration: 1, timeline: [], fingerprint: "hidden" };
describe("v2.0 autonomous panels", () => {
  it("shows stage and explicit approval controls only", () => {
    const html = renderToStaticMarkup(<><LoopStagePanel snapshot={snapshot} /><ApprovalPanel snapshot={snapshot} onApprove={() => undefined} onReject={() => undefined} /></>);
    expect(html).toContain("WAITING_APPROVAL");
    expect(html).toContain("Approve");
    expect(html).toContain("Reject");
    expect(html).not.toContain("Execute");
    expect(html).not.toContain("Auto Repair");
  });
});
