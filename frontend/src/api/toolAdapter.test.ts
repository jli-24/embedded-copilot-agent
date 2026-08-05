import { describe, expect, it } from "vitest";
import { fetchToolCapability, fetchToolDevice, ToolAdapterRequestError } from "./toolAdapter";

describe("v2.1 tool adapter API", () => {
  it("uses the capability and device projection paths", async () => {
    const calls: string[] = [];
    const fetcher = async (path: string) => {
      calls.push(path);
      return new Response(JSON.stringify({}), { status: 200 });
    };
    await fetchToolCapability("demo", fetcher as typeof fetch);
    await fetchToolDevice("demo", fetcher as typeof fetch);
    expect(calls).toEqual(["/api/toolchain/v21/status/demo", "/api/toolchain/v21/device/demo"]);
  });

  it("rejects unsafe project identifiers without a request", async () => {
    expect(() => fetchToolCapability("../private")).toThrowError(ToolAdapterRequestError);
    expect(() => fetchToolDevice("../private")).toThrowError(ToolAdapterRequestError);
  });
});
