import type { OptimizationAnalysis, OptimizationFinding } from "../types/optimizationV26";

export type OptimizationV26ApiError = "OPTIMIZATION_UNAVAILABLE" | "DIGITAL_TWIN_NOT_FOUND" | "FINDING_NOT_FOUND" | "APPROVAL_REQUIRED" | "OPTIMIZATION_REJECTED";
export class OptimizationV26RequestError extends Error { readonly code: OptimizationV26ApiError; constructor(code: OptimizationV26ApiError) { super(code); this.name = "OptimizationV26RequestError"; this.code = code; } }
const projectPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/;
const findingPattern = /^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$/;

async function responseValue<T>(response: Response, notFound: OptimizationV26ApiError): Promise<T> {
  if (response.ok) { try { return await response.json() as T; } catch { throw new OptimizationV26RequestError("OPTIMIZATION_REJECTED"); } }
  throw new OptimizationV26RequestError(response.status === 404 ? notFound : response.status === 422 ? "OPTIMIZATION_REJECTED" : "OPTIMIZATION_UNAVAILABLE");
}

export async function fetchOptimizationAnalysis(projectId: string, fetcher: typeof fetch = fetch): Promise<OptimizationAnalysis> {
  if (!projectPattern.test(projectId)) throw new OptimizationV26RequestError("OPTIMIZATION_REJECTED");
  let response: Response;
  try { response = await fetcher(`/api/optimization/v26/${encodeURIComponent(projectId)}`); } catch { throw new OptimizationV26RequestError("OPTIMIZATION_UNAVAILABLE"); }
  return responseValue<OptimizationAnalysis>(response, "DIGITAL_TWIN_NOT_FOUND");
}

type Decision = { finding_id: string; finding_fingerprint: string; reviewer: string; decided_at: string };
async function decide(finding: OptimizationFinding, action: "approve" | "reject", fetcher: typeof fetch): Promise<OptimizationFinding> {
  if (!findingPattern.test(finding.finding_id)) throw new OptimizationV26RequestError("OPTIMIZATION_REJECTED");
  const body: Decision = { finding_id: finding.finding_id, finding_fingerprint: finding.fingerprint, reviewer: "web-reviewer", decided_at: new Date().toISOString() };
  let response: Response;
  try { response = await fetcher(`/api/optimization/v26/${encodeURIComponent(finding.finding_id)}/${action}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }); } catch { throw new OptimizationV26RequestError("OPTIMIZATION_UNAVAILABLE"); }
  return responseValue<OptimizationFinding>(response, "FINDING_NOT_FOUND");
}
export function approveOptimizationFinding(finding: OptimizationFinding, fetcher: typeof fetch = fetch) { return decide(finding, "approve", fetcher); }
export function rejectOptimizationFinding(finding: OptimizationFinding, fetcher: typeof fetch = fetch) { return decide(finding, "reject", fetcher); }
