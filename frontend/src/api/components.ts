import type { ComponentRecommendation } from "../types/components";
export type ComponentApiError = "COMPONENT_PROJECT_NOT_FOUND" | "COMPONENT_RECOMMENDATION_REJECTED" | "COMPONENT_UNAVAILABLE";
export class ComponentRequestError extends Error {
  readonly code: ComponentApiError;
  constructor(code: ComponentApiError) { super(code); this.name = "ComponentRequestError"; this.code = code; }
}
export async function fetchComponents(projectId: string, fetcher: typeof fetch = fetch): Promise<ComponentRecommendation[]> {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(projectId)) throw new ComponentRequestError("COMPONENT_RECOMMENDATION_REJECTED");
  let response: Response;
  try { response = await fetcher(`/api/components/${encodeURIComponent(projectId)}`); } catch { throw new ComponentRequestError("COMPONENT_UNAVAILABLE"); }
  if (response.ok) { try { const value = (await response.json()) as ComponentRecommendation[]; if (!Array.isArray(value)) throw new Error("invalid"); return value; } catch { throw new ComponentRequestError("COMPONENT_RECOMMENDATION_REJECTED"); } }
  throw new ComponentRequestError(response.status === 404 ? "COMPONENT_PROJECT_NOT_FOUND" : response.status === 422 ? "COMPONENT_RECOMMENDATION_REJECTED" : "COMPONENT_UNAVAILABLE");
}
