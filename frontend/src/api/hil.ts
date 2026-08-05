import type { DeviceObservationSnapshot, HILValidationResult, HardwareCapabilitySnapshot } from "../types/hil";

export type HILApiError = "DEVICE_UNAVAILABLE" | "OBSERVATION_UNAVAILABLE" | "HIL_APPROVAL_REQUIRED" | "HIL_FAILED" | "HIL_RESULT_NOT_FOUND" | "HIL_REJECTED";
export class HILRequestError extends Error { readonly code: HILApiError; constructor(code: HILApiError) { super(code); this.name = "HILRequestError"; this.code = code; } }
const projectPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/;

async function get<T>(path: string, fetcher: typeof fetch, notFound: HILApiError, rejected: HILApiError): Promise<T> {
  let response: Response;
  try { response = await fetcher(path); } catch { throw new HILRequestError("HIL_FAILED"); }
  if (response.ok) { try { return await response.json() as T; } catch { throw new HILRequestError(rejected); } }
  throw new HILRequestError(response.status === 404 ? notFound : response.status === 422 ? rejected : "HIL_FAILED");
}

export function fetchHILCapability(projectId: string, fetcher: typeof fetch = fetch): Promise<HardwareCapabilitySnapshot> {
  if (!projectPattern.test(projectId)) throw new HILRequestError("HIL_REJECTED");
  return get(`/api/hil/v25/device/${encodeURIComponent(projectId)}`, fetcher, "HIL_RESULT_NOT_FOUND", "HIL_REJECTED");
}

export function fetchHILObservation(projectId: string, fetcher: typeof fetch = fetch): Promise<DeviceObservationSnapshot> {
  if (!projectPattern.test(projectId)) throw new HILRequestError("HIL_REJECTED");
  return get(`/api/hil/v25/observation/${encodeURIComponent(projectId)}`, fetcher, "HIL_RESULT_NOT_FOUND", "HIL_REJECTED");
}

export function fetchHILResult(projectId: string, fetcher: typeof fetch = fetch): Promise<HILValidationResult> {
  if (!projectPattern.test(projectId)) throw new HILRequestError("HIL_REJECTED");
  return get(`/api/hil/v25/result/${encodeURIComponent(projectId)}`, fetcher, "HIL_RESULT_NOT_FOUND", "HIL_REJECTED");
}
