"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import type { Language } from "@/lib/types";

const LANG_COOKIE = "cc_lang"; // keep in sync with i18n/server.ts

function persistLanguage(lang: Language) {
  document.cookie = `${LANG_COOKIE}=${lang}; path=/; max-age=31536000; samesite=lax`;
}

export function LanguageToggle({ lang }: { lang: Language }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function choose(next: Language) {
    if (next === lang) return;
    persistLanguage(next);
    // Re-render server components with the new dictionary.
    startTransition(() => router.refresh());
  }

  return (
    <div
      role="group"
      aria-label="Language / భాష"
      className={`inline-flex rounded-full border border-line bg-surface p-0.5 text-xs font-semibold ${pending ? "opacity-60" : ""}`}
    >
      {(
        [
          ["en", "EN"],
          ["te", "తెలుగు"],
        ] as const
      ).map(([code, label]) => (
        <button
          key={code}
          type="button"
          lang={code}
          aria-pressed={lang === code}
          onClick={() => choose(code)}
          className={`rounded-full px-3 py-1.5 transition-colors ${
            lang === code ? "bg-brand-600 text-white" : "text-muted hover:text-ink"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
