import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getMe, getMyEntries, getMyListings } from "@/lib/api";
import { businessName } from "@/lib/directory";
import { formatPrice, localized } from "@/lib/format";
import { getSession } from "@/lib/supabase/server";
import type { Business, Listing, Profile } from "@/lib/types";
import { ContactDetails } from "./ContactDetails";

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
  const [listings, entries]: [Listing[] | null, Business[] | null] = profile
    ? await Promise.all([
        getMyListings(session.accessToken).catch(() => null),
        getMyEntries(session.accessToken).catch(() => null),
      ])
    : [null, null];
  const isStaff = profile?.role === "moderator" || profile?.role === "admin";

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
        {profile && <ContactDetails profile={profile} t={t.account} countryLabel={t.auth.country} />}
        {profile?.role === "admin" && (
          <Link href="/admin/users" className="mt-6 inline-block text-sm font-semibold text-accent-600 hover:underline">
            👥 {t.account.manageUsers}
          </Link>
        )}
        <form action="/auth/signout" method="post" className="mt-6">
          <Button type="submit" variant="secondary" size="sm">
            {t.nav.signOut}
          </Button>
        </form>
      </div>

      {listings && (
        <section className="mt-10">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-2xl font-bold">{t.myListings.title}</h2>
            <Link href="/sell" className="text-sm font-semibold text-brand-700 hover:underline">
              📸 {t.nav.sell}
            </Link>
          </div>
          {listings.length === 0 ? (
            <p className="rounded-xl border border-dashed border-line p-6 text-center text-muted">
              {t.myListings.empty}
            </p>
          ) : (
            <ul className="divide-y divide-line rounded-[var(--radius-card)] border border-line bg-surface">
              {listings.map((l) => (
                <li key={l.id} className="flex items-center gap-3 p-3">
                  <span
                    className={`w-20 shrink-0 rounded-full px-2 py-0.5 text-center text-xs font-semibold ${
                      l.status === "active" ? "bg-brand-100 text-brand-700" : "bg-canvas text-muted"
                    }`}
                  >
                    {t.myListings.status[l.status]}
                  </span>
                  <Link
                    href={`/listings/${l.id}`}
                    className="min-w-0 flex-1 truncate font-medium hover:underline"
                    lang={lang}
                  >
                    {localized(l.title_en, l.title_te, lang)}
                  </Link>
                  <span className="hidden text-sm text-muted sm:inline">{formatPrice(l, lang)}</span>
                  <Link
                    href={`/listings/${l.id}/edit`}
                    className="text-sm font-semibold text-brand-700 hover:underline"
                  >
                    {t.myListings.edit}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {entries && (
        <section className="mt-10">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-2xl font-bold">{t.myEntries.title}</h2>
            <div className="flex gap-4 text-sm font-semibold">
              {isStaff && (
                <Link href="/admin/directory" className="text-accent-600 hover:underline">
                  🛡️ {t.myEntries.reviewQueue}
                </Link>
              )}
              {isStaff && (
                <Link href="/admin/directory/import" className="text-accent-600 hover:underline">
                  📋 {t.npiImport.link}
                </Link>
              )}
              <Link href="/directory/new" className="text-brand-700 hover:underline">
                ➕ {t.directory.add}
              </Link>
            </div>
          </div>
          {entries.length === 0 ? (
            <p className="rounded-xl border border-dashed border-line p-6 text-center text-muted">
              {t.myEntries.empty}
            </p>
          ) : (
            <ul className="divide-y divide-line rounded-[var(--radius-card)] border border-line bg-surface">
              {entries.map((b) => (
                <li key={b.id} className="flex items-center gap-3 p-3">
                  <span
                    className={`w-24 shrink-0 rounded-full px-2 py-0.5 text-center text-xs font-semibold ${
                      b.status === "active"
                        ? "bg-brand-100 text-brand-700"
                        : b.status === "rejected"
                          ? "bg-accent-100 text-accent-600"
                          : "bg-canvas text-muted"
                    }`}
                  >
                    {t.myEntries.status[b.status]}
                  </span>
                  <Link href={`/directory/${b.id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">
                    {b.category?.icon} {businessName(b, lang)}
                  </Link>
                  <Link
                    href={`/directory/${b.id}/edit`}
                    className="text-sm font-semibold text-brand-700 hover:underline"
                  >
                    {t.myListings.edit}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </Container>
  );
}
