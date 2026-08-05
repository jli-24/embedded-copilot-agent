import type { FirmwareBuildResult, FirmwareProjectSnapshot } from "../types/firmware";
import type { DebugAnalysisSnapshot } from "../types/debug";

export type FirmwareApiError = "FIRMWARE_UNAVAILABLE" | "BUILD_APPROVAL_REQUIRED" | "BUILD_UNAVAILABLE" | "BUILD_FAILED" | "FIRMWARE_NOT_FOUND" | "FIRMWARE_REJECTED";
export class FirmwareRequestError extends Error { readonly code: FirmwareApiError; constructor(code: FirmwareApiError) { super(code); this.name = "FirmwareRequestError"; this.code = code; } }
const projectPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/;

async function get<T>(path: string, fetcher: typeof fetch, notFound: FirmwareApiError, rejected: FirmwareApiError): Promise<T> {
  let response: Response;
  try { response = await fetcher(path); } catch { throw new FirmwareRequestError("FIRMWARE_UNAVAILABLE"); }
  if (response.ok) { try { return await response.json() as T; } catch { throw new FirmwareRequestError(rejected); } }
  throw new FirmwareRequestError(response.status === 404 ? notFound : response.status === 422 ? rejected : "FIRMWARE_UNAVAILABLE");
}

export function fetchFirmware(projectId: string, fetcher: typeof fetch = fetch): Promise<FirmwareProjectSnapshot> {
  if (!projectPattern.test(projectId)) throw new FirmwareRequestError("FIRMWARE_REJECTED");
  return get(`/api/firmware/v24/${encodeURIComponent(projectId)}`, fetcher, "FIRMWARE_NOT_FOUND", "FIRMWARE_REJECTED");
}

export function fetchFirmwareBuild(projectId: string, fetcher: typeof fetch = fetch): Promise<FirmwareBuildResult> {
  if (!projectPattern.test(projectId)) throw new FirmwareRequestError("FIRMWARE_REJECTED");
  return get(`/api/firmware/v24/build/${encodeURIComponent(projectId)}`, fetcher, "FIRMWARE_NOT_FOUND", "FIRMWARE_REJECTED");
}

export function fetchFirmwareDebug(projectId: string, fetcher: typeof fetch = fetch): Promise<DebugAnalysisSnapshot> {
  if (!projectPattern.test(projectId)) throw new FirmwareRequestError("FIRMWARE_REJECTED");
  return get(`/api/firmware/v24/debug/${encodeURIComponent(projectId)}`, fetcher, "FIRMWARE_NOT_FOUND", "FIRMWARE_REJECTED");
}
