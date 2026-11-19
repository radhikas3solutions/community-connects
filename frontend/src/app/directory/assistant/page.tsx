import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getCategories } from "@/lib/api";
import { getSession } from "@/lib/supabase/server";
import { AssistantChat } from "./AssistantChat";

export const metadata: Metadata = { title: "Add your business or service" };

export default async function AssistantPage() {
  const session = await getSession();
  if (!session) redirect("/login?next=/directory/assistant");
  const [{ lang, t }, cats] = await Promise.all([getDictionary(), getCategories("business")]);
  const d = t.directory;
  // Only plain strings can cross to a client component (t.directory has a function).
  const directoryLabels = {
    call: d.call,
    whatsapp: d.whatsapp,
    email: d.email,
    website: d.website,
    address: d.address,
    serviceArea: d.serviceArea,
    hours: d.hours,
    languages: d.languages,
    individual: d.individual,
  };

  return (
    <Container className="py-10">
      <h1 className="text-3xl font-bold" lang={lang}>
        💬 {t.assistant.title}
      </h1>
      <p className="mt-2 max-w-2xl text-muted" lang={lang}>
        {t.assistant.intro}
      </p>
      <AssistantChat
        categories={cats.data}
        lang={lang}
        t={t.assistant}
        languageNames={t.directory.languageNames}
        directoryLabels={directoryLabels}
      />
    </Container>
  );
}
