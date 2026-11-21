/** Member phone numbers from any country, sent to the API in international form ("+917702345678"). */

export interface Country {
  code: string; // ISO 3166 alpha-2
  dial: string; // country calling code, digits only
  name: string;
  flag: string;
}

// Most members are in the US; the rest are the countries their families most often call from.
export const COUNTRIES: Country[] = [
  { code: "US", dial: "1", name: "United States / Canada", flag: "🇺🇸" },
  { code: "IN", dial: "91", name: "India", flag: "🇮🇳" },
  { code: "GB", dial: "44", name: "United Kingdom", flag: "🇬🇧" },
  { code: "AE", dial: "971", name: "United Arab Emirates", flag: "🇦🇪" },
  { code: "SA", dial: "966", name: "Saudi Arabia", flag: "🇸🇦" },
  { code: "QA", dial: "974", name: "Qatar", flag: "🇶🇦" },
  { code: "KW", dial: "965", name: "Kuwait", flag: "🇰🇼" },
  { code: "OM", dial: "968", name: "Oman", flag: "🇴🇲" },
  { code: "SG", dial: "65", name: "Singapore", flag: "🇸🇬" },
  { code: "MY", dial: "60", name: "Malaysia", flag: "🇲🇾" },
  { code: "AU", dial: "61", name: "Australia", flag: "🇦🇺" },
  { code: "NZ", dial: "64", name: "New Zealand", flag: "🇳🇿" },
  { code: "DE", dial: "49", name: "Germany", flag: "🇩🇪" },
  { code: "FR", dial: "33", name: "France", flag: "🇫🇷" },
  { code: "NL", dial: "31", name: "Netherlands", flag: "🇳🇱" },
  { code: "IE", dial: "353", name: "Ireland", flag: "🇮🇪" },
  { code: "MX", dial: "52", name: "Mexico", flag: "🇲🇽" },
  { code: "BR", dial: "55", name: "Brazil", flag: "🇧🇷" },
  { code: "PK", dial: "92", name: "Pakistan", flag: "🇵🇰" },
  { code: "BD", dial: "880", name: "Bangladesh", flag: "🇧🇩" },
  { code: "LK", dial: "94", name: "Sri Lanka", flag: "🇱🇰" },
  { code: "NP", dial: "977", name: "Nepal", flag: "🇳🇵" },
  { code: "PH", dial: "63", name: "Philippines", flag: "🇵🇭" },
  { code: "CN", dial: "86", name: "China", flag: "🇨🇳" },
  { code: "JP", dial: "81", name: "Japan", flag: "🇯🇵" },
  { code: "KR", dial: "82", name: "South Korea", flag: "🇰🇷" },
  { code: "NG", dial: "234", name: "Nigeria", flag: "🇳🇬" },
  { code: "KE", dial: "254", name: "Kenya", flag: "🇰🇪" },
  { code: "ZA", dial: "27", name: "South Africa", flag: "🇿🇦" },
];

export interface PhoneValue {
  country: string; // Country.code
  number: string; // as typed
}

export const emptyPhone = (): PhoneValue => ({ country: "US", number: "" });

/**
 * International form, or null when it can't be a real number. A number typed with its own "+"
 * ignores the country picker. The national trunk "0" (India "098…", UK "020…") is dropped.
 */
export function toInternational({ country, number }: PhoneValue): string | null {
  const typed = number.trim();
  let digits = typed.replace(/\D/g, "");
  if (!digits) return null;
  if (typed.startsWith("+")) {
    // already international
  } else if (typed.startsWith("00")) {
    digits = digits.slice(2);
  } else {
    const dial = COUNTRIES.find((c) => c.code === country)?.dial ?? "1";
    if (dial === "1") {
      if (digits.length === 11 && digits.startsWith("1")) digits = digits.slice(1);
      if (!/^[2-9][0-9]{2}[2-9][0-9]{6}$/.test(digits)) return null;
    } else {
      digits = digits.replace(/^0+/, "");
    }
    digits = dial + digits;
  }
  if (digits.length < 7 || digits.length > 15 || digits.startsWith("0")) return null;
  return `+${digits}`;
}

/** Back from "+917702345678" to the picker and the national number, for editing. */
export function fromInternational(phone: string | null | undefined): PhoneValue {
  if (!phone) return emptyPhone();
  const digits = phone.replace(/\D/g, "");
  // Longest calling code first, so "+971" isn't read as "+97…".
  const match = [...COUNTRIES].sort((a, b) => b.dial.length - a.dial.length).find((c) => digits.startsWith(c.dial));
  return match ? { country: match.code, number: digits.slice(match.dial.length) } : { country: "US", number: phone };
}

/** wa.me wants digits only. */
export const whatsappLink = (phone: string) => `https://wa.me/${phone.replace(/\D/g, "")}`;
