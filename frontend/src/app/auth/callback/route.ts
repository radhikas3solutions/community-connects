import { NextResponse, type NextRequest } from "next/server";
import { safeNext } from "@/lib/safe-next";
import { requestOrigin } from "@/lib/request-origin";
import { createClient } from "@/lib/supabase/server";

/** OAuth / magic-link landing: exchange the PKCE code for a session cookie. */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const origin = requestOrigin(request);
  const code = searchParams.get("code");
  const next = safeNext(searchParams.get("next"));

  const supabase = await createClient();
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(new URL(next, origin));
    console.error("[auth/callback] code exchange failed:", error.code ?? "", error.message);
  } else {
    console.error("[auth/callback] no code in callback URL:", searchParams.toString());
  }

  // A used/expired link opened again (double click, mail-app prefetch) by someone who is
  // already signed in in this browser: don't show an error, just continue.
  const { data } = await supabase.auth.getUser();
  if (data.user) return NextResponse.redirect(new URL(next, origin));

  return NextResponse.redirect(new URL(`/login?error=callback&next=${encodeURIComponent(next)}`, origin));
}
