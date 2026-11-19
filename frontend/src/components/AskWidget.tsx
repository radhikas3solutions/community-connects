"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ASK_STORAGE_KEY, AskChat } from "@/app/ask/AskChat";
import type { Dictionary } from "@/i18n/dictionaries";
import type { Language } from "@/lib/types";

// Pages that already are a chat, or where a floating chat would get in the way.
const HIDDEN_ON = ["/ask", "/directory/assistant", "/login", "/auth"];

/** "Ask CC": the search assistant as a floating button and panel on every page. */
export function AskWidget({ lang, t, signedIn }: { lang: Language; t: Dictionary["ask"]; signedIn: boolean }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Contact details in a saved conversation are for members only: drop it after sign-out.
  useEffect(() => {
    if (signedIn) return;
    try {
      sessionStorage.removeItem(ASK_STORAGE_KEY);
    } catch {
      // ignore
    }
  }, [signedIn]);

  if (HIDDEN_ON.some((p) => pathname === p || pathname.startsWith(`${p}/`))) return null;

  return (
    <>
      <div
        role="dialog"
        aria-label={t.title}
        hidden={!open}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        onClick={(e) => {
          // On phones the panel covers the page, so close it when a result link is followed.
          const link = (e.target as HTMLElement).closest("a[href^='/']");
          if (link && window.matchMedia("(max-width: 639px)").matches) setOpen(false);
        }}
        className={`${open ? "flex" : "hidden"} fixed inset-0 z-50 flex-col overflow-hidden bg-surface shadow-2xl sm:inset-auto sm:right-6 sm:bottom-24 sm:h-[min(40rem,calc(100dvh-8rem))] sm:w-[26rem] sm:rounded-[var(--radius-card)] sm:border sm:border-line`}
      >
        <div className="flex items-center justify-between gap-2 border-b border-line bg-brand-600 px-4 py-3 text-white">
          <p className="font-semibold" lang={lang}>
            ✨ {t.title}
          </p>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label={t.close}
            className="grid size-8 place-items-center rounded-full text-xl hover:bg-white/15"
          >
            ×
          </button>
        </div>
        <div className="min-h-0 flex-1">
          {signedIn ? (
            <AskChat lang={lang} t={t} compact active={open} />
          ) : (
            <div className="space-y-4 p-6" lang={lang}>
              <p>{t.greeting}</p>
              <p className="text-muted">{t.signInPrompt}</p>
              <Link
                href={`/login?next=${encodeURIComponent(pathname)}`}
                className="inline-block rounded-full bg-brand-600 px-5 py-2 font-semibold text-white"
              >
                {t.signIn}
              </Link>
            </div>
          )}
        </div>
      </div>

      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-full bg-brand-600 px-5 py-3 font-semibold text-white shadow-lg hover:bg-brand-700 sm:right-6 sm:bottom-6"
          lang={lang}
        >
          <span aria-hidden>✨</span> {t.launcher}
        </button>
      )}
    </>
  );
}
