import { describe, expect, it } from "vitest";
import { fetchDebugAnalysis, DebugRequestError } from "./debug";
import { approveOptimization, fetchOptimization } from "./optimization";

describe("v2.3 debug and optimization API", () => {
  it("uses stable paths and approval binding", async () => {
    const calls: string[] = [];
    const fetcher = async (path: string, init?: RequestInit) => {
      calls.push(path);
      if (init?.method === "POST") return new Response(JSON.stringify({ proposal_id: "proposal:demo:1" }), { status: 200 });
      return new Response(JSON.stringify({ project_id: "demo" }), { status: 200 });
    };
    await fetchDebugAnalysis("demo", fetcher as typeof fetch);
    const proposal = { proposal_id: "proposal:demo:1", project_id: "demo", target_area: "TEST", suggested_change: "Review", reason: "Evidence", evidence_reference: "evidence:demo", risk: "Review", confidence: "PROJECTED", status: "PROPOSED", fingerprint: "sha256:" + "a".repeat(64) } as const;
    await fetchOptimization("demo", fetcher as typeof fetch);
    await approveOptimization(proposal, fetcher as typeof fetch);
    expect(calls).toEqual(["/api/debug/v23/demo", "/api/optimization/v23/demo", "/api/optimization/v23/proposal%3Ademo%3A1/approve"]);
  });

  it("rejects unsafe project ids locally", async () => {
    await expect(fetchDebugAnalysis("../private")).rejects.toBeInstanceOf(DebugRequestError);
  });
});
