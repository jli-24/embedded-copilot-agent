import { describe, expect, it } from "vitest";
import { fetchDigitalTwin, DigitalTwinRequestError } from "./digitalTwin";
import { fetchOptimizationAnalysis, OptimizationV26RequestError } from "./optimizationV26";

describe("v2.6 projection API", () => {
  it("uses stable read paths", async () => {
    const calls: string[] = [];
    const fetcher = async (path: string) => { calls.push(path); return new Response("{}", { status: 200 }); };
    await fetchDigitalTwin("demo", fetcher as typeof fetch);
    await fetchOptimizationAnalysis("demo", fetcher as typeof fetch);
    expect(calls).toEqual(["/api/digital-twin/v26/demo", "/api/optimization/v26/demo"]);
  });

  it("rejects unsafe project identifiers locally", async () => {
    await expect(fetchDigitalTwin("../private")).rejects.toBeInstanceOf(DigitalTwinRequestError);
    await expect(fetchOptimizationAnalysis("../private")).rejects.toBeInstanceOf(OptimizationV26RequestError);
  });
});
