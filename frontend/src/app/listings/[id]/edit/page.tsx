import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getCategories, getListing, getMe } from "@/lib/api";
import { getSession } from "@/lib/supabase/server";
import { EditListingForm } from "./EditListingForm";

export const metadata: Metadata = { title: "Review your listing" };

export default async function EditListingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await getSession();
  if (!session) redirect(`/login?next=/listings/${id}/edit`);

  const [{ lang, t }, listing, cats, me] = await Promise.all([
    getDictionary(),
    getListing(id, session.accessToken),
    getCategories("marketplace"),
    getMe(session.accessToken).catch(() => null),
  ]);
  const isStaff = me?.role === "moderator" || me?.role === "admin";
  if (!listing || (listing.owner.id !== session.userId && !isStaff)) notFound();

  return (
    <Container className="max-w-3xl py-10">
      <h1 className="text-3xl font-bold" lang={lang}>
        {t.edit.title}
      </h1>
      <EditListingForm
        listing={listing}
        categories={cats.data}
        lang={lang}
        t={t.edit}
        conditions={t.conditions}
        typeLabels={{ sell: t.listing.sell, free: t.listing.free, buy: t.listing.wanted }}
      />
    </Container>
  );
}
