import { SITE_URL } from "@/lib/env";
import { formatPrice, localized } from "@/lib/format";
import { businessName } from "@/lib/directory";
import type { Business, Language, Listing } from "@/lib/types";

const typeEmoji: Record<Listing["listing_type"], string> = { free: "🆓", sell: "🏷️", buy: "🔎" };

/**
 * Public link to a listing. It carries the language so the person (and WhatsApp's preview
 * fetcher, which has no language cookie) sees the listing in the language it was shared in.
 */
export function listingShareUrl(id: string, lang: Language) {
  return `${SITE_URL}/listings/${id}?lang=${lang}`;
}

/** Stable image URL for link previews; redirects to a fresh signed photo URL. */
export function listingCoverUrl(id: string) {
  return `${SITE_URL}/listings/${id}/cover`;
}

/** Ready-to-send message, e.g. "🆓 Natural wood baby crib\nFree · Herndon\nhttps://…". */
export function listingShareText(listing: Listing, lang: Language) {
  const title = localized(listing.title_en, listing.title_te, lang);
  const details = [formatPrice(listing, lang), listing.city].filter(Boolean).join(" · ");
  return `${typeEmoji[listing.listing_type]} ${title}\n${details}\n${listingShareUrl(listing.id, lang)}`;
}

export const businessShareUrl = (id: string, lang: Language) => `${SITE_URL}/directory/${id}?lang=${lang}`;

/** e.g. "🍽️ Godavari Kitchen\nRestaurants · Ashburn\nhttps://…" */
export function businessShareText(b: Business, lang: Language) {
  const category = b.category ? (lang === "te" ? b.category.name_te : b.category.name_en) : null;
  const details = [category, b.city].filter(Boolean).join(" · ");
  return `${b.category?.icon ?? "📍"} ${businessName(b, lang)}\n${details}\n${businessShareUrl(b.id, lang)}`;
}
