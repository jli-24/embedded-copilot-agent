import type { ModelRuntimeStatus } from "../types/runtime";

export type RuntimeApiError = "MODEL_UNAVAILABLE" | "MODEL_STATUS_REJECTED";

export class RuntimeRequestError extends Error {
  readonly code: RuntimeApiError;
  constructor(code: RuntimeApiError) {
    super(code);
    this.name = "RuntimeRequestError";
    this.code = code;
  }
}

export async function fetchRuntimeStatus(fetcher: typeof fetch = fetch): Promise<ModelRuntimeStatus> {
  let response: Response;
  try {
    response = await fetcher("/api/v1/copilot/models/status");
  } catch {
    throw new RuntimeRequestError("MODEL_UNAVAILABLE");
  }
  if (!response.ok) throw new RuntimeRequestError("MODEL_UNAVAILABLE");
  try {
    const value = (await response.json()) as ModelRuntimeStatus;
    if (typeof value.provider !== "string" || typeof value.status !== "string" || !Array.isArray(value.capabilities)) {
      throw new Error("invalid");
    }
    return value;
  } catch {
    throw new RuntimeRequestError("MODEL_STATUS_REJECTED");
  }
}
