export type FlashRequest = { firmware_reference: string; device_reference: string; approval_reference?: string | null; capability_reference?: string | null };
export type FlashResult = { status: string; firmware_reference: string; device_reference: string; summary: string; fingerprint: string };
export type FlashApiError = "FLASH_CAPABILITY_REQUIRED" | "FLASH_APPROVAL_REQUIRED" | "FLASH_FAILED" | "FLASH_UNAVAILABLE";
export class FlashRequestError extends Error { readonly code: FlashApiError; constructor(code: FlashApiError) { super(code); this.code = code; } }
export async function submitFlash(request: FlashRequest, fetcher: typeof fetch = fetch): Promise<FlashResult> {
  let response: Response; try { response = await fetcher("/api/validation/flash", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request) }); } catch { throw new FlashRequestError("FLASH_UNAVAILABLE"); }
  if (response.ok) { try { return (await response.json()) as FlashResult; } catch { throw new FlashRequestError("FLASH_FAILED"); } }
  let body: unknown = null; try { body = await response.json(); } catch { /* fixed fallback below */ }
  const returned = typeof body === "object" && body !== null && "error" in body ? (body as { error?: unknown }).error : null;
  const code: FlashApiError = returned === "FLASH_CAPABILITY_REQUIRED" || returned === "FLASH_APPROVAL_REQUIRED" || returned === "FLASH_FAILED" || returned === "FLASH_UNAVAILABLE"
    ? returned
    : response.status === 503 ? "FLASH_UNAVAILABLE" : "FLASH_FAILED";
  throw new FlashRequestError(code);
}
