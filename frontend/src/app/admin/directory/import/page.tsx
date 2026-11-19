import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { apiFetch, getMe } from "@/lib/api";
import { getSession } from "@/lib/supabase/server";
import { NpiImport, type NpiOptions } from "./NpiImport";

export const metadata: Metadata = { title: "Import doctors & dentists" };

export default async function NpiImportPage() {
  const session = await getSession();
  if (!session) redirect("/login?next=/admin/directory/import");
  const [{ lang, t }, me] = await Promise.all([getDictionary(), getMe(session.accessToken).catch(() => null)]);
  if (me?.role !== "moderator" && me?.role !== "admin") notFound();
  const options = await apiFetch<NpiOptions>("/api/v1/admin/import/npi", { token: session.accessToken });

  return (
    <Container className="max-w-4xl py-10">
      <h1 className="text-3xl font-bold" lang={lang}>
        📋 {t.npiImport.title}
      </h1>
      <p className="mt-2 max-w-3xl text-muted" lang={lang}>
        {t.npiImport.intro}
      </p>
      <NpiImport options={options} t={t.npiImport} lang={lang} />
    </Container>
  );
}
