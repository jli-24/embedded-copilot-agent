import type { DigitalTwinSnapshot } from "../types/digitalTwin";

export type DigitalTwinApiError = "DIGITAL_TWIN_UNAVAILABLE" | "DIGITAL_TWIN_NOT_FOUND" | "DIGITAL_TWIN_REJECTED";
export class DigitalTwinRequestError extends Error { readonly code: DigitalTwinApiError; constructor(code: DigitalTwinApiError) { super(code); this.name = "DigitalTwinRequestError"; this.code = code; } }
const projectPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/;

export async function fetchDigitalTwin(projectId: string, fetcher: typeof fetch = fetch): Promise<DigitalTwinSnapshot> {
  if (!projectPattern.test(projectId)) throw new DigitalTwinRequestError("DIGITAL_TWIN_REJECTED");
  let response: Response;
  try { response = await fetcher(`/api/digital-twin/v26/${encodeURIComponent(projectId)}`); } catch { throw new DigitalTwinRequestError("DIGITAL_TWIN_UNAVAILABLE"); }
  if (response.ok) { try { return await response.json() as DigitalTwinSnapshot; } catch { throw new DigitalTwinRequestError("DIGITAL_TWIN_REJECTED"); } }
  throw new DigitalTwinRequestError(response.status === 404 ? "DIGITAL_TWIN_NOT_FOUND" : response.status === 422 ? "DIGITAL_TWIN_REJECTED" : "DIGITAL_TWIN_UNAVAILABLE");
}
