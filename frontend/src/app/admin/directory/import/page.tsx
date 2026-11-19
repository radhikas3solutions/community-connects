import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { apiFetch, getMe } from "@/lib/api";
import { getSession } from "@/lib/supabase/server";
import { NpiImport, type NpiOptions } from "./NpiImport";
import { OsmImport, type OsmOptions } from "./OsmImport";

export const metadata: Metadata = { title: "Import public data" };

export default async function ImportPage() {
  const session = await getSession();
  if (!session) redirect("/login?next=/admin/directory/import");
  const [{ lang, t }, me] = await Promise.all([getDictionary(), getMe(session.accessToken).catch(() => null)]);
  if (me?.role !== "moderator" && me?.role !== "admin") notFound();
  const [npi, osm] = await Promise.all([
    apiFetch<NpiOptions>("/api/v1/admin/import/npi", { token: session.accessToken }),
    apiFetch<OsmOptions>("/api/v1/admin/import/osm", { token: session.accessToken }),
  ]);

  return (
    <Container className="max-w-4xl py-10">
      <h1 className="text-3xl font-bold" lang={lang}>
        📋 {t.npiImport.pageTitle}
      </h1>

      <section className="mt-8 rounded-[var(--radius-card)] border border-line bg-surface p-5">
        <h2 className="text-xl font-bold" lang={lang}>
          🍽️ {t.osmImport.title}
        </h2>
        <p className="mt-2 text-sm text-muted" lang={lang}>
          {t.osmImport.intro}
        </p>
        <OsmImport options={osm} t={t.osmImport} common={t.npiImport} lang={lang} />
      </section>

      <section className="mt-8 rounded-[var(--radius-card)] border border-line bg-surface p-5">
        <h2 className="text-xl font-bold" lang={lang}>
          🩺 {t.npiImport.title}
        </h2>
        <p className="mt-2 text-sm text-muted" lang={lang}>
          {t.npiImport.intro}
        </p>
        <NpiImport options={npi} t={t.npiImport} lang={lang} />
      </section>
    </Container>
  );
}
