"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { BrowserApiError, browserApi } from "@/lib/browser-api";
import { resizeForUpload } from "@/lib/resize-image";
import type { Business, MenuItem } from "@/lib/types";

type Row = {
  key: number;
  section: string;
  name: string;
  name_te: string;
  description: string;
  price: string;
  veg: "" | "veg" | "nonveg";
};

let nextKey = 0;
const toRow = (m: MenuItem): Row => ({
  key: nextKey++,
  section: m.section ?? "",
  name: m.name,
  name_te: m.name_te ?? "",
  description: m.description ?? "",
  price: m.price_cents == null ? "" : (m.price_cents / 100).toFixed(2),
  veg: m.is_vegetarian == null ? "" : m.is_vegetarian ? "veg" : "nonveg",
});
const blank = (section = ""): Row => ({ key: nextKey++, section, name: "", name_te: "", description: "", price: "", veg: "" });
const orNull = (s: string) => s.trim() || null;
const MAX_PHOTOS = 5;

export function MenuEditor({
  business,
  t,
  labels,
}: {
  business: Business;
  t: Dictionary["menuEditor"];
  labels: { veg: string; nonVeg: string };
}) {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<Row[]>(() => business.menu.map(toRow));
  const [busy, setBusy] = useState<null | "read" | "save">(null);
  const [message, setMessage] = useState<{ kind: "error" | "ok"; text: string } | null>(null);
  const input = "w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-sm";

  const update = (key: number, patch: Partial<Row>) =>
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  async function readPhotos(files: FileList | null) {
    if (!files?.length) return;
    setMessage(null);
    setBusy("read");
    try {
      const form = new FormData();
      const resized = await Promise.all(Array.from(files).slice(0, MAX_PHOTOS).map(resizeForUpload));
      resized.forEach((file) => form.append("photos", file, file.name));
      const { items } = await browserApi<{ items: MenuItem[] }>(
        `/api/v1/businesses/${business.id}/menu/read-photos`,
        { method: "POST", body: form },
      );
      if (rows.some((r) => r.name.trim()) && !window.confirm(t.replaceConfirm)) return;
      setRows(items.map(toRow));
      setMessage({ kind: "ok", text: t.readDone.replace("{n}", String(items.length)) });
    } catch (err) {
      const text =
        err instanceof BrowserApiError
          ? err.code === "rate_limited"
            ? t.rateLimited
            : err.status === 422
              ? err.message
              : t.error
          : t.error;
      setMessage({ kind: "error", text });
    } finally {
      setBusy(null);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function save() {
    setMessage(null);
    const items = rows
      .filter((r) => r.name.trim())
      .map((r) => {
        const price = r.price.trim() === "" ? null : Math.round(Number(r.price) * 100);
        return {
          section: orNull(r.section),
          name: r.name.trim(),
          name_te: orNull(r.name_te),
          description: orNull(r.description),
          price_cents: price == null || Number.isNaN(price) || price < 0 ? null : price,
          is_vegetarian: r.veg === "" ? null : r.veg === "veg",
        };
      });
    setBusy("save");
    try {
      const saved = await browserApi<Business>(`/api/v1/businesses/${business.id}/menu`, {
        method: "PUT",
        body: JSON.stringify({ items }),
      });
      setRows(saved.menu.map(toRow));
      setMessage({ kind: "ok", text: t.saved });
      router.refresh();
    } catch {
      setMessage({ kind: "error", text: t.error });
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="mt-12 border-t border-line pt-8">
      <h2 className="text-2xl font-bold">{t.title}</h2>
      <p className="mt-1 text-sm text-muted">{t.intro}</p>

      <div className="mt-4">
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          multiple
          className="sr-only"
          id="menu-photos"
          onChange={(e) => readPhotos(e.target.files)}
          disabled={busy !== null}
        />
        <label
          htmlFor="menu-photos"
          aria-disabled={busy !== null}
          className={`inline-flex h-11 cursor-pointer items-center gap-2 rounded-full bg-accent-500 px-5 text-sm font-semibold text-white hover:bg-accent-600 ${
            busy !== null ? "pointer-events-none opacity-60" : ""
          }`}
        >
          📸 {busy === "read" ? t.reading : t.readPhotos}
        </label>
      </div>

      {rows.length === 0 ? (
        <p className="mt-4 rounded-xl border border-dashed border-line p-6 text-center text-sm text-muted">{t.empty}</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {rows.map((r, i) => (
            <li key={r.key} className="grid gap-2 rounded-xl border border-line bg-surface p-3 sm:grid-cols-6">
              <input
                aria-label={`${t.section} ${i + 1}`}
                placeholder={t.section}
                value={r.section}
                onChange={(e) => update(r.key, { section: e.target.value })}
                className={`${input} sm:col-span-2`}
                maxLength={80}
              />
              <input
                aria-label={`${t.dish} ${i + 1}`}
                placeholder={t.dish}
                value={r.name}
                onChange={(e) => update(r.key, { name: e.target.value })}
                className={`${input} font-medium sm:col-span-3`}
                maxLength={160}
              />
              <input
                aria-label={`${t.price} ${i + 1}`}
                placeholder={t.price}
                value={r.price}
                onChange={(e) => update(r.key, { price: e.target.value })}
                inputMode="decimal"
                className={input}
              />
              <input
                aria-label={`${t.dishTe} ${i + 1}`}
                placeholder={t.dishTe}
                value={r.name_te}
                onChange={(e) => update(r.key, { name_te: e.target.value })}
                className={`${input} sm:col-span-2`}
                lang="te"
                maxLength={240}
              />
              <input
                aria-label={`${t.description} ${i + 1}`}
                placeholder={t.description}
                value={r.description}
                onChange={(e) => update(r.key, { description: e.target.value })}
                className={`${input} sm:col-span-2`}
                maxLength={500}
              />
              <select
                aria-label={`${t.vegLabel} ${i + 1}`}
                value={r.veg}
                onChange={(e) => update(r.key, { veg: e.target.value as Row["veg"] })}
                className={input}
              >
                <option value="">{t.unknown}</option>
                <option value="veg">🟢 {labels.veg}</option>
                <option value="nonveg">🔴 {labels.nonVeg}</option>
              </select>
              <button
                type="button"
                onClick={() => setRows((prev) => prev.filter((x) => x.key !== r.key))}
                className="text-sm font-medium text-red-700 hover:underline"
              >
                {t.remove}
              </button>
            </li>
          ))}
        </ul>
      )}

      {message && (
        <p
          role={message.kind === "error" ? "alert" : "status"}
          className={`mt-4 rounded-xl p-3 text-sm ${message.kind === "error" ? "bg-accent-100" : "bg-brand-50 text-brand-700"}`}
        >
          {message.text}
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-3">
        <Button
          type="button"
          variant="secondary"
          onClick={() => setRows((prev) => [...prev, blank(prev.at(-1)?.section ?? "")])}
          disabled={busy !== null}
        >
          ➕ {t.addDish}
        </Button>
        <Button type="button" onClick={save} disabled={busy !== null}>
          {busy === "save" ? "…" : t.save}
        </Button>
      </div>
    </section>
  );
}
