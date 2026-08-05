import type { OptimizationProposal } from "../types/optimization";

export type OptimizationApiError = "OPTIMIZATION_UNAVAILABLE" | "PROPOSAL_NOT_FOUND" | "PROPOSAL_REJECTED" | "APPROVAL_REQUIRED";
export class OptimizationRequestError extends Error { readonly code: OptimizationApiError; constructor(code: OptimizationApiError) { super(code); this.name = "OptimizationRequestError"; this.code = code; } }
const projectPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/;
const proposalPattern = /^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$/;

async function request<T>(path: string, fetcher: typeof fetch, response: Response, notFound: OptimizationApiError): Promise<T> {
  if (response.ok) { try { return await response.json() as T; } catch { throw new OptimizationRequestError("PROPOSAL_REJECTED"); } }
  throw new OptimizationRequestError(response.status === 404 ? notFound : response.status === 422 ? "PROPOSAL_REJECTED" : "OPTIMIZATION_UNAVAILABLE");
}

export async function fetchOptimization(projectId: string, fetcher: typeof fetch = fetch): Promise<OptimizationProposal> {
  if (!projectPattern.test(projectId)) throw new OptimizationRequestError("PROPOSAL_REJECTED");
  let response: Response;
  try { response = await fetcher(`/api/optimization/v23/${encodeURIComponent(projectId)}`); } catch { throw new OptimizationRequestError("OPTIMIZATION_UNAVAILABLE"); }
  return request("", fetcher, response, "PROPOSAL_NOT_FOUND");
}

type Decision = { proposal_id: string; proposal_fingerprint: string; reviewer: string; decided_at: string };
async function decide(proposal: OptimizationProposal, action: "approve" | "reject", fetcher: typeof fetch): Promise<OptimizationProposal> {
  if (!proposalPattern.test(proposal.proposal_id)) throw new OptimizationRequestError("PROPOSAL_REJECTED");
  let response: Response;
  const body: Decision = { proposal_id: proposal.proposal_id, proposal_fingerprint: proposal.fingerprint, reviewer: "web-reviewer", decided_at: new Date().toISOString() };
  try { response = await fetcher(`/api/optimization/v23/${encodeURIComponent(proposal.proposal_id)}/${action}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }); } catch { throw new OptimizationRequestError("OPTIMIZATION_UNAVAILABLE"); }
  return request("", fetcher, response, "PROPOSAL_NOT_FOUND");
}
export function approveOptimization(proposal: OptimizationProposal, fetcher: typeof fetch = fetch) { return decide(proposal, "approve", fetcher); }
export function rejectOptimization(proposal: OptimizationProposal, fetcher: typeof fetch = fetch) { return decide(proposal, "reject", fetcher); }
