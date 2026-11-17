"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { BrowserApiError, browserApi } from "@/lib/browser-api";
import { resizeForUpload } from "@/lib/resize-image";
import type { Listing } from "@/lib/types";

const MAX_PHOTOS = 5;

type Photo = { id: string; file: File; preview: string };
type ErrorKey = keyof Dictionary["sell"]["errors"];

export function SellFlow({ t }: { t: Dictionary["sell"] }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [listingType, setListingType] = useState<"sell" | "free">("sell");
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addFiles(files: FileList | null) {
    if (!files?.length) return;
    setError(null);
    const room = MAX_PHOTOS - photos.length;
    if (files.length > room) setError(t.tooMany);
    const added = Array.from(files)
      .slice(0, Math.max(room, 0))
      .map((file) => ({ id: crypto.randomUUID(), file, preview: URL.createObjectURL(file) }));
    setPhotos((prev) => [...prev, ...added]);
    if (inputRef.current) inputRef.current.value = "";
  }

  function removePhoto(id: string) {
    setPhotos((prev) => {
      const gone = prev.find((p) => p.id === id);
      if (gone) URL.revokeObjectURL(gone.preview);
      return prev.filter((p) => p.id !== id);
    });
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!photos.length) {
      setError(t.needPhoto);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.set("listing_type", listingType);
      if (note.trim()) form.set("note", note.trim());
      const resized = await Promise.all(photos.map((p) => resizeForUpload(p.file)));
      resized.forEach((file) => form.append("photos", file, file.name));

      const listing = await browserApi<Listing>("/api/v1/ai/draft-listing", { method: "POST", body: form });
      router.push(`/listings/${listing.id}/edit`);
    } catch (err) {
      const code = err instanceof BrowserApiError ? err.code : "generic";
      setError(t.errors[(code in t.errors ? code : "generic") as ErrorKey]);
      setBusy(false);
    }
  }

  if (busy) {
    return (
      <div role="status" aria-live="polite" className="py-16 text-center">
        <p aria-hidden className="animate-pulse text-5xl">
          ✨
        </p>
        <p className="mt-4 text-lg font-semibold">{t.working}</p>
        <p className="mt-1 text-sm text-muted">{t.workingHint}</p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <fieldset>
        <legend className="mb-2 font-semibold">{t.typeLabel}</legend>
        <div className="grid grid-cols-2 gap-3">
          {(["sell", "free"] as const).map((type) => (
            <label
              key={type}
              className={`flex cursor-pointer items-center justify-center rounded-xl border p-3 text-center font-medium ${
                listingType === type ? "border-brand-600 bg-brand-50 text-brand-700" : "border-line bg-surface"
              }`}
            >
              <input
                type="radio"
                name="listing_type"
                value={type}
                checked={listingType === type}
                onChange={() => setListingType(type)}
                className="sr-only"
              />
              {type === "sell" ? `🏷️ ${t.typeSell}` : `🎁 ${t.typeFree}`}
            </label>
          ))}
        </div>
      </fieldset>

      <div>
        <p className="font-semibold">{t.photosLabel}</p>
        <p className="mb-3 text-sm text-muted">{t.photosHelp}</p>
        {photos.length > 0 && (
          <ul className="mb-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
            {photos.map((p, i) => (
              <li key={p.id} className="relative aspect-square overflow-hidden rounded-lg border border-line">
                {/* Local preview (blob: URL), not a remote image */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={p.preview} alt={`${t.photosLabel} ${i + 1}`} className="h-full w-full object-cover" />
                <button
                  type="button"
                  onClick={() => removePhoto(p.id)}
                  aria-label={`${t.remove} ${i + 1}`}
                  className="absolute top-1 right-1 grid h-7 w-7 place-items-center rounded-full bg-ink/70 text-white"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        {photos.length < MAX_PHOTOS && (
          <label className="flex h-28 cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-brand-200 bg-brand-50 text-brand-700 hover:bg-brand-100">
            <span aria-hidden className="text-3xl">
              📷
            </span>
            <span className="font-medium">{photos.length ? t.addMore : t.takePhoto}</span>
            <input
              ref={inputRef}
              type="file"
              // Listing only these makes iPhones convert HEIC photos to JPEG on upload.
              accept="image/jpeg,image/png,image/webp"
              multiple
              className="sr-only"
              onChange={(e) => addFiles(e.target.files)}
            />
          </label>
        )}
      </div>

      <div>
        <label htmlFor="note" className="mb-1 block font-semibold">
          {t.noteLabel}
        </label>
        <textarea
          id="note"
          value={note}
          maxLength={500}
          rows={3}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t.notePlaceholder}
          className="w-full rounded-xl border border-line bg-surface p-3"
        />
      </div>

      {error && (
        <p role="alert" className="rounded-xl border border-accent-400 bg-accent-100 p-3 text-sm">
          {error}
        </p>
      )}

      <Button type="submit" variant="accent" size="lg" className="w-full">
        ✨ {t.submit}
      </Button>
    </form>
  );
}
