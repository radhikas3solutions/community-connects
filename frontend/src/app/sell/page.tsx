import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getSession } from "@/lib/supabase/server";
import { SellFlow } from "./SellFlow";

export const metadata: Metadata = { title: "Sell or give" };

export default async function SellPage() {
  const session = await getSession();
  if (!session) redirect("/login?next=/sell");
  const { lang, t } = await getDictionary();

  return (
    <Container className="max-w-xl py-10">
      <h1 className="text-3xl font-bold" lang={lang}>
        📸 {t.sell.title}
      </h1>
      <p className="mt-2 mb-8 text-muted" lang={lang}>
        {t.sell.intro}
      </p>
      <SellFlow t={t.sell} />
    </Container>
  );
}
