import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { isAuthConfigured } from "@/lib/env";
import { getSession } from "@/lib/supabase/server";
import { safeNext } from "@/lib/safe-next";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  const { next, error } = await searchParams;
  const nextPath = safeNext(next);
  if (await getSession()) redirect(nextPath);
  const { lang, t } = await getDictionary();

  return (
    <Container className="max-w-md py-16">
      <div className="rounded-[var(--radius-card)] border border-line bg-surface p-8 shadow-sm">
        <h1 className="text-2xl font-bold" lang={lang}>
          {t.auth.title}
        </h1>
        <p className="mt-2 text-muted" lang={lang}>
          {t.auth.subtitle}
        </p>
        {error && (
          <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {t.auth.error}
          </p>
        )}
        {isAuthConfigured() ? (
          <LoginForm t={t.auth} next={nextPath} />
        ) : (
          <p role="status" className="mt-6 rounded-lg bg-accent-100 p-3 text-sm">
            {t.auth.notConfigured}
          </p>
        )}
      </div>
    </Container>
  );
}
