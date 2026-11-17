import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getMe } from "@/lib/api";
import { getSession } from "@/lib/supabase/server";
import type { Profile } from "@/lib/types";

export const metadata: Metadata = { title: "My account" };

export default async function AccountPage() {
  const session = await getSession();
  if (!session) redirect("/login?next=/account");
  const { lang, t } = await getDictionary();

  let profile: Profile | null = null;
  try {
    // First call provisions the profile row in our database.
    profile = await getMe(session.accessToken);
  } catch (err) {
    console.error("[account] /me failed", err);
  }

  return (
    <Container className="max-w-2xl py-10">
      <h1 className="mb-6 text-3xl font-bold">{t.account.title}</h1>
      <div className="rounded-[var(--radius-card)] border border-line bg-surface p-6">
        {profile ? (
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
            <dt className="text-muted">Email</dt>
            <dd>{profile.email ?? session.email}</dd>
            <dt className="text-muted">{t.account.language}</dt>
            <dd>{profile.preferred_language === "te" ? "తెలుగు" : "English"}</dd>
            <dt className="text-muted">{t.account.role}</dt>
            <dd className="capitalize">{profile.role}</dd>
            <dt className="text-muted">{t.account.memberSince}</dt>
            <dd>{new Date(profile.created_at).toLocaleDateString(lang === "te" ? "te-IN" : "en-US")}</dd>
          </dl>
        ) : (
          <p role="alert" className="text-sm">
            {t.account.apiDown}
          </p>
        )}
        <form action="/auth/signout" method="post" className="mt-6">
          <Button type="submit" variant="secondary" size="sm">
            {t.nav.signOut}
          </Button>
        </form>
      </div>
    </Container>
  );
}
