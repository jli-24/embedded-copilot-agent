import type { ObservationSnapshot, ToolCapabilitySnapshot, ToolExecutionResult } from "../types/toolAdapter";

export type ToolAdapterApiError =
  | "TOOL_STATUS_NOT_FOUND"
  | "TOOL_STATUS_REJECTED"
  | "TOOL_UNAVAILABLE"
  | "TOOL_EXECUTION_REJECTED"
  | "TOOL_EXECUTION_FAILED"
  | "BUILD_APPROVAL_REQUIRED"
  | "FLASH_APPROVAL_REQUIRED"
  | "FLASH_UNAVAILABLE"
  | "FLASH_FAILED"
  | "OBSERVATION_NOT_FOUND"
  | "OBSERVATION_REJECTED"
  | "OBSERVATION_UNAVAILABLE";

export class ToolAdapterRequestError extends Error {
  readonly code: ToolAdapterApiError;
  constructor(code: ToolAdapterApiError) { super(code); this.name = "ToolAdapterRequestError"; this.code = code; }
}

const projectPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/;

async function get<T>(path: string, fetcher: typeof fetch, notFound: ToolAdapterApiError, rejected: ToolAdapterApiError): Promise<T> {
  let response: Response;
  try { response = await fetcher(path); } catch { throw new ToolAdapterRequestError("TOOL_UNAVAILABLE"); }
  if (response.ok) {
    try { return (await response.json()) as T; } catch { throw new ToolAdapterRequestError(rejected); }
  }
  throw new ToolAdapterRequestError(response.status === 404 ? notFound : response.status === 422 ? rejected : "TOOL_UNAVAILABLE");
}

export function fetchToolCapability(projectId: string, fetcher: typeof fetch = fetch): Promise<ToolCapabilitySnapshot> {
  if (!projectPattern.test(projectId)) throw new ToolAdapterRequestError("TOOL_STATUS_REJECTED");
  return get(`/api/toolchain/v21/status/${encodeURIComponent(projectId)}`, fetcher, "TOOL_STATUS_NOT_FOUND", "TOOL_STATUS_REJECTED");
}

export function fetchToolDevice(projectId: string, fetcher: typeof fetch = fetch): Promise<ObservationSnapshot> {
  if (!projectPattern.test(projectId)) throw new ToolAdapterRequestError("OBSERVATION_REJECTED");
  return get(`/api/toolchain/v21/device/${encodeURIComponent(projectId)}`, fetcher, "OBSERVATION_NOT_FOUND", "OBSERVATION_REJECTED");
}

type BuildRequest = { artifact_reference: string; workspace_reference: string; approval_reference?: string };
type FlashRequest = { firmware_reference: string; device_reference: string; approval_reference?: string };

async function post<T>(path: string, body: unknown, fetcher: typeof fetch): Promise<T> {
  let response: Response;
  try { response = await fetcher(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }); } catch { throw new ToolAdapterRequestError("TOOL_UNAVAILABLE"); }
  if (response.ok) { try { return (await response.json()) as T; } catch { throw new ToolAdapterRequestError("TOOL_EXECUTION_REJECTED"); } }
  if (response.status === 422 || response.status === 503) {
    try {
      const payload = (await response.json()) as { error?: string };
      const code = payload.error as ToolAdapterApiError | undefined;
      if (code) throw new ToolAdapterRequestError(code);
    } catch (error) {
      if (error instanceof ToolAdapterRequestError) throw error;
    }
  }
  throw new ToolAdapterRequestError(response.status === 422 ? "TOOL_EXECUTION_REJECTED" : "TOOL_UNAVAILABLE");
}

export function requestBuild(body: BuildRequest, fetcher: typeof fetch = fetch): Promise<ToolExecutionResult> {
  return post("/api/toolchain/v21/build", body, fetcher);
}

export function requestFlash(body: FlashRequest, fetcher: typeof fetch = fetch): Promise<ToolExecutionResult> {
  return post("/api/toolchain/v21/flash", body, fetcher);
}
