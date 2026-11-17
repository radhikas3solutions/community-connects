import { SITE_URL } from "@/lib/env";
import { formatPrice, localized } from "@/lib/format";
import type { Language, Listing } from "@/lib/types";

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
