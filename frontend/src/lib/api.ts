import "server-only";

import { SERVER_API_URL } from "@/lib/env";
import type { AdminProfile, Business, Category, CategoryKind, Listing, Page, Profile } from "@/lib/types";

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
    // Authenticated responses are per-user: never cache them. An explicit `cache` wins.
    ...(token || init.cache
      ? { cache: init.cache ?? ("no-store" as const) }
      : { next: { revalidate: revalidate ?? 60 } }),
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
  safe(apiFetch<Category[]>(`/api/v1/categories${kind ? `?kind=${kind}` : ""}`, { revalidate: 300 }), [] as Category[]);

export const searchListings = (params: Record<string, string | undefined>) => {
  const qs = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => Boolean(e[1])));
  return safe(apiFetch<Page<Listing>>(`/api/v1/listings?${qs}`, { revalidate: 30 }), {
    items: [],
    total: 0,
    limit: 24,
    offset: 0,
  } as Page<Listing>);
};

export const getMe = (token: string) => apiFetch<Profile>("/api/v1/me", { token });

/**
 * A single listing. Pass the viewer's token to see their own drafts.
 * Returns `null` when it doesn't exist (or isn't visible); throws when the API is down.
 */
export async function getListing(id: string, token?: string): Promise<Listing | null> {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  try {
    return await apiFetch<Listing>(`/api/v1/listings/${id}`, { token, revalidate: 30 });
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 422)) return null;
    throw err;
  }
}

export const getMyListings = (token: string) => apiFetch<Listing[]>("/api/v1/listings/mine", { token });

// ---------------------------------------------------------------- directory

/** Directory search. With a token, individuals' contact details are included. */
export const searchDirectory = (params: Record<string, string | undefined>, token?: string) => {
  const qs = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => Boolean(e[1])));
  return safe(apiFetch<Page<Business>>(`/api/v1/businesses?${qs}`, { token, revalidate: 60 }), {
    items: [],
    total: 0,
    limit: 24,
    offset: 0,
  } as Page<Business>);
};

/** One entry; `null` when it doesn't exist or isn't visible to this viewer. Throws when the API is down. */
export async function getBusiness(id: string, token?: string): Promise<Business | null> {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  try {
    // Not cached: a cached copy would outlive a removed entry (failed revalidation keeps it).
    return await apiFetch<Business>(`/api/v1/businesses/${id}`, { token, cache: "no-store" });
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 422)) return null;
    throw err;
  }
}

export const getMyEntries = (token: string) => apiFetch<Business[]>("/api/v1/businesses/mine", { token });
export const getAdminUsers = (token: string, q?: string) =>
  apiFetch<AdminProfile[]>(`/api/v1/admin/users?limit=200${q ? `&q=${encodeURIComponent(q)}` : ""}`, {
    token,
    cache: "no-store",
  });
export const getReviewQueue = (token: string) => apiFetch<Business[]>("/api/v1/businesses/review-queue", { token });
