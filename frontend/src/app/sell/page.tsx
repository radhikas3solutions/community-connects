import type { Metadata } from "next";
import { ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";

export const metadata: Metadata = { title: "Sell or give" };

// Protected by the proxy. The AI photo-to-listing flow lands here in Phase 2.
export default async function SellPage() {
  const { t } = await getDictionary();
  return (
    <Container className="max-w-xl py-16 text-center">
      <p aria-hidden className="text-5xl">
        📸
      </p>
      <h1 className="mt-4 text-3xl font-bold">{t.home.ctaSell}</h1>
      <p className="mt-2 text-muted">{t.home.comingSoon}</p>
      <ButtonLink href="/listings" variant="secondary" className="mt-6">
        {t.home.ctaBrowse}
      </ButtonLink>
    </Container>
  );
}
