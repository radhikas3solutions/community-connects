import { localized } from "@/lib/format";
import type { Business, Language } from "@/lib/types";

export const businessName = (b: Pick<Business, "name" | "name_te">, lang: Language) =>
  (lang === "te" && b.name_te) || b.name;

export const businessDescription = (b: Business, lang: Language) =>
  localized(b.description_en, b.description_te, lang);

const digits = (phone: string) => phone.replace(/\D/g, "");

/** `tel:` link; keeps a leading + for international numbers. */
export const telHref = (phone: string) => `tel:${phone.trim().startsWith("+") ? "+" : ""}${digits(phone)}`;

/** wa.me needs the full international number; bare 10-digit numbers are taken as US (+1). */
export function whatsappChatHref(phone: string) {
  const d = digits(phone);
  return `https://wa.me/${d.length === 10 ? `1${d}` : d}`;
}

/** Google Maps search for a business's street address; null for individuals / no address. */
export function directionsHref(b: Business) {
  if (!b.address) return null;
  const query = [b.address, b.city, "VA", b.zip_code].filter(Boolean).join(", ");
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

export const menuPrice = (cents: number | null) =>
  cents == null ? "" : `$${(cents / 100).toFixed(cents % 100 === 0 ? 0 : 2)}`;
