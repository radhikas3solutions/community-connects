import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getCategories } from "@/lib/api";
import { getSession } from "@/lib/supabase/server";
import { BusinessForm } from "../BusinessForm";

export const metadata: Metadata = { title: "Add to the directory" };

export default async function NewBusinessPage() {
  const session = await getSession();
  if (!session) redirect("/login?next=/directory/new");
  const [{ lang, t }, cats] = await Promise.all([getDictionary(), getCategories("business")]);

  return (
    <Container className="max-w-3xl py-10">
      <h1 className="text-3xl font-bold" lang={lang}>
        {t.entryForm.titleNew}
      </h1>
      <p className="mt-2 text-muted" lang={lang}>
        {t.entryForm.intro}{" "}
        <Link href="/directory/assistant" className="font-semibold text-brand-700 hover:underline">
          💬 {t.assistant.cta}
        </Link>
      </p>
      <BusinessForm categories={cats.data} lang={lang} t={t.entryForm} languageNames={t.directory.languageNames} />
    </Container>
  );
}
