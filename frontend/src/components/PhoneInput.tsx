"use client";

import { COUNTRIES, type Country, type PhoneValue } from "@/lib/phone";

const US: Country = { code: "US", dial: "1", name: "United States / Canada", flag: "🇺🇸" };

/** Country picker plus number. Typing a number starting with "+" works for any country. */
export function PhoneInput({
  id,
  value,
  onChange,
  required,
  countryLabel,
}: {
  id: string;
  value: PhoneValue;
  onChange: (value: PhoneValue) => void;
  required?: boolean;
  countryLabel: string;
}) {
  const country = COUNTRIES.find((c) => c.code === value.country) ?? US;
  return (
    <div className="flex gap-2">
      <label htmlFor={`${id}-country`} className="sr-only">
        {countryLabel}
      </label>
      <select
        id={`${id}-country`}
        value={country.code}
        onChange={(e) => onChange({ ...value, country: e.target.value })}
        className="h-11 w-28 shrink-0 rounded-xl border border-line bg-surface px-2 text-sm"
      >
        {COUNTRIES.map((c) => (
          <option key={c.code} value={c.code}>
            {c.flag} +{c.dial} {c.name}
          </option>
        ))}
      </select>
      <input
        id={id}
        type="tel"
        required={required}
        autoComplete="tel"
        placeholder={country.dial === "1" ? "703-555-0123" : "98765 43210"}
        value={value.number}
        onChange={(e) => onChange({ ...value, number: e.target.value })}
        className="h-11 min-w-0 flex-1 rounded-xl border border-line bg-surface px-4"
      />
    </div>
  );
}
