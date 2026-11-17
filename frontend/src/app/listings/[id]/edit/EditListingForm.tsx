"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { BrowserApiError, browserApi } from "@/lib/browser-api";
import type { Category, ItemCondition, Language, Listing, ListingImage, ListingType } from "@/lib/types";

type Props = {
  listing: Listing;
  categories: Category[];
  lang: Language;
  t: Dictionary["edit"];
  conditions: Dictionary["conditions"];
  typeLabels: Record<ListingType, string>;
};

type TextField =
  | "title_en"
  | "title_te"
  | "description_en"
  | "description_te"
  | "category_id"
  | "condition"
  | "price"
  | "city"
  | "zip_code";

const CONDITIONS: ItemCondition[] = ["new", "like_new", "good", "fair", "for_parts"];
const input = "w-full rounded-xl border border-line bg-surface px-3 py-2";

const dollars = (cents: number | null) => (cents == null ? "" : String(cents / 100));
const usd = (cents: number) => `$${Math.round(cents / 100).toLocaleString("en-US")}`;
const orNull = (s: string) => s.trim() || null;

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      {children}
    </div>
  );
}

export function EditListingForm({ listing, categories, lang, t, conditions, typeLabels }: Props) {
  const router = useRouter();
  const [f, setF] = useState<Record<TextField, string>>({
    title_en: listing.title_en ?? "",
    title_te: listing.title_te ?? "",
    description_en: listing.description_en ?? "",
    description_te: listing.description_te ?? "",
    category_id: listing.category?.id ? String(listing.category.id) : "",
    condition: listing.condition ?? "",
    price: dollars(listing.price_cents),
    city: listing.city ?? "",
    zip_code: listing.zip_code ?? "",
  });
  const [negotiable, setNegotiable] = useState(listing.is_negotiable);
  const [images, setImages] = useState<ListingImage[]>(listing.images);
  const [busy, setBusy] = useState<null | "save" | "publish" | "sold" | "delete">(null);
  const [message, setMessage] = useState<{ kind: "error" | "ok"; text: string } | null>(null);

  const isDraft = listing.status === "draft";
  const isSell = listing.listing_type === "sell";
  const set = (key: TextField) => (e: { target: { value: string } }) =>
    setF((prev) => ({ ...prev, [key]: e.target.value }));

  function payload() {
    const price = f.price.trim() === "" ? null : Math.round(Number(f.price) * 100);
    return {
      title_en: orNull(f.title_en),
      title_te: orNull(f.title_te),
      description_en: orNull(f.description_en),
      description_te: orNull(f.description_te),
      category_id: f.category_id ? Number(f.category_id) : null,
      condition: f.condition || null,
      ...(isSell ? { price_cents: price } : {}),
      is_negotiable: negotiable,
      city: orNull(f.city),
      zip_code: orNull(f.zip_code),
    };
  }

  async function save(action: "save" | "publish" | "sold", e?: FormEvent) {
    e?.preventDefault();
    setMessage(null);
    const body = payload();
    if (!body.title_en && !body.title_te) return setMessage({ kind: "error", text: t.needTitle });
    if (action === "publish" && isSell && (body.price_cents == null || Number.isNaN(body.price_cents))) {
      return setMessage({ kind: "error", text: t.needPrice });
    }
    setBusy(action);
    try {
      const status = action === "publish" ? "active" : action === "sold" ? "sold" : undefined;
      await browserApi<Listing>(`/api/v1/listings/${listing.id}`, {
        method: "PATCH",
        body: JSON.stringify(status ? { ...body, status } : body),
      });
      if (action === "save") {
        setMessage({ kind: "ok", text: t.saved });
        router.refresh();
      } else {
        router.push(`/listings/${listing.id}`);
        router.refresh();
      }
    } catch (err) {
      const detail = err instanceof BrowserApiError && err.status === 422 ? ` (${err.message})` : "";
      setMessage({ kind: "error", text: `${t.error}${detail}` });
    } finally {
      setBusy(null);
    }
  }

  async function deletePhoto(imageId: string) {
    try {
      await browserApi(`/api/v1/listings/${listing.id}/images/${imageId}`, { method: "DELETE" });
      setImages((prev) => prev.filter((i) => i.id !== imageId));
    } catch {
      setMessage({ kind: "error", text: t.error });
    }
  }

  async function deleteListing() {
    if (!window.confirm(t.confirmDelete)) return;
    setBusy("delete");
    try {
      await browserApi(`/api/v1/listings/${listing.id}`, { method: "DELETE" });
      router.push("/account");
      router.refresh();
    } catch {
      setMessage({ kind: "error", text: t.error });
      setBusy(null);
    }
  }

  return (
    <form onSubmit={(e) => save("save", e)} className="mt-6 space-y-8">
      {isDraft && (
        <div className="space-y-1 rounded-xl border border-accent-400 bg-accent-100 p-4 text-sm" lang={lang}>
          <p className="font-semibold">{t.draftNotice}</p>
          {listing.ai_confidence != null && <p>✨ {t.aiNotice}</p>}
        </div>
      )}

      {images.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">{t.photos}</h2>
          <ul className="grid grid-cols-3 gap-2 sm:grid-cols-5">
            {images.map((img, i) => (
              <li key={img.id} className="relative aspect-square overflow-hidden rounded-lg border border-line">
                <Image
                  src={img.url}
                  alt={`${t.photos} ${i + 1}`}
                  width={img.width}
                  height={img.height}
                  unoptimized
                  className="h-full w-full object-cover"
                />
                {images.length > 1 && (
                  <button
                    type="button"
                    onClick={() => deletePhoto(img.id)}
                    aria-label={`${t.deletePhoto} ${i + 1}`}
                    className="absolute top-1 right-1 grid h-7 w-7 place-items-center rounded-full bg-ink/70 text-white"
                  >
                    ×
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <section className="space-y-3">
          <h2 className="font-semibold">🇺🇸 {t.english}</h2>
          <Field label={t.titleLabel} htmlFor="title_en">
            <input id="title_en" value={f.title_en} onChange={set("title_en")} maxLength={140} className={input} />
          </Field>
          <Field label={t.descriptionLabel} htmlFor="description_en">
            <textarea
              id="description_en"
              value={f.description_en}
              onChange={set("description_en")}
              rows={6}
              maxLength={5000}
              className={input}
            />
          </Field>
        </section>
        <section className="space-y-3" lang="te">
          <h2 className="font-semibold">తెలుగు · {t.telugu}</h2>
          <Field label={t.titleLabel} htmlFor="title_te">
            <input id="title_te" value={f.title_te} onChange={set("title_te")} maxLength={280} className={input} />
          </Field>
          <Field label={t.descriptionLabel} htmlFor="description_te">
            <textarea
              id="description_te"
              value={f.description_te}
              onChange={set("description_te")}
              rows={6}
              maxLength={10000}
              className={input}
            />
          </Field>
        </section>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t.category} htmlFor="category">
          <select id="category" value={f.category_id} onChange={set("category_id")} className={input}>
            <option value="">{t.none}</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.icon} {lang === "te" ? c.name_te : c.name_en}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t.condition} htmlFor="condition">
          <select id="condition" value={f.condition} onChange={set("condition")} className={input}>
            <option value="">{t.none}</option>
            {CONDITIONS.map((c) => (
              <option key={c} value={c}>
                {conditions[c]}
              </option>
            ))}
          </select>
        </Field>

        {isSell ? (
          <div>
            <Field label={t.price} htmlFor="price">
              <input
                id="price"
                type="number"
                inputMode="decimal"
                min={0}
                step="1"
                value={f.price}
                onChange={set("price")}
                className={input}
              />
            </Field>
            {listing.ai_price_low_cents != null && listing.ai_price_high_cents != null && (
              <p className="mt-1 text-xs text-muted">
                ✨ {t.aiPriceRange} {usd(listing.ai_price_low_cents)} to {usd(listing.ai_price_high_cents)}
              </p>
            )}
            <label className="mt-2 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={negotiable}
                onChange={(e) => setNegotiable(e.target.checked)}
              />
              {t.negotiable}
            </label>
          </div>
        ) : (
          <p className="self-end rounded-xl bg-brand-50 p-3 text-sm font-semibold text-brand-700">
            🎁 {typeLabels[listing.listing_type]}
          </p>
        )}

        <div className="grid grid-cols-[1fr_8rem] gap-3">
          <Field label={t.city} htmlFor="city">
            <input id="city" value={f.city} onChange={set("city")} maxLength={80} className={input} />
          </Field>
          <Field label={t.zip} htmlFor="zip">
            <input
              id="zip"
              value={f.zip_code}
              onChange={set("zip_code")}
              inputMode="numeric"
              pattern="\d{5}(-\d{4})?"
              className={input}
            />
          </Field>
        </div>
      </div>

      {message && (
        <p
          role={message.kind === "error" ? "alert" : "status"}
          className={`rounded-xl p-3 text-sm ${
            message.kind === "error" ? "border border-accent-400 bg-accent-100" : "bg-brand-50 text-brand-700"
          }`}
        >
          {message.text}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        {isDraft ? (
          <>
            <Button type="button" variant="accent" size="lg" disabled={!!busy} onClick={() => save("publish")}>
              {busy === "publish" ? t.publishing : t.publish}
            </Button>
            <Button type="submit" variant="secondary" size="lg" disabled={!!busy}>
              {busy === "save" ? t.saving : t.save}
            </Button>
          </>
        ) : (
          <>
            <Button type="submit" size="lg" disabled={!!busy}>
              {busy === "save" ? t.saving : t.update}
            </Button>
            {listing.status === "active" && (
              <Button type="button" variant="secondary" size="lg" disabled={!!busy} onClick={() => save("sold")}>
                {t.markSold}
              </Button>
            )}
          </>
        )}
        <Button type="button" variant="ghost" size="lg" disabled={!!busy} onClick={deleteListing} className="ml-auto">
          {t.deleteListing}
        </Button>
      </div>
    </form>
  );
}
