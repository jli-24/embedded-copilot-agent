import { describe, expect, it, vi } from "vitest";
import { fetchGeneration, GenerationRequestError } from "./generation";

describe("generation API adapter", () => {
  it("requests the fixed project route", async () => {
    const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify({ project_id: "demo" }), { status: 200 }));
    await fetchGeneration("demo", fetcher as typeof fetch);
    expect(fetcher).toHaveBeenCalledWith("/api/generation/demo");
  });
  it("rejects unsafe ids and maps unavailable responses", async () => {
    await expect(fetchGeneration("../private")).rejects.toBeInstanceOf(GenerationRequestError);
    const fetcher = vi.fn(async () => new Response("private exception", { status: 503 }));
    await expect(fetchGeneration("demo", fetcher as typeof fetch)).rejects.toMatchObject({ code: "GENERATION_UNAVAILABLE" });
  });
});
