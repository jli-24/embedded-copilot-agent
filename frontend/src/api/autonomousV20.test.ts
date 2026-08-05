import { describe, expect, it, vi } from "vitest";
import { fetchAutonomousV20, approveAutonomousAction } from "./autonomousV20";

describe("v2.0 autonomous API", () => {
  it("uses the versioned snapshot route", async () => {
    const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify({ current_stage: "INITIALIZING" }), { status: 200 }));
    await fetchAutonomousV20("demo", fetcher as typeof fetch);
    expect(fetcher).toHaveBeenCalledWith("/api/v2/autonomous/loop/demo");
  });
  it("keeps approval as an explicit action", async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ current_stage: "PLANNING" }), { status: 200 }));
    await approveAutonomousAction("action-1", { action_fingerprint: "sha256:" + "1".repeat(64), reviewer: "reviewer", decided_at: "2026-08-01T00:00:00Z" }, fetcher as typeof fetch);
    const calls = fetcher.mock.calls as unknown as [string][];
    expect(calls[0][0]).toBe("/api/autonomous/action/action-1/approve");
  });
});
