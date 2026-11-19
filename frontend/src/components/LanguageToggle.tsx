"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { LANG_COOKIE } from "@/i18n/constants";
import type { Language } from "@/lib/types";


function persistLanguage(lang: Language) {
  document.cookie = `${LANG_COOKIE}=${lang}; path=/; max-age=31536000; samesite=lax`;
}

export function LanguageToggle({ lang }: { lang: Language }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function choose(next: Language) {
    if (next === lang) return;
    persistLanguage(next);
    // A shared link's `?lang=` would override the new choice, so drop it from the URL.
    const url = new URL(window.location.href);
    if (url.searchParams.has("lang")) {
      url.searchParams.delete("lang");
      startTransition(() => router.replace(url.pathname + url.search + url.hash));
      return;
    }
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
            lang === code ? "bg-accent-500 text-white" : "text-muted hover:text-accent-600"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
