import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { SUPABASE_ANON_KEY, SUPABASE_URL, isAuthConfigured } from "@/lib/env";

/** Supabase client for Server Components, Server Actions and Route Handlers. */
export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options),
          );
        } catch {
          // Called from a Server Component: cookies are read-only there.
          // The proxy refreshes the session, so this is safe to ignore.
        }
      },
    },
  });
}

export type SessionInfo = {
  userId: string;
  email: string | null;
  accessToken: string;
};

/**
 * Returns the verified session (claims checked against Supabase's signing keys),
 * or null when signed out / auth is not configured.
 */
export async function getSession(): Promise<SessionInfo | null> {
  if (!isAuthConfigured()) return null;
  const supabase = await createClient();
  const { data: claimsData, error } = await supabase.auth.getClaims();
  if (error || !claimsData?.claims?.sub) return null;
  const { data } = await supabase.auth.getSession();
  if (!data.session) return null;
  return {
    userId: claimsData.claims.sub,
    email: (claimsData.claims.email as string | undefined) ?? null,
    accessToken: data.session.access_token,
  };
}
