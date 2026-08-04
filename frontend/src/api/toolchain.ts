import type { ToolchainSnapshot } from "../types/toolchain";
export type ToolchainApiError = "TOOLCHAIN_PROJECT_NOT_FOUND" | "TOOLCHAIN_SNAPSHOT_REJECTED" | "TOOLCHAIN_UNAVAILABLE";
export class ToolchainRequestError extends Error {
  readonly code: ToolchainApiError;
  constructor(code: ToolchainApiError) { super(code); this.name = "ToolchainRequestError"; this.code = code; }
}
export async function fetchToolchain(projectId: string, fetcher: typeof fetch = fetch): Promise<ToolchainSnapshot> {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(projectId)) throw new ToolchainRequestError("TOOLCHAIN_SNAPSHOT_REJECTED");
  let response: Response;
  try { response = await fetcher(`/api/toolchain/${encodeURIComponent(projectId)}`); } catch { throw new ToolchainRequestError("TOOLCHAIN_UNAVAILABLE"); }
  if (response.ok) { try { return (await response.json()) as ToolchainSnapshot; } catch { throw new ToolchainRequestError("TOOLCHAIN_SNAPSHOT_REJECTED"); } }
  throw new ToolchainRequestError(response.status === 404 ? "TOOLCHAIN_PROJECT_NOT_FOUND" : response.status === 422 ? "TOOLCHAIN_SNAPSHOT_REJECTED" : "TOOLCHAIN_UNAVAILABLE");
}
