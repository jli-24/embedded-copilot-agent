import { describe, expect, it, vi } from "vitest";
import { fetchDevice, DeviceRequestError } from "./device";
import { fetchObservation } from "./observation";
import { fetchValidationLoop } from "./validation";
import { submitFlash } from "./flash";

describe("v1.9 validation API adapters", () => {
  it("uses fixed read-only routes", async () => {
    const fetcher = vi.fn(async (url: string) => new Response(url.includes("flash") ? JSON.stringify({ status: "SUCCESS" }) : "{}", { status: 200 }));
    await fetchDevice("demo", fetcher as typeof fetch);
    await fetchObservation("demo", fetcher as typeof fetch);
    await fetchValidationLoop("demo", fetcher as typeof fetch);
    await submitFlash({ firmware_reference: "a", device_reference: "b" }, fetcher as typeof fetch);
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
      "/api/device/demo", "/api/validation/observation/demo", "/api/validation/loop/demo", "/api/validation/flash",
    ]);
  });

  it("rejects unsafe project ids before fetch", async () => {
    const fetcher = vi.fn();
    await expect(fetchDevice("../private", fetcher as typeof fetch)).rejects.toBeInstanceOf(DeviceRequestError);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("maps fixed flash capability errors", async () => {
    const fetcher = async () => new Response(JSON.stringify({ error: "FLASH_CAPABILITY_REQUIRED" }), { status: 422 });
    await expect(submitFlash({ firmware_reference: "a", device_reference: "b" }, fetcher as typeof fetch)).rejects.toMatchObject({ code: "FLASH_CAPABILITY_REQUIRED" });
  });
});
