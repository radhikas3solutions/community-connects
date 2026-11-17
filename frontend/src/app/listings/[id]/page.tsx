import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getListing } from "@/lib/api";
import { formatPrice, localized } from "@/lib/format";
import { getSession } from "@/lib/supabase/server";
import type { Listing } from "@/lib/types";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  const listing = await getListing(id).catch(() => null);
  return { title: listing ? (listing.title_en ?? listing.title_te ?? "Listing") : "Listing" };
}

export default async function ListingPage({ params }: { params: Params }) {
  const { id } = await params;
  const [session, { lang, t }] = await Promise.all([getSession(), getDictionary()]);

  let listing: Listing | null;
  try {
    // With a token the owner can also see their own draft.
    listing = await getListing(id, session?.accessToken);
  } catch (err) {
    console.error("[listing] fetch failed", err);
    return (
      <Container className="py-16">
        <p role="status" className="rounded-xl border border-accent-400 bg-accent-100 p-4 text-sm">
          {t.apiOffline}
        </p>
      </Container>
    );
  }
  if (!listing) notFound();

  const isOwner = session?.userId === listing.owner.id;
  const title = localized(listing.title_en, listing.title_te, lang);
  const description = localized(listing.description_en, listing.description_te, lang);
  const [cover, ...rest] = listing.images;
  const typeLabel =
    listing.listing_type === "free" ? t.listing.free : listing.listing_type === "buy" ? t.listing.wanted : t.listing.sell;

  return (
    <Container className="py-8">
      <Link href="/listings" className="text-sm text-brand-700 hover:underline">
        ← {t.detail.back}
      </Link>

      {listing.status === "draft" && (
        <p className="mt-4 rounded-xl border border-accent-400 bg-accent-100 p-3 text-sm font-semibold">
          {t.detail.draft}
        </p>
      )}

      <div className="mt-4 grid gap-8 md:grid-cols-[1.2fr_1fr]">
        <section aria-label="Photos" className="space-y-2">
          {cover ? (
            <>
              <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
                <Image
                  src={cover.url}
                  alt={title}
                  width={cover.width}
                  height={cover.height}
                  unoptimized
                  priority
                  className="max-h-[70vh] w-full object-contain"
                />
              </div>
              {rest.length > 0 && (
                <ul className="grid grid-cols-4 gap-2">
                  {rest.map((img, i) => (
                    <li key={img.id} className="aspect-square overflow-hidden rounded-lg border border-line">
                      <a href={img.url} target="_blank" rel="noopener noreferrer">
                        <Image
                          src={img.url}
                          alt={`${title} (${i + 2})`}
                          width={img.width}
                          height={img.height}
                          unoptimized
                          className="h-full w-full object-cover"
                        />
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <div aria-hidden className="grid aspect-[4/3] place-items-center rounded-[var(--radius-card)] bg-brand-50 text-7xl">
              {listing.category?.icon ?? "📦"}
            </div>
          )}
        </section>

        <section className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-brand-100 px-2 py-0.5 text-xs font-semibold text-brand-700">{typeLabel}</span>
            {listing.status === "sold" && (
              <span className="rounded-full bg-ink px-2 py-0.5 text-xs font-semibold text-white">{t.detail.sold}</span>
            )}
          </div>
          <h1 className="text-3xl font-bold" lang={listing.title_te && lang === "te" ? "te" : "en"}>
            {title}
          </h1>
          <p className="text-3xl font-extrabold text-brand-700">
            {formatPrice(listing, lang)}
            {listing.is_negotiable && listing.listing_type === "sell" && (
              <span className="ml-2 align-middle text-sm font-medium text-muted">{t.detail.negotiable}</span>
            )}
          </p>

          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            {listing.condition && (
              <>
                <dt className="text-muted">{t.detail.condition}</dt>
                <dd>{t.conditions[listing.condition]}</dd>
              </>
            )}
            {listing.category && (
              <>
                <dt className="text-muted">{t.detail.category}</dt>
                <dd>
                  <Link href={`/listings?category=${listing.category.slug}`} className="text-brand-700 hover:underline">
                    {listing.category.icon} {lang === "te" ? listing.category.name_te : listing.category.name_en}
                  </Link>
                </dd>
              </>
            )}
            {(listing.city || listing.zip_code) && (
              <>
                <dt aria-label="Location">📍</dt>
                <dd>{[listing.city, listing.zip_code].filter(Boolean).join(" ")}</dd>
              </>
            )}
            <dt className="text-muted">{t.detail.seller}</dt>
            <dd>{listing.owner.display_name ?? "—"}</dd>
            <dt className="text-muted">{t.detail.posted}</dt>
            <dd>{new Date(listing.created_at).toLocaleDateString(lang === "te" ? "te-IN" : "en-US")}</dd>
          </dl>

          {description && (
            <p className="whitespace-pre-line" lang={listing.description_te && lang === "te" ? "te" : "en"}>
              {description}
            </p>
          )}

          {isOwner ? (
            <ButtonLink href={`/listings/${listing.id}/edit`} variant="secondary">
              ✏️ {t.detail.edit}
            </ButtonLink>
          ) : (
            <p className="rounded-xl bg-brand-50 p-3 text-sm text-brand-700">{t.detail.contactSoon}</p>
          )}
        </section>
      </div>
    </Container>
  );
}
