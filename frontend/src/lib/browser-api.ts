import { PUBLIC_API_URL } from "@/lib/env";
import { createClient } from "@/lib/supabase/client";
import type { ApiErrorDetail } from "@/lib/types";

export class BrowserApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

/** Calls the API from the browser with the signed-in user's access token. */
export async function browserApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await createClient().auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new BrowserApiError(401, "signed_out", "Not signed in");

  const isForm = init.body instanceof FormData;
  const res = await fetch(`${PUBLIC_API_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      // FormData sets its own multipart boundary; never override it.
      ...(init.body && !isForm ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${token}`,
      ...init.headers,
    },
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: ApiErrorDetail };
    const detail = body.detail;
    if (detail && typeof detail === "object" && "code" in detail) {
      throw new BrowserApiError(res.status, detail.code, detail.message);
    }
    const message = typeof detail === "string" ? detail : res.statusText;
    throw new BrowserApiError(res.status, res.status === 429 ? "rate_limited" : "error", message);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
