import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getSession } from "@/lib/supabase/server";
import { AskChat } from "./AskChat";

export const metadata: Metadata = {
  title: "Ask Community Connect",
  description: "Find doctors, dentists, tutors, helpers, restaurants and used items in Northern Virginia.",
};

export default async function AskPage({ searchParams }: { searchParams: Promise<{ q?: string | string[] }> }) {
  const sp = await searchParams;
  const q = (Array.isArray(sp.q) ? sp.q[0] : sp.q)?.trim().slice(0, 1000) || "";
  const session = await getSession();
  if (!session) redirect(`/login?next=${encodeURIComponent(q ? `/ask?q=${encodeURIComponent(q)}` : "/ask")}`);
  const { lang, t } = await getDictionary();

  return (
    <Container className="max-w-4xl py-10">
      <h1 className="text-3xl font-bold" lang={lang}>
        ✨ {t.ask.title}
      </h1>
      <p className="mt-2 max-w-2xl text-muted" lang={lang}>
        {t.ask.intro}
      </p>
      <AskChat lang={lang} t={t.ask} initialQuestion={q} />
    </Container>
  );
}
