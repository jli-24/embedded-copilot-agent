import { describe, expect, it, vi } from "vitest";
import { fetchWorkspace, WorkspaceRequestError } from "./workspace";
import { fetchToolchain } from "./toolchain";
import { fetchComponents } from "./components";
import { fetchRuntimeStatus } from "./runtime";

describe("v1.8 read-only API adapters", () => {
  it("uses fixed project routes", async () => {
    const fetcher = vi.fn(async (url: string) => new Response(
      url.includes("components") ? "[]" : url.includes("models/status") ? JSON.stringify({ provider: "unavailable", status: "unavailable", capabilities: [], model: null }) : "{}",
      { status: 200 },
    ));
    await fetchWorkspace("demo", fetcher as typeof fetch);
    await fetchToolchain("demo", fetcher as typeof fetch);
    await fetchComponents("demo", fetcher as typeof fetch);
    await fetchRuntimeStatus(fetcher as typeof fetch);
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
      "/api/workspace/demo", "/api/toolchain/demo", "/api/components/demo", "/api/v1/copilot/models/status",
    ]);
  });

  it("rejects unsafe project ids without a request", async () => {
    const fetcher = vi.fn();
    await expect(fetchWorkspace("../private", fetcher as typeof fetch)).rejects.toBeInstanceOf(WorkspaceRequestError);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("maps unavailable responses to fixed safe errors", async () => {
    const fetcher = async () => new Response("private exception", { status: 503 });
    await expect(fetchToolchain("demo", fetcher as typeof fetch)).rejects.toMatchObject({ code: "TOOLCHAIN_UNAVAILABLE" });
    await expect(fetchComponents("demo", fetcher as typeof fetch)).rejects.toMatchObject({ code: "COMPONENT_UNAVAILABLE" });
  });
});
