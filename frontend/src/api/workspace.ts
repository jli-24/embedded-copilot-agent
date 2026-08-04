import type { WorkspaceSnapshot } from "../types/workspace";

export type WorkspaceApiError = "WORKSPACE_PROJECT_NOT_FOUND" | "WORKSPACE_SNAPSHOT_REJECTED" | "WORKSPACE_UNAVAILABLE";
export class WorkspaceRequestError extends Error {
  readonly code: WorkspaceApiError;
  constructor(code: WorkspaceApiError) { super(code); this.name = "WorkspaceRequestError"; this.code = code; }
}
export async function fetchWorkspace(projectId: string, fetcher: typeof fetch = fetch): Promise<WorkspaceSnapshot> {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(projectId)) throw new WorkspaceRequestError("WORKSPACE_SNAPSHOT_REJECTED");
  let response: Response;
  try { response = await fetcher(`/api/workspace/${encodeURIComponent(projectId)}`); } catch { throw new WorkspaceRequestError("WORKSPACE_UNAVAILABLE"); }
  if (response.ok) { try { return (await response.json()) as WorkspaceSnapshot; } catch { throw new WorkspaceRequestError("WORKSPACE_SNAPSHOT_REJECTED"); } }
  throw new WorkspaceRequestError(response.status === 404 ? "WORKSPACE_PROJECT_NOT_FOUND" : response.status === 422 ? "WORKSPACE_SNAPSHOT_REJECTED" : "WORKSPACE_UNAVAILABLE");
}
