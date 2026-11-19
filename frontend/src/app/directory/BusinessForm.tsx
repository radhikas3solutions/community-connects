"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { BrowserApiError, browserApi } from "@/lib/browser-api";
import type { Business, Category, EntryKind, Language } from "@/lib/types";

type Props = {
  business?: Business;
  categories: Category[];
  lang: Language;
  t: Dictionary["entryForm"];
  languageNames: Record<string, string>;
};

const LANGUAGE_CHOICES = ["te", "en", "hi", "ta", "kn", "ml", "mr", "gu", "bn", "ur", "pa"];
const TEXT_FIELDS = [
  "name",
  "name_te",
  "description_en",
  "description_te",
  "phone",
  "whatsapp",
  "email",
  "website",
  "address",
  "city",
  "zip_code",
  "service_area",
  "hours",
] as const;
type TextField = (typeof TEXT_FIELDS)[number];

const input = "w-full rounded-xl border border-line bg-surface px-3 py-2";
const orNull = (s: string) => s.trim() || null;

function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function BusinessForm({ business, categories, lang, t, languageNames }: Props) {
  const router = useRouter();
  const editing = Boolean(business);
  const [kind, setKind] = useState<EntryKind>(business?.kind ?? "business");
  const [categoryId, setCategoryId] = useState(business?.category ? String(business.category.id) : "");
  const [f, setF] = useState<Record<TextField, string>>(
    () => Object.fromEntries(TEXT_FIELDS.map((k) => [k, business?.[k] ?? ""])) as Record<TextField, string>,
  );
  const [languages, setLanguages] = useState<string[]>(business?.languages ?? ["te", "en"]);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState<null | "save" | "delete">(null);
  const [message, setMessage] = useState<{ kind: "error" | "ok"; text: string } | null>(null);

  const isIndividual = kind === "individual";
  const set = (key: TextField) => (e: { target: { value: string } }) =>
    setF((prev) => ({ ...prev, [key]: e.target.value }));
  const toggleLanguage = (code: string) =>
    setLanguages((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setMessage(null);
    if (!categoryId) return setMessage({ kind: "error", text: t.needCategory });
    if (!(f.phone.trim() || f.whatsapp.trim() || f.email.trim() || f.website.trim())) {
      return setMessage({ kind: "error", text: t.needContact });
    }
    if (!editing && isIndividual && !consent) return setMessage({ kind: "error", text: t.needConsent });

    const fields = Object.fromEntries(TEXT_FIELDS.map((k) => [k, orNull(f[k])]));
    if (isIndividual) delete fields.address;
    const body = { ...fields, category_id: Number(categoryId), languages };

    setBusy("save");
    try {
      if (editing && business) {
        await browserApi<Business>(`/api/v1/businesses/${business.id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
        setMessage({ kind: "ok", text: t.saved });
        router.refresh();
      } else {
        const created = await browserApi<Business>("/api/v1/businesses", {
          method: "POST",
          body: JSON.stringify({ ...body, kind, consent_confirmed: consent }),
        });
        router.push(`/directory/${created.id}`);
        router.refresh();
      }
    } catch (err) {
      const detail = err instanceof BrowserApiError && err.status === 422 ? ` (${err.message})` : "";
      setMessage({ kind: "error", text: `${t.error}${detail}` });
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (!business || !window.confirm(t.confirmDelete)) return;
    setBusy("delete");
    try {
      await browserApi(`/api/v1/businesses/${business.id}`, { method: "DELETE" });
      router.push("/account");
      router.refresh();
    } catch {
      setMessage({ kind: "error", text: t.error });
      setBusy(null);
    }
  }

  return (
    <form onSubmit={submit} className="mt-6 space-y-6" lang={lang}>
      {!editing && (
        <fieldset>
          <legend className="mb-2 text-sm font-medium">{t.kind}</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {(["business", "individual"] as const).map((k) => (
              <label
                key={k}
                className={`flex cursor-pointer items-start gap-2 rounded-xl border p-3 text-sm ${
                  kind === k ? "border-brand-600 bg-brand-50" : "border-line bg-surface"
                }`}
              >
                <input type="radio" name="kind" value={k} checked={kind === k} onChange={() => setKind(k)} className="mt-1" />
                {k === "business" ? t.kindBusiness : t.kindIndividual}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t.category} htmlFor="category">
          <select
            id="category"
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className={input}
            required
          >
            <option value="">{t.chooseCategory}</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.icon} {lang === "te" ? c.name_te : c.name_en}
              </option>
            ))}
          </select>
        </Field>
        <div />
        <Field label={t.name} htmlFor="name">
          <input id="name" value={f.name} onChange={set("name")} required minLength={2} maxLength={120} className={input} />
        </Field>
        <Field label={t.nameTe} htmlFor="name_te">
          <input id="name_te" value={f.name_te} onChange={set("name_te")} maxLength={240} className={input} lang="te" />
        </Field>
      </div>

      <Field label={t.descriptionEn} htmlFor="description_en">
        <textarea
          id="description_en"
          value={f.description_en}
          onChange={set("description_en")}
          rows={3}
          maxLength={3000}
          className={input}
          lang="en"
        />
      </Field>
      <Field label={t.descriptionTe} htmlFor="description_te">
        <textarea
          id="description_te"
          value={f.description_te}
          onChange={set("description_te")}
          rows={3}
          maxLength={6000}
          className={input}
          lang="te"
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t.phone} htmlFor="phone">
          <input id="phone" type="tel" value={f.phone} onChange={set("phone")} className={input} autoComplete="off" />
        </Field>
        <Field label={t.whatsapp} htmlFor="whatsapp">
          <input id="whatsapp" type="tel" value={f.whatsapp} onChange={set("whatsapp")} className={input} autoComplete="off" />
        </Field>
        <Field label={t.email} htmlFor="email">
          <input id="email" type="email" value={f.email} onChange={set("email")} className={input} autoComplete="off" />
        </Field>
        <Field label={t.website} htmlFor="website">
          <input id="website" value={f.website} onChange={set("website")} className={input} placeholder="example.com" />
        </Field>
        {!isIndividual && (
          <Field label={t.address} htmlFor="address">
            <input id="address" value={f.address} onChange={set("address")} maxLength={200} className={input} />
          </Field>
        )}
        <Field label={t.city} htmlFor="city">
          <input id="city" value={f.city} onChange={set("city")} maxLength={80} className={input} />
        </Field>
        <Field label={t.zip} htmlFor="zip_code">
          <input
            id="zip_code"
            value={f.zip_code}
            onChange={set("zip_code")}
            inputMode="numeric"
            pattern="\d{5}(-\d{4})?"
            className={input}
          />
        </Field>
        <Field label={t.serviceArea} htmlFor="service_area" hint={t.serviceAreaHint}>
          <input id="service_area" value={f.service_area} onChange={set("service_area")} maxLength={200} className={input} />
        </Field>
        <Field label={t.hours} htmlFor="hours" hint={t.hoursHint}>
          <input id="hours" value={f.hours} onChange={set("hours")} maxLength={200} className={input} />
        </Field>
      </div>

      <fieldset>
        <legend className="mb-2 text-sm font-medium">{t.languages}</legend>
        <div className="flex flex-wrap gap-2">
          {LANGUAGE_CHOICES.map((code) => (
            <label
              key={code}
              className={`cursor-pointer rounded-full border px-3 py-1 text-sm ${
                languages.includes(code) ? "border-brand-600 bg-brand-50" : "border-line bg-surface"
              }`}
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={languages.includes(code)}
                onChange={() => toggleLanguage(code)}
              />
              {languageNames[code] ?? code}
            </label>
          ))}
        </div>
      </fieldset>

      {isIndividual && (
        <div className="space-y-3 rounded-xl border border-line bg-brand-50 p-4 text-sm">
          <p>🔒 {t.privacyNote}</p>
          {!editing && (
            <label className="flex items-start gap-2 font-medium">
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1" />
              {t.consent}
            </label>
          )}
        </div>
      )}

      {message && (
        <p
          role={message.kind === "error" ? "alert" : "status"}
          className={`rounded-xl p-3 text-sm ${message.kind === "error" ? "bg-accent-100" : "bg-brand-50 text-brand-700"}`}
        >
          {message.text}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={busy !== null}>
          {busy === "save" ? t.saving : editing ? t.save : t.submit}
        </Button>
        {editing && (
          <Button type="button" variant="ghost" onClick={remove} disabled={busy !== null} className="ml-auto text-red-700">
            {t.delete}
          </Button>
        )}
      </div>
    </form>
  );
}
