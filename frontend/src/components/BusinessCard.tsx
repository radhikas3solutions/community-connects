import Link from "next/link";
import type { Dictionary } from "@/i18n/dictionaries";
import { businessName, directionsHref, telHref } from "@/lib/directory";
import type { Business, Language } from "@/lib/types";

export function BusinessCard({ business: b, lang, t }: { business: Business; lang: Language; t: Dictionary }) {
  const category = b.category ? (lang === "te" ? b.category.name_te : b.category.name_en) : null;
  const where = b.kind === "individual" ? b.service_area || b.city : b.city;
  const map = directionsHref(b);
  const langs = b.languages
    .slice(0, 3)
    .map((code) => t.directory.languageNames[code] ?? code)
    .join(", ");

  return (
    <article className="relative flex h-full gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-4 transition-shadow focus-within:shadow-md hover:shadow-md">
      <span aria-hidden className="grid size-12 shrink-0 place-items-center rounded-xl bg-brand-50 text-2xl">
        {b.category?.icon ?? "📍"}
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <h3 className="font-semibold" lang={lang === "te" && b.name_te ? "te" : undefined}>
          {/* Stretched link: the whole card is clickable, but only the name is announced. */}
          <Link href={`/directory/${b.id}`} className="after:absolute after:inset-0">
            {businessName(b, lang)}
          </Link>
          {b.is_verified && (
            <span className="ml-2 align-middle text-xs font-semibold text-brand-700" title={t.directory.verified}>
              ✓ {t.directory.verified}
            </span>
          )}
          {b.source === "npi" && (
            <span className="ml-2 align-middle text-xs font-semibold text-muted" lang={lang}>
              📋 {t.directory.publicRecord}
            </span>
          )}
          {b.source === "osm" && (
            <span className="ml-2 align-middle text-xs font-semibold text-muted" lang={lang}>
              🗺️ {t.directory.osmRecord}
            </span>
          )}
        </h3>
        {b.specialty && <p className="text-sm font-semibold text-brand-700">{b.specialty}</p>}
        {category && (
          <p className="text-sm text-muted" lang={lang}>
            {category}
            {b.kind === "individual" && ` · ${t.directory.individual}`}
          </p>
        )}
        {where && <p className="truncate text-sm">📍 {where}</p>}
        {langs && (
          <p className="truncate text-xs text-muted" lang={lang}>
            🗣️ {langs}
          </p>
        )}
        {(b.phone || map) && (
          // Above the stretched link (relative z-10) so the buttons work on their own.
          <div className="relative z-10 flex flex-wrap gap-2 pt-2 text-sm" lang={lang}>
            {b.phone && (
              <a
                href={telHref(b.phone)}
                className="rounded-full bg-accent-500 px-3 py-1 font-semibold text-white hover:bg-accent-600"
              >
                📞 {t.directory.call}
              </a>
            )}
            {map && (
              <a
                href={map}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-full border border-line px-3 py-1 font-semibold hover:bg-brand-50"
              >
                🗺️ {t.directory.map}
              </a>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
