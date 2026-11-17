import "server-only";

import { SERVER_API_URL } from "@/lib/env";
import type { Category, CategoryKind, Listing, Page, Profile } from "@/lib/types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type FetchOpts = RequestInit & { token?: string; revalidate?: number };

export async function apiFetch<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const { token, revalidate, headers, ...init } = opts;
  const res = await fetch(`${SERVER_API_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    // Authenticated responses are per-user: never cache them.
    ...(token ? { cache: "no-store" as const } : { next: { revalidate: revalidate ?? 60 } }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new ApiError(res.status, detail?.detail ?? res.statusText);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

/** Never let a public page crash because the API is down; render an empty state instead. */
async function safe<T>(p: Promise<T>, fallback: T): Promise<{ data: T; ok: boolean }> {
  try {
    return { data: await p, ok: true };
  } catch (err) {
    console.error("[api]", err);
    return { data: fallback, ok: false };
  }
}

export const getCategories = (kind?: CategoryKind) =>
  safe(
    apiFetch<Category[]>(`/api/v1/categories${kind ? `?kind=${kind}` : ""}`, { revalidate: 300 }),
    [] as Category[],
  );

export const searchListings = (params: Record<string, string | undefined>) => {
  const qs = new URLSearchParams(
    Object.entries(params).filter((e): e is [string, string] => Boolean(e[1])),
  );
  return safe(
    apiFetch<Page<Listing>>(`/api/v1/listings?${qs}`, { revalidate: 30 }),
    { items: [], total: 0, limit: 24, offset: 0 } as Page<Listing>,
  );
};

export const getMe = (token: string) => apiFetch<Profile>("/api/v1/me", { token });
