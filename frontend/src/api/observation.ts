import type { ObservationSnapshot } from "../types/observation";
export type ObservationApiError = "OBSERVATION_NOT_FOUND" | "OBSERVATION_SNAPSHOT_REJECTED" | "OBSERVATION_UNAVAILABLE";
export class ObservationRequestError extends Error { readonly code: ObservationApiError; constructor(code: ObservationApiError) { super(code); this.code = code; } }
export async function fetchObservation(projectId: string, fetcher: typeof fetch = fetch): Promise<ObservationSnapshot> {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(projectId)) throw new ObservationRequestError("OBSERVATION_SNAPSHOT_REJECTED");
  let response: Response; try { response = await fetcher(`/api/validation/observation/${encodeURIComponent(projectId)}`); } catch { throw new ObservationRequestError("OBSERVATION_UNAVAILABLE"); }
  if (response.ok) { try { return (await response.json()) as ObservationSnapshot; } catch { throw new ObservationRequestError("OBSERVATION_SNAPSHOT_REJECTED"); } }
  throw new ObservationRequestError(response.status === 404 ? "OBSERVATION_NOT_FOUND" : response.status === 422 ? "OBSERVATION_SNAPSHOT_REJECTED" : "OBSERVATION_UNAVAILABLE");
}
