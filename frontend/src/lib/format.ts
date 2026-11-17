import type { Language, Listing } from "@/lib/types";

export function formatPrice(listing: Pick<Listing, "listing_type" | "price_cents" | "currency">, lang: Language) {
  if (listing.listing_type === "free") return lang === "te" ? "ఉచితం" : "Free";
  if (listing.price_cents == null) return lang === "te" ? "ధర చర్చించవచ్చు" : "Make an offer";
  return new Intl.NumberFormat(lang === "te" ? "te-IN" : "en-US", {
    style: "currency",
    currency: listing.currency || "USD",
    maximumFractionDigits: listing.price_cents % 100 === 0 ? 0 : 2,
  }).format(listing.price_cents / 100);
}

/** Pick the text in the viewer's language, falling back to the other one. */
export function localized(en: string | null | undefined, te: string | null | undefined, lang: Language) {
  return (lang === "te" ? te || en : en || te) ?? "";
}
