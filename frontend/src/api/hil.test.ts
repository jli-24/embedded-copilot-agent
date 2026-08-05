import { describe, expect, it } from "vitest";
import { fetchHILCapability, fetchHILObservation, fetchHILResult, HILRequestError } from "./hil";

describe("v2.5 HIL API", () => {
  it("uses stable read-only paths", async () => {
    const calls: string[] = [];
    const fetcher = async (path: string) => { calls.push(path); return new Response("{}", { status: 200 }); };
    await fetchHILCapability("demo", fetcher as typeof fetch);
    await fetchHILObservation("demo", fetcher as typeof fetch);
    await fetchHILResult("demo", fetcher as typeof fetch);
    expect(calls).toEqual([
      "/api/hil/v25/device/demo",
      "/api/hil/v25/observation/demo",
      "/api/hil/v25/result/demo",
    ]);
  });

  it("rejects unsafe project identifiers without a request", () => {
    expect(() => fetchHILCapability("../private")).toThrowError(HILRequestError);
    expect(() => fetchHILObservation("../private")).toThrowError(HILRequestError);
    expect(() => fetchHILResult("../private")).toThrowError(HILRequestError);
  });
});
