export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/** Browser-reachable API base URL. */
export const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
/** Server-side API base URL (docker network name in compose). */
export const SERVER_API_URL = process.env.API_INTERNAL_URL ?? PUBLIC_API_URL;

/** Lets the UI run (e.g. in CI / e2e) before a Supabase project is configured. */
export const isAuthConfigured = () =>
  Boolean(SUPABASE_URL && SUPABASE_ANON_KEY && !SUPABASE_URL.includes("YOUR-PROJECT"));
