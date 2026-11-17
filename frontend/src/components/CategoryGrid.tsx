import Link from "next/link";
import type { Category, Language } from "@/lib/types";

export function CategoryGrid({
  categories,
  lang,
  hrefFor,
}: {
  categories: Category[];
  lang: Language;
  /** Return null to render a non-link tile (e.g. features not built yet). */
  hrefFor: (c: Category) => string | null;
}) {
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {categories.map((c) => {
        const href = hrefFor(c);
        const inner = (
          <>
            <span aria-hidden className="text-2xl">
              {c.icon}
            </span>
            <span className="min-w-0">
              <span className="block truncate font-semibold" lang={lang}>
                {lang === "te" ? c.name_te : c.name_en}
              </span>
              <span className="block truncate text-xs text-muted" lang={lang === "te" ? "en" : "te"}>
                {lang === "te" ? c.name_en : c.name_te}
              </span>
            </span>
          </>
        );
        const cls =
          "flex items-center gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-3 transition";
        return (
          <li key={c.id}>
            {href ? (
              <Link href={href} className={`${cls} hover:border-brand-200 hover:bg-brand-50`}>
                {inner}
              </Link>
            ) : (
              <div className={`${cls} opacity-80`}>{inner}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
