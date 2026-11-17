import type { Metadata } from "next";
import Link from "next/link";
import { ListingCard } from "@/components/ListingCard";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getCategories, searchListings } from "@/lib/api";

export const metadata: Metadata = { title: "Browse listings" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);

export default async function ListingsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const params = {
    q: one(sp.q),
    listing_type: one(sp.listing_type),
    category: one(sp.category),
    sort: one(sp.sort) ?? "newest",
    offset: one(sp.offset),
  };
  const [{ lang, t }, cats, results] = await Promise.all([
    getDictionary(),
    getCategories("marketplace"),
    searchListings(params),
  ]);

  const typeTabs = [
    { value: undefined, label: t.browse.all },
    { value: "sell", label: t.listing.sell },
    { value: "free", label: t.listing.free },
    { value: "buy", label: t.listing.wanted },
  ];
  const hrefWith = (patch: Record<string, string | undefined>) => {
    const qs = new URLSearchParams(
      Object.entries({ ...params, offset: undefined, ...patch }).filter((e): e is [string, string] => Boolean(e[1])),
    );
    return `/listings${qs.size ? `?${qs}` : ""}`;
  };

  return (
    <Container className="py-8">
      <h1 className="mb-6 text-3xl font-bold">{t.browse.title}</h1>

      <form action="/listings" className="mb-4 flex gap-2" role="search">
        {params.listing_type && <input type="hidden" name="listing_type" value={params.listing_type} />}
        {params.category && <input type="hidden" name="category" value={params.category} />}
        <label htmlFor="q" className="sr-only">
          {t.browse.search}
        </label>
        <input
          id="q"
          name="q"
          defaultValue={params.q}
          placeholder={t.browse.search}
          className="h-11 flex-1 rounded-full border border-line bg-surface px-4"
        />
        <Button type="submit">{t.browse.searchButton}</Button>
      </form>

      <nav aria-label="Listing type" className="mb-4 flex flex-wrap gap-2">
        {typeTabs.map((tab) => {
          const active = params.listing_type === tab.value;
          return (
            <Link
              key={tab.label}
              href={hrefWith({ listing_type: tab.value })}
              aria-current={active ? "page" : undefined}
              className={`rounded-full border px-4 py-1.5 text-sm font-medium ${
                active ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-surface hover:bg-brand-50"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>

      {cats.data.length > 0 && (
        <nav aria-label="Categories" className="mb-6 flex gap-2 overflow-x-auto pb-2">
          {cats.data.map((c) => {
            const active = params.category === c.slug;
            return (
              <Link
                key={c.id}
                href={hrefWith({ category: active ? undefined : c.slug })}
                aria-current={active ? "page" : undefined}
                className={`shrink-0 rounded-full border px-3 py-1 text-sm ${
                  active ? "border-accent-500 bg-accent-100" : "border-line bg-surface hover:bg-brand-50"
                }`}
                lang={lang}
              >
                {c.icon} {lang === "te" ? c.name_te : c.name_en}
              </Link>
            );
          })}
        </nav>
      )}

      {!results.ok ? (
        <p role="status" className="rounded-xl border border-accent-400 bg-accent-100 p-4 text-sm">
          {t.apiOffline}
        </p>
      ) : (
        <>
          <p className="mb-4 text-sm text-muted">{t.browse.results(results.data.total)}</p>
          {results.data.items.length ? (
            <ul className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
              {results.data.items.map((l) => (
                <li key={l.id}>
                  <ListingCard listing={l} lang={lang} t={t} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-xl border border-dashed border-line p-8 text-center text-muted">{t.listing.empty}</p>
          )}
        </>
      )}
    </Container>
  );
}
