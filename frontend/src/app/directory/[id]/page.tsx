import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { ShareListing } from "@/components/ShareListing";
import { ButtonLink, buttonClass } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { getDictionary, getLang } from "@/i18n/server";
import { getBusiness } from "@/lib/api";
import {
  businessDescription,
  businessName,
  directionsHref,
  menuPrice,
  telHref,
  whatsappChatHref,
} from "@/lib/directory";
import { businessShareText, businessShareUrl } from "@/lib/share";
import { getSession } from "@/lib/supabase/server";
import type { Business, MenuItem } from "@/lib/types";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  const [business, lang] = await Promise.all([getBusiness(id).catch(() => null), getLang()]);
  if (!business) return { title: "Directory" };
  const title = businessName(business, lang);
  const category = business.category ? (lang === "te" ? business.category.name_te : business.category.name_en) : null;
  const description = [category, business.city, businessDescription(business, lang)]
    .filter(Boolean)
    .join(" · ")
    .slice(0, 200);
  return {
    title,
    description,
    alternates: { canonical: `/directory/${business.id}` },
    openGraph: {
      type: "website",
      title,
      description,
      url: businessShareUrl(business.id, lang),
      locale: lang === "te" ? "te_IN" : "en_US",
    },
  };
}

export default async function BusinessPage({ params }: { params: Params }) {
  const { id } = await params;
  const [session, { lang, t }] = await Promise.all([getSession(), getDictionary()]);
  const d = t.directory;

  let business: Business | null;
  try {
    // Signed in: individuals' contact details are included, and editors see pending entries.
    business = await getBusiness(id, session?.accessToken);
  } catch (err) {
    console.error("[directory] fetch failed", err);
    return (
      <Container className="py-16">
        <p role="status" className="rounded-xl border border-accent-400 bg-accent-100 p-4 text-sm">
          {t.apiOffline}
        </p>
      </Container>
    );
  }
  if (!business) notFound();

  const b = business;
  const name = businessName(b, lang);
  const description = businessDescription(b, lang);
  const category = b.category ? (lang === "te" ? b.category.name_te : b.category.name_en) : null;
  const directions = directionsHref(b);
  const whatsapp = b.whatsapp || null;
  const languages = b.languages.map((code) => d.languageNames[code] ?? code).join(", ");

  return (
    <Container className="max-w-3xl py-8">
      <Link href="/directory" className="text-sm text-brand-700 hover:underline">
        ← {d.back}
      </Link>

      {b.status === "pending_review" && (
        <p className="mt-4 rounded-xl border border-accent-400 bg-accent-100 p-3 text-sm font-semibold" lang={lang}>
          {d.pending}
        </p>
      )}
      {b.status === "rejected" && (
        <div className="mt-4 rounded-xl border border-accent-400 bg-accent-100 p-3 text-sm" lang={lang}>
          <p className="font-semibold">{d.rejected}</p>
          {b.review_note && (
            <p className="mt-1">
              {d.reviewerNote} {b.review_note}
            </p>
          )}
        </div>
      )}

      <header className="mt-6 flex gap-4">
        <span aria-hidden className="grid size-16 shrink-0 place-items-center rounded-2xl bg-brand-50 text-4xl">
          {b.category?.icon ?? "📍"}
        </span>
        <div className="min-w-0">
          <h1 className="text-3xl font-bold" lang={lang === "te" && b.name_te ? "te" : undefined}>
            {name}
          </h1>
          <p className="mt-1 text-muted" lang={lang}>
            {[category, b.kind === "individual" ? d.individual : null].filter(Boolean).join(" · ")}
            {b.is_verified && <span className="ml-2 font-semibold text-brand-700">✓ {d.verified}</span>}
            {b.source === "npi" && <span className="ml-2 text-sm font-semibold">📋 {d.publicRecord}</span>}
            {b.source === "osm" && <span className="ml-2 text-sm font-semibold">🗺️ {d.osmRecord}</span>}
          </p>
        </div>
      </header>
      {b.source === "npi" && (
        <p className="mt-4 rounded-xl border border-line bg-canvas p-3 text-sm text-muted" lang={lang}>
          📋 {d.publicRecordNote}
        </p>
      )}
      {b.source === "osm" && (
        <p className="mt-4 rounded-xl border border-line bg-canvas p-3 text-sm text-muted" lang={lang}>
          🗺️ {d.osmRecordNote}{" "}
          {b.source_url && (
            <a
              href={b.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-brand-700 hover:underline"
            >
              {d.osmView}
            </a>
          )}
          <span className="mt-1 block text-xs">
            <a
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:underline"
            >
              {d.osmCredit}
            </a>
          </span>
        </p>
      )}

      {/* Contact actions */}
      <div className="mt-6 flex flex-wrap gap-2">
        {b.phone && (
          <a href={telHref(b.phone)} className={buttonClass("primary")}>
            📞 {d.call}
          </a>
        )}
        {/* Only when the business gave a WhatsApp number: a phone number alone is no consent to WhatsApp. */}
        {whatsapp && !b.contact_hidden && (
          <a
            href={whatsappChatHref(whatsapp)}
            target="_blank"
            rel="noopener noreferrer"
            className={buttonClass("secondary")}
          >
            💬 {d.whatsapp}
          </a>
        )}
        {directions && (
          <a href={directions} target="_blank" rel="noopener noreferrer" className={buttonClass("secondary")}>
            🧭 {d.directions}
          </a>
        )}
        {b.website && (
          <a href={b.website} target="_blank" rel="noopener noreferrer nofollow" className={buttonClass("secondary")}>
            🌐 {d.website}
          </a>
        )}
        {b.email && (
          <a href={`mailto:${b.email}`} className={buttonClass("secondary")}>
            ✉️ {d.email}
          </a>
        )}
      </div>
      {b.contact_hidden && (
        <p className="mt-3 text-sm" lang={lang}>
          🔒{" "}
          <Link href={`/login?next=/directory/${b.id}`} className="font-semibold text-brand-700 hover:underline">
            {d.signInForContact}
          </Link>
        </p>
      )}

      {description && (
        <p className="mt-6 whitespace-pre-line" lang={lang === "te" && b.description_te ? "te" : "en"}>
          {description}
        </p>
      )}

      <dl className="mt-6 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        {b.address && <Row label={d.address}>{[b.address, b.city, b.zip_code].filter(Boolean).join(", ")}</Row>}
        {!b.address && b.city && <Row label="📍">{b.city}</Row>}
        {b.service_area && <Row label={d.serviceArea}>{b.service_area}</Row>}
        {b.hours && <Row label={d.hours}>{b.hours}</Row>}
        {b.phone && !b.contact_hidden && <Row label={d.call}>{b.phone}</Row>}
        {languages && <Row label={d.languages}>{languages}</Row>}
      </dl>

      {b.menu.length > 0 && <Menu items={b.menu} lang={lang} labels={d} />}

      <div className="mt-8 space-y-4 border-t border-line pt-6">
        {b.status === "active" && (
          <ShareListing
            text={businessShareText(b, lang)}
            url={businessShareUrl(b.id, lang)}
            labels={{
              title: d.share,
              whatsapp: t.detail.shareWhatsapp,
              copy: t.detail.copyLink,
              copied: t.detail.copied,
            }}
          />
        )}
        {b.can_edit && (
          <ButtonLink href={`/directory/${b.id}/edit`} variant="secondary">
            ✏️ {d.edit}
          </ButtonLink>
        )}
      </div>
    </Container>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted">{label}</dt>
      <dd>{children}</dd>
    </>
  );
}

function Menu({
  items,
  lang,
  labels,
}: {
  items: MenuItem[];
  lang: "en" | "te";
  labels: { menu: string; veg: string; nonVeg: string };
}) {
  // Group consecutive dishes by section, keeping menu order.
  const sections: { title: string | null; items: MenuItem[] }[] = [];
  for (const item of items) {
    const last = sections.at(-1);
    if (last && last.title === item.section) last.items.push(item);
    else sections.push({ title: item.section, items: [item] });
  }
  return (
    <section className="mt-8">
      <h2 className="mb-3 text-2xl font-bold" lang={lang}>
        {labels.menu}
      </h2>
      <div className="space-y-6">
        {sections.map((s, i) => (
          <div key={i}>
            {s.title && <h3 className="mb-2 text-sm font-bold tracking-wide text-accent-600 uppercase">{s.title}</h3>}
            <ul className="divide-y divide-line rounded-[var(--radius-card)] border border-line bg-surface">
              {s.items.map((item, j) => {
                const name = (lang === "te" && item.name_te) || item.name;
                return (
                  <li key={item.id ?? j} className="flex items-start gap-3 p-3">
                    {item.is_vegetarian != null && (
                      <span
                        role="img"
                        aria-label={item.is_vegetarian ? labels.veg : labels.nonVeg}
                        title={item.is_vegetarian ? labels.veg : labels.nonVeg}
                        className={`mt-1 grid size-4 shrink-0 place-items-center rounded-sm border-2 ${
                          item.is_vegetarian ? "border-green-600" : "border-red-700"
                        }`}
                      >
                        <span
                          className={`size-1.5 rounded-full ${item.is_vegetarian ? "bg-green-600" : "bg-red-700"}`}
                        />
                      </span>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="font-medium" lang={lang === "te" && item.name_te ? "te" : undefined}>
                        {name}
                      </p>
                      {item.description && <p className="text-sm text-muted">{item.description}</p>}
                    </div>
                    {item.price_cents != null && (
                      <span className="shrink-0 font-semibold">{menuPrice(item.price_cents)}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
