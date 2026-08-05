import type { DebugAnalysisSnapshot } from "../types/debug";

export type DebugApiError = "DEBUG_UNAVAILABLE" | "DEBUG_NOT_FOUND" | "DEBUG_REJECTED";
export class DebugRequestError extends Error { readonly code: DebugApiError; constructor(code: DebugApiError) { super(code); this.name = "DebugRequestError"; this.code = code; } }
const projectPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/;

export async function fetchDebugAnalysis(projectId: string, fetcher: typeof fetch = fetch): Promise<DebugAnalysisSnapshot> {
  if (!projectPattern.test(projectId)) throw new DebugRequestError("DEBUG_REJECTED");
  let response: Response;
  try { response = await fetcher(`/api/debug/v23/${encodeURIComponent(projectId)}`); } catch { throw new DebugRequestError("DEBUG_UNAVAILABLE"); }
  if (response.ok) { try { return await response.json() as DebugAnalysisSnapshot; } catch { throw new DebugRequestError("DEBUG_REJECTED"); } }
  throw new DebugRequestError(response.status === 404 ? "DEBUG_NOT_FOUND" : response.status === 422 ? "DEBUG_REJECTED" : "DEBUG_UNAVAILABLE");
}
