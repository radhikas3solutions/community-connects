import type { EmailOtpType } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";
import { safeNext } from "@/lib/safe-next";
import { requestOrigin } from "@/lib/request-origin";
import { createClient } from "@/lib/supabase/server";

const EMAIL_TYPES = new Set<EmailOtpType>(["email", "magiclink", "signup", "invite", "recovery", "email_change"]);

/**
 * Sign-in landing for Google (PKCE `code`) and email links.
 *
 * Email links carry `token_hash` + `type` (see docs/DEPLOY.md, email templates): they work in any
 * browser or device, unlike PKCE codes, which only work in the browser that asked for the link
 * (so a link opened from the Gmail app, or on the phone, would fail).
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const origin = requestOrigin(request);
  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const next = safeNext(searchParams.get("next"));

  const supabase = await createClient();
  if (tokenHash && type && EMAIL_TYPES.has(type)) {
    const { error } = await supabase.auth.verifyOtp({ token_hash: tokenHash, type });
    if (!error) return NextResponse.redirect(new URL(next, origin));
    console.error("[auth/callback] email link failed:", error.code ?? "", error.message);
  } else if (code) {
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
