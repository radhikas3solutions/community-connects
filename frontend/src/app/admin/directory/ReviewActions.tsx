"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { browserApi } from "@/lib/browser-api";

export function ReviewActions({ id, t }: { id: string; t: Dictionary["review"] }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState(false);

  async function review(action: "approve" | "reject", verified?: boolean) {
    setBusy(true);
    setError(false);
    try {
      await browserApi(`/api/v1/businesses/${id}/review`, {
        method: "POST",
        body: JSON.stringify({
          action,
          ...(action === "reject" ? { note: note.trim() || null } : {}),
          ...(verified ? { is_verified: true } : {}),
        }),
      });
      setDone(true);
      router.refresh();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  if (done) return <p className="text-sm font-semibold text-brand-700">✓ {t.done}</p>;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => review("approve")} disabled={busy}>
          {t.approve}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => review("approve", true)} disabled={busy}>
          ✓ {t.approveVerified}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setRejecting((v) => !v)} disabled={busy} className="text-red-700">
          {t.reject}
        </Button>
      </div>
      {rejecting && (
        <div className="flex flex-wrap gap-2">
          <label htmlFor={`note-${id}`} className="sr-only">
            {t.rejectReason}
          </label>
          <input
            id={`note-${id}`}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t.rejectReason}
            maxLength={500}
            className="h-9 min-w-0 flex-1 rounded-full border border-line bg-surface px-3 text-sm"
          />
          <Button size="sm" variant="accent" onClick={() => review("reject")} disabled={busy}>
            {t.reject}
          </Button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          ⚠️
        </p>
      )}
    </div>
  );
}
