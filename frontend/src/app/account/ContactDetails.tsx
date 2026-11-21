"use client";

import { useState, type FormEvent } from "react";
import { PhoneInput } from "@/components/PhoneInput";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { browserApi } from "@/lib/browser-api";
import { fromInternational, toInternational, whatsappLink } from "@/lib/phone";
import type { Profile } from "@/lib/types";

/** The member's name, phone and WhatsApp number, with an edit form. */
export function ContactDetails({
  profile,
  t,
  countryLabel,
}: {
  profile: Profile;
  t: Dictionary["account"];
  countryLabel: string;
}) {
  const [current, setCurrent] = useState(profile);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<"" | "saved" | "failed">("");

  const [firstName, setFirstName] = useState(profile.first_name ?? "");
  const [lastName, setLastName] = useState(profile.last_name ?? "");
  const [phone, setPhone] = useState(() => fromInternational(profile.phone));
  const [whatsapp, setWhatsapp] = useState(() => fromInternational(profile.whatsapp));

  async function save(e: FormEvent) {
    e.preventDefault();
    const phoneNumber = phone.number.trim() ? toInternational(phone) : null;
    const whatsappNumber = whatsapp.number.trim() ? toInternational(whatsapp) : null;
    if ((phone.number.trim() && !phoneNumber) || (whatsapp.number.trim() && !whatsappNumber)) {
      setStatus("failed");
      return;
    }
    setBusy(true);
    setStatus("");
    try {
      const first = firstName.trim();
      const last = lastName.trim();
      const updated = await browserApi<Profile>("/api/v1/me", {
        method: "PATCH",
        body: JSON.stringify({
          ...(first ? { first_name: first } : {}),
          ...(last ? { last_name: last } : {}),
          ...(first || last ? { display_name: [first, last].filter(Boolean).join(" ") } : {}),
          phone: phoneNumber ?? "",
          whatsapp: whatsappNumber ?? "",
          whatsapp_opt_in: Boolean(whatsappNumber),
        }),
      });
      setCurrent(updated);
      setEditing(false);
      setStatus("saved");
    } catch {
      setStatus("failed");
    } finally {
      setBusy(false);
    }
  }

  const input = "h-11 w-full rounded-xl border border-line bg-surface px-4";

  if (editing) {
    return (
      <form onSubmit={save} className="mt-6 space-y-3 border-t border-line pt-6 text-sm">
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1">
            <span className="block font-medium">{t.name}</span>
            <input value={firstName} onChange={(e) => setFirstName(e.target.value)} maxLength={60} className={input} />
          </label>
          <label className="space-y-1">
            <span className="block font-medium">&nbsp;</span>
            <input value={lastName} onChange={(e) => setLastName(e.target.value)} maxLength={60} className={input} />
          </label>
        </div>
        <div className="space-y-1">
          <label htmlFor="edit-phone" className="block font-medium">
            {t.phone}
          </label>
          <PhoneInput id="edit-phone" value={phone} onChange={setPhone} countryLabel={countryLabel} />
        </div>
        <div className="space-y-1">
          <label htmlFor="edit-whatsapp" className="block font-medium">
            {t.whatsapp}
          </label>
          <PhoneInput id="edit-whatsapp" value={whatsapp} onChange={setWhatsapp} countryLabel={countryLabel} />
        </div>
        {status === "failed" && (
          <p role="alert" className="text-red-700">
            {t.saveFailed}
          </p>
        )}
        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={busy}>
            {t.save}
          </Button>
          <Button type="button" size="sm" variant="secondary" onClick={() => setEditing(false)} disabled={busy}>
            {t.cancel}
          </Button>
        </div>
      </form>
    );
  }

  const name = current.display_name || [current.first_name, current.last_name].filter(Boolean).join(" ");
  return (
    <div className="mt-6 border-t border-line pt-6 text-sm">
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3">
        <dt className="text-muted">{t.name}</dt>
        <dd>{name || t.notSet}</dd>
        <dt className="text-muted">{t.phone}</dt>
        <dd>
          {current.phone ? (
            <a href={`tel:${current.phone}`} className="hover:underline">
              {current.phone}
            </a>
          ) : (
            t.notSet
          )}
        </dd>
        <dt className="text-muted">{t.whatsapp}</dt>
        <dd>
          {current.whatsapp ? (
            <a href={whatsappLink(current.whatsapp)} target="_blank" rel="noopener" className="hover:underline">
              {current.whatsapp}
            </a>
          ) : (
            t.notSet
          )}
        </dd>
      </dl>
      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            setEditing(true);
            setStatus("");
          }}
          className="font-semibold text-brand-700 hover:underline"
        >
          ✏️ {t.editContact}
        </button>
        {status === "saved" && <span className="text-brand-700">✓ {t.saved}</span>}
      </div>
    </div>
  );
}
