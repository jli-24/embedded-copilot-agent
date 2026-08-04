import type { DeviceSnapshot } from "../types/device";
export type DeviceApiError = "DEVICE_NOT_FOUND" | "DEVICE_SNAPSHOT_REJECTED" | "DEVICE_UNAVAILABLE";
export class DeviceRequestError extends Error { readonly code: DeviceApiError; constructor(code: DeviceApiError) { super(code); this.code = code; } }
export async function fetchDevice(projectId: string, fetcher: typeof fetch = fetch): Promise<DeviceSnapshot> {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(projectId)) throw new DeviceRequestError("DEVICE_SNAPSHOT_REJECTED");
  let response: Response; try { response = await fetcher(`/api/device/${encodeURIComponent(projectId)}`); } catch { throw new DeviceRequestError("DEVICE_UNAVAILABLE"); }
  if (response.ok) { try { return (await response.json()) as DeviceSnapshot; } catch { throw new DeviceRequestError("DEVICE_SNAPSHOT_REJECTED"); } }
  throw new DeviceRequestError(response.status === 404 ? "DEVICE_NOT_FOUND" : response.status === 422 ? "DEVICE_SNAPSHOT_REJECTED" : "DEVICE_UNAVAILABLE");
}
