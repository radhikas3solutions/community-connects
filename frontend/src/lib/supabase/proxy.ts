import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { SUPABASE_ANON_KEY, SUPABASE_URL, isAuthConfigured } from "@/lib/env";
import { requestOrigin } from "@/lib/request-origin";

/** Paths that require a signed-in user (optimistic check; the API enforces auth). */
const PROTECTED_PREFIXES = ["/account", "/sell", "/admin"];

/**
 * Refreshes the Supabase session cookie on every navigation and redirects
 * signed-out users away from protected pages.
 */
export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });
  if (!isAuthConfigured()) return response;

  const supabase = createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headers) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
        // Cache-control headers that stop CDNs caching auth responses.
        Object.entries(headers ?? {}).forEach(([k, v]) => response.headers.set(k, v));
      },
    },
  });

  // Do not run code between createServerClient and getClaims(): it triggers the refresh.
  const { data } = await supabase.auth.getClaims();
  const signedIn = Boolean(data?.claims?.sub);

  const { pathname } = request.nextUrl;
  if (!signedIn && PROTECTED_PREFIXES.some((p) => pathname.startsWith(p))) {
    const url = new URL(`/login?next=${encodeURIComponent(pathname)}`, requestOrigin(request));
    return NextResponse.redirect(url);
  }
  return response;
}
