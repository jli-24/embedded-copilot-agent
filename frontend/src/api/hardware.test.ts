import { describe, expect, it } from "vitest";
import { fetchHardwareDesign, fetchHardwareReview, HardwareRequestError } from "./hardware";

describe("v2.2 hardware API", () => {
  it("uses stable design and review paths", async () => {
    const calls: string[] = [];
    const fetcher = async (path: string) => { calls.push(path); return new Response("{}", { status: 200 }); };
    await fetchHardwareDesign("demo", fetcher as typeof fetch);
    await fetchHardwareReview("demo", fetcher as typeof fetch);
    expect(calls).toEqual(["/api/hardware/v22/design/demo", "/api/hardware/v22/review/demo"]);
  });

  it("rejects unsafe project identifiers without a request", () => {
    expect(() => fetchHardwareDesign("../private")).toThrowError(HardwareRequestError);
    expect(() => fetchHardwareReview("../private")).toThrowError(HardwareRequestError);
  });
});
