import { describe, expect, it, vi } from "vitest";
import { AutonomousRequestError, fetchAutonomousLoop, validateProjectId } from "./autonomous";

describe("autonomous API adapter", () => {
  it("validates project ids and requests the fixed route", async () => {
    const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify({ project_id: "demo" }), { status: 200 }));
    await fetchAutonomousLoop("demo", fetcher as typeof fetch);
    expect(fetcher).toHaveBeenCalledWith("/api/autonomous/loop/demo");
    expect(() => validateProjectId("../private")).toThrowError(AutonomousRequestError);
  });

  it.each([[404, "AUTONOMOUS_PROJECT_NOT_FOUND"], [422, "AUTONOMOUS_SNAPSHOT_REJECTED"], [503, "AUTONOMOUS_UNAVAILABLE"]] as const)(
    "maps %s to a safe error", async (status, code) => {
      const fetcher = vi.fn(async () => new Response("private exception", { status }));
      await expect(fetchAutonomousLoop("demo", fetcher as typeof fetch)).rejects.toMatchObject({ code });
    },
  );
});
