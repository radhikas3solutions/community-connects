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

  return (
    <article className="flex h-full flex-col overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
      {/* Photos arrive in Phase 2 (Supabase Storage); placeholder keeps the grid rhythm. */}
      <div aria-hidden className="grid aspect-[4/3] place-items-center bg-brand-50 text-4xl">
        {listing.category?.icon ?? "📦"}
      </div>
      <div className="flex flex-1 flex-col gap-1 p-3">
        <span className={`w-fit rounded-full px-2 py-0.5 text-xs font-semibold ${badge[listing.listing_type]}`}>
          {label}
        </span>
        <h3 className="line-clamp-2 font-semibold" lang={lang}>
          {title}
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
