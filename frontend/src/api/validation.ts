import type { ValidationSnapshot } from "../types/validation";
export type ValidationApiError = "VALIDATION_PROJECT_NOT_FOUND" | "VALIDATION_SNAPSHOT_REJECTED" | "VALIDATION_UNAVAILABLE";
export class ValidationRequestError extends Error { readonly code: ValidationApiError; constructor(code: ValidationApiError) { super(code); this.code = code; } }
export async function fetchValidationLoop(projectId: string, fetcher: typeof fetch = fetch): Promise<ValidationSnapshot> {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(projectId)) throw new ValidationRequestError("VALIDATION_SNAPSHOT_REJECTED");
  let response: Response; try { response = await fetcher(`/api/validation/loop/${encodeURIComponent(projectId)}`); } catch { throw new ValidationRequestError("VALIDATION_UNAVAILABLE"); }
  if (response.ok) { try { return (await response.json()) as ValidationSnapshot; } catch { throw new ValidationRequestError("VALIDATION_SNAPSHOT_REJECTED"); } }
  throw new ValidationRequestError(response.status === 404 ? "VALIDATION_PROJECT_NOT_FOUND" : response.status === 422 ? "VALIDATION_SNAPSHOT_REJECTED" : "VALIDATION_UNAVAILABLE");
}
