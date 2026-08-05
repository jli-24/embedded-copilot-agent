import type { HardwareReviewProposal, UnifiedHardwareModel } from "../types/hardware";

export type HardwareApiError = "HARDWARE_UNAVAILABLE" | "DESIGN_NOT_FOUND" | "DESIGN_REJECTED" | "REVIEW_UNAVAILABLE";
export class HardwareRequestError extends Error { readonly code: HardwareApiError; constructor(code: HardwareApiError) { super(code); this.name = "HardwareRequestError"; this.code = code; } }
const projectPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/;

async function request<T>(path: string, fetcher: typeof fetch, notFound: HardwareApiError, rejected: HardwareApiError): Promise<T> {
  let response: Response;
  try { response = await fetcher(path); } catch { throw new HardwareRequestError("HARDWARE_UNAVAILABLE"); }
  if (response.ok) { try { return (await response.json()) as T; } catch { throw new HardwareRequestError(rejected); } }
  throw new HardwareRequestError(response.status === 404 ? notFound : response.status === 422 ? rejected : "HARDWARE_UNAVAILABLE");
}

export function fetchHardwareDesign(projectId: string, fetcher: typeof fetch = fetch): Promise<UnifiedHardwareModel> {
  if (!projectPattern.test(projectId)) throw new HardwareRequestError("DESIGN_REJECTED");
  return request(`/api/hardware/v22/design/${encodeURIComponent(projectId)}`, fetcher, "DESIGN_NOT_FOUND", "DESIGN_REJECTED");
}

export function fetchHardwareReview(projectId: string, fetcher: typeof fetch = fetch): Promise<HardwareReviewProposal[]> {
  if (!projectPattern.test(projectId)) throw new HardwareRequestError("REVIEW_UNAVAILABLE");
  return request(`/api/hardware/v22/review/${encodeURIComponent(projectId)}`, fetcher, "REVIEW_UNAVAILABLE", "REVIEW_UNAVAILABLE");
}
