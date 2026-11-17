import Image from "next/image";
import Link from "next/link";
import type { Dictionary } from "@/i18n/dictionaries";
import { formatPrice, localized } from "@/lib/format";
import type { Language, Listing } from "@/lib/types";

const badge: Record<Listing["listing_type"], string> = {
  free: "bg-brand-100 text-brand-700",
  buy: "bg-accent-100 text-accent-600",
  sell: "bg-canvas text-muted",
};

export function ListingCard({ listing, lang, t }: { listing: Listing; lang: Language; t: Dictionary }) {
  const title = localized(listing.title_en, listing.title_te, lang);
  const label =
    listing.listing_type === "free" ? t.listing.free : listing.listing_type === "buy" ? t.listing.wanted : t.listing.sell;

  const cover = listing.images?.[0];

  return (
    <article className="relative flex h-full flex-col overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface transition-shadow focus-within:shadow-md hover:shadow-md">
      {cover ? (
        <Image
          src={cover.url}
          alt=""
          width={cover.width}
          height={cover.height}
          unoptimized
          className="aspect-[4/3] w-full object-cover"
        />
      ) : (
        <div aria-hidden className="grid aspect-[4/3] place-items-center bg-brand-50 text-4xl">
          {listing.category?.icon ?? "📦"}
        </div>
      )}
      <div className="flex flex-1 flex-col gap-1 p-3">
        <span className={`w-fit rounded-full px-2 py-0.5 text-xs font-semibold ${badge[listing.listing_type]}`}>
          {label}
        </span>
        <h3 className="line-clamp-2 font-semibold" lang={lang}>
          {/* Stretched link: the whole card is clickable, but only the title is announced. */}
          <Link href={`/listings/${listing.id}`} className="after:absolute after:inset-0">
            {title}
          </Link>
        </h3>
        <p className="mt-auto text-lg font-bold text-brand-700">{formatPrice(listing, lang)}</p>
        <p className="text-xs text-muted">
          {[listing.city, listing.distance_km != null ? `${listing.distance_km} ${t.listing.km}` : null]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </div>
    </article>
  );
}
