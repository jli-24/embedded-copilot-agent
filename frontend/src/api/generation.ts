import type { GenerationSnapshot } from "../types/generation";

export type GenerationApiError =
  | "GENERATION_PROJECT_NOT_FOUND"
  | "GENERATION_SNAPSHOT_REJECTED"
  | "GENERATION_UNAVAILABLE";

export class GenerationRequestError extends Error {
  readonly code: GenerationApiError;
  constructor(code: GenerationApiError) {
    super(code);
    this.name = "GenerationRequestError";
    this.code = code;
  }
}

export async function fetchGeneration(
  projectId: string,
  fetcher: typeof fetch = fetch,
): Promise<GenerationSnapshot> {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(projectId)) {
    throw new GenerationRequestError("GENERATION_SNAPSHOT_REJECTED");
  }
  let response: Response;
  try {
    response = await fetcher(`/api/generation/${encodeURIComponent(projectId)}`);
  } catch {
    throw new GenerationRequestError("GENERATION_UNAVAILABLE");
  }
  if (response.ok) {
    try {
      return (await response.json()) as GenerationSnapshot;
    } catch {
      throw new GenerationRequestError("GENERATION_SNAPSHOT_REJECTED");
    }
  }
  const code: GenerationApiError = response.status === 404
    ? "GENERATION_PROJECT_NOT_FOUND"
    : response.status === 422
      ? "GENERATION_SNAPSHOT_REJECTED"
      : "GENERATION_UNAVAILABLE";
  throw new GenerationRequestError(code);
}
