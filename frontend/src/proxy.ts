import type { NextRequest } from "next/server";
import { LANG_OVERRIDE_HEADER } from "@/i18n/constants";
import { updateSession } from "@/lib/supabase/proxy";

export async function proxy(request: NextRequest) {
  // `?lang=te` (used in shared links) shows that page in Telugu without changing the
  // visitor's saved preference. getLang() reads this header before the cookie.
  const lang = request.nextUrl.searchParams.get("lang");
  if (lang === "en" || lang === "te") request.headers.set(LANG_OVERRIDE_HEADER, lang);
  else request.headers.delete(LANG_OVERRIDE_HEADER);
  return updateSession(request);
}

export const config = {
  matcher: [
    // Everything except static assets and image optimisation files.
    "/((?!_next/static|_next/image|favicon.ico|robots.txt|.*\\.(?:svg|png|jpg|jpeg|gif|webp|avif)$).*)",
  ],
};
