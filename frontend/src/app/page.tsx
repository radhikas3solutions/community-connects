import Link from "next/link";
import { CategoryGrid } from "@/components/CategoryGrid";
import { ListingCard } from "@/components/ListingCard";
import { ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getCategories, searchListings } from "@/lib/api";

export default async function HomePage() {
  const [{ lang, t }, cats, recent] = await Promise.all([
    getDictionary(),
    getCategories(),
    searchListings({ limit: "8", sort: "newest" }),
  ]);

  const marketplace = cats.data.filter((c) => c.kind === "marketplace");
  const general = marketplace.filter((c) => !c.is_community_specific);
  const community = marketplace.filter((c) => c.is_community_specific);
  const business = cats.data.filter((c) => c.kind === "business");

  const quick = [
    { href: "/listings?listing_type=free", label: t.home.quick.free, icon: "🎁", live: true },
    { href: "/listings?listing_type=buy", label: t.home.quick.wanted, icon: "🔎", live: true },
    { href: null, label: t.home.quick.directory, icon: "🏪", live: false },
    { href: null, label: t.home.quick.events, icon: "🎬", live: false },
  ];

  return (
    <>
      <section className="border-b border-line bg-gradient-to-b from-brand-50 to-canvas">
        <Container className="grid gap-8 py-12 md:grid-cols-[1.3fr_1fr] md:items-center md:py-16">
          <div>
            <p className="mb-3 text-sm font-semibold tracking-wide text-accent-600 uppercase">{t.tagline}</p>
            <h1 className="text-4xl font-extrabold tracking-tight text-brand-900 md:text-5xl" lang={lang}>
              {t.home.heroTitle}
            </h1>
            <p className="mt-4 max-w-xl text-lg text-muted" lang={lang}>
              {t.home.heroBody}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <ButtonLink href="/sell" variant="accent" size="lg">
                📸 {t.home.ctaSell}
              </ButtonLink>
              <ButtonLink href="/listings" variant="secondary" size="lg">
                {t.home.ctaBrowse}
              </ButtonLink>
            </div>
          </div>
          <ul className="grid grid-cols-2 gap-3">
            {quick.map((q) => {
              const body = (
                <>
                  <span aria-hidden className="text-3xl">
                    {q.icon}
                  </span>
                  <span className="font-semibold">{q.label}</span>
                  {!q.live && <span className="text-xs text-muted">{t.home.comingSoon}</span>}
                </>
              );
              const cls =
                "flex h-full flex-col gap-1 rounded-[var(--radius-card)] border border-line bg-surface p-4 shadow-sm";
              return (
                <li key={q.label}>
                  {q.href ? (
                    <Link href={q.href} className={`${cls} hover:border-brand-200`}>
                      {body}
                    </Link>
                  ) : (
                    <div className={cls}>{body}</div>
                  )}
                </li>
              );
            })}
          </ul>
        </Container>
      </section>

      <Container className="space-y-12 py-10">
        {!cats.ok && (
          <p role="status" className="rounded-xl border border-accent-400 bg-accent-100 p-4 text-sm">
            {t.apiOffline}
          </p>
        )}

        <Section title={t.home.recent} action={{ href: "/listings", label: t.home.seeAll }}>
          {recent.data.items.length ? (
            <ul className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {recent.data.items.map((l) => (
                <li key={l.id}>
                  <ListingCard listing={l} lang={lang} t={t} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-xl border border-dashed border-line p-8 text-center text-muted">{t.listing.empty}</p>
          )}
        </Section>

        {general.length > 0 && (
          <Section title={t.home.marketplace}>
            <CategoryGrid categories={general} lang={lang} hrefFor={(c) => `/listings?category=${c.slug}`} />
          </Section>
        )}
        {community.length > 0 && (
          <Section title={t.home.community}>
            <CategoryGrid categories={community} lang={lang} hrefFor={(c) => `/listings?category=${c.slug}`} />
          </Section>
        )}
        {business.length > 0 && (
          <Section title={t.home.directory} badge={t.home.comingSoon}>
            <CategoryGrid categories={business} lang={lang} hrefFor={() => null} />
          </Section>
        )}
      </Container>
    </>
  );
}

function Section({
  title,
  action,
  badge,
  children,
}: {
  title: string;
  action?: { href: string; label: string };
  badge?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h2 className="text-xl font-bold">
          {title}
          {badge && (
            <span className="ml-2 rounded-full bg-accent-100 px-2 py-0.5 align-middle text-xs font-semibold text-accent-600">
              {badge}
            </span>
          )}
        </h2>
        {action && (
          <Link href={action.href} className="text-sm font-semibold text-brand-600 hover:underline">
            {action.label} →
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}
