import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { SUPABASE_ANON_KEY, SUPABASE_URL, isAuthConfigured } from "@/lib/env";
import { getSession } from "@/lib/supabase/server";
import { safeNext } from "@/lib/safe-next";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = { title: "Sign in" };

// Codes Supabase uses for a link that expired or was already used.
const EXPIRED = new Set(["otp_expired", "flow_state_expired", "access_denied"]);
// PKCE: the link was opened in a different browser from the one that asked for it.
const OTHER_BROWSER = new Set(["bad_code_verifier", "flow_state_not_found", "code_error"]);

/** Whether Google sign-in is switched on in Supabase (hide the button otherwise). */
async function googleEnabled(): Promise<boolean> {
  try {
    const res = await fetch(`${SUPABASE_URL}/auth/v1/settings`, {
      headers: { apikey: SUPABASE_ANON_KEY },
      next: { revalidate: 300 },
    });
    if (!res.ok) return false;
    const settings = (await res.json()) as { external?: Record<string, boolean> };
    return Boolean(settings.external?.google);
  } catch {
    return false;
  }
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  const { next, error } = await searchParams;
  const nextPath = safeNext(next);
  if (await getSession()) redirect(nextPath);
  const [{ lang, t }, google] = await Promise.all([
    getDictionary(),
    isAuthConfigured() ? googleEnabled() : Promise.resolve(false),
  ]);
  const message = !error
    ? null
    : EXPIRED.has(error)
      ? t.auth.linkExpired
      : OTHER_BROWSER.has(error)
        ? t.auth.otherBrowser
        : t.auth.error;

  return (
    <Container className="max-w-md py-16">
      <div className="rounded-[var(--radius-card)] border border-line bg-surface p-8 shadow-sm">
        <h1 className="text-2xl font-bold" lang={lang}>
          {t.auth.title}
        </h1>
        <p className="mt-2 text-muted" lang={lang}>
          {t.auth.subtitle}
        </p>
        {message && (
          <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {message} <span className="text-xs text-red-500">({error})</span>
          </p>
        )}
        {isAuthConfigured() ? (
          <LoginForm t={t.auth} next={nextPath} google={google} />
        ) : (
          <p role="status" className="mt-6 rounded-lg bg-accent-100 p-3 text-sm">
            {t.auth.notConfigured}
          </p>
        )}
      </div>
    </Container>
  );
}
