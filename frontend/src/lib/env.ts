export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
// Production fallback: the askmitra.ai project's publishable key. It is public by design (it ships
// in the browser bundle and only allows what Row Level Security allows), so keeping it here is safe
// and stops a missing Vercel variable from breaking sign-in. Local dev uses its own key from .env.
const PRODUCTION_SUPABASE_URL = "https://upyttsplupzciohhgatl.supabase.co";
const PRODUCTION_PUBLISHABLE_KEY = "sb_publishable_-4NDA85dBcC0lrKPx5GOyw_EnJmUEUH";

export const SUPABASE_ANON_KEY =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  (SUPABASE_URL === PRODUCTION_SUPABASE_URL ? PRODUCTION_PUBLISHABLE_KEY : "");
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/** Browser-reachable API base URL. */
export const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
/** Server-side API base URL (docker network name in compose). */
export const SERVER_API_URL = process.env.API_INTERNAL_URL ?? PUBLIC_API_URL;

/** Lets the UI run (e.g. in CI / e2e) before a Supabase project is configured. */
export const isAuthConfigured = () =>
  Boolean(SUPABASE_URL && SUPABASE_ANON_KEY && !SUPABASE_URL.includes("YOUR-PROJECT"));
