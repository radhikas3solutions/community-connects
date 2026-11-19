import type { Metadata } from "next";
import Link from "next/link";
import { BusinessCard } from "@/components/BusinessCard";
import { CategoryGrid } from "@/components/CategoryGrid";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getCategories, searchDirectory } from "@/lib/api";

export const metadata: Metadata = {
  title: "Local directory",
  description: "Doctors, helpers, plumbers, tailors, restaurants and more in Northern Virginia.",
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
const LANGUAGE_FILTERS = ["te", "hi", "ta", "kn", "en"];

export default async function DirectoryPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const params = {
    q: one(sp.q),
    category: one(sp.category),
    language: one(sp.language),
    city: one(sp.city),
    offset: one(sp.offset),
  };
  const filtered = Boolean(params.q || params.category || params.language || params.city);
  const [{ lang, t }, cats, results] = await Promise.all([
    getDictionary(),
    getCategories("business"),
    searchDirectory({ ...params, limit: "48" }),
  ]);
  const d = t.directory;
  const select = "h-11 rounded-full border border-line bg-surface px-4";

  return (
    <Container className="py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold" lang={lang}>
            {d.title}
          </h1>
          <p className="mt-1 text-muted" lang={lang}>
            {d.subtitle}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ButtonLink href="/directory/assistant" variant="accent">
            💬 {t.assistant.cta}
          </ButtonLink>
          <ButtonLink href="/directory/new" variant="secondary">
            ➕ {d.add}
          </ButtonLink>
        </div>
      </div>

      <form action="/directory" className="mb-6 grid gap-2 md:grid-cols-[1fr_auto_auto_auto_auto]" role="search">
        <label htmlFor="q" className="sr-only">
          {d.search}
        </label>
        <input
          id="q"
          name="q"
          defaultValue={params.q}
          placeholder={d.search}
          className="h-11 rounded-full border border-line bg-surface px-4"
        />
        <label htmlFor="category" className="sr-only">
          {t.entryForm.category}
        </label>
        <select id="category" name="category" defaultValue={params.category ?? ""} className={select}>
          <option value="">{d.anyCategory}</option>
          {cats.data.map((c) => (
            <option key={c.id} value={c.slug}>
              {c.icon} {lang === "te" ? c.name_te : c.name_en}
            </option>
          ))}
        </select>
        <label htmlFor="language" className="sr-only">
          {d.languages}
        </label>
        <select id="language" name="language" defaultValue={params.language ?? ""} className={select}>
          <option value="">{d.anyLanguage}</option>
          {LANGUAGE_FILTERS.map((code) => (
            <option key={code} value={code}>
              {d.languageNames[code]}
            </option>
          ))}
        </select>
        <label htmlFor="city" className="sr-only">
          {d.city}
        </label>
        <input id="city" name="city" defaultValue={params.city} placeholder={d.city} className={select} />
        <Button type="submit">{d.searchButton}</Button>
      </form>

      {!filtered && cats.data.length > 0 && (
        <div className="mb-10">
          <CategoryGrid categories={cats.data} lang={lang} hrefFor={(c) => `/directory?category=${c.slug}`} />
        </div>
      )}

      {!results.ok ? (
        <p role="status" className="rounded-xl border border-accent-400 bg-accent-100 p-4 text-sm">
          {t.apiOffline}
        </p>
      ) : (
        <>
          <p className="mb-4 text-sm text-muted">
            {d.results(results.data.total)}
            {filtered && (
              <>
                {" · "}
                <Link href="/directory" className="text-brand-700 hover:underline">
                  {d.anyCategory}
                </Link>
              </>
            )}
          </p>
          {results.data.items.length ? (
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {results.data.items.map((b) => (
                <li key={b.id}>
                  <BusinessCard business={b} lang={lang} t={t} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-xl border border-dashed border-line p-8 text-center text-muted" lang={lang}>
              {d.empty}
            </p>
          )}
        </>
      )}
    </Container>
  );
}
