import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getBusiness, getCategories } from "@/lib/api";
import { businessName } from "@/lib/directory";
import { getSession } from "@/lib/supabase/server";
import { BusinessForm } from "../../BusinessForm";
import { MenuEditor } from "./MenuEditor";

export const metadata: Metadata = { title: "Edit directory entry" };

// Categories where a menu makes sense.
const MENU_CATEGORIES = new Set(["restaurants", "catering-tiffin", "indian-grocery"]);

export default async function EditBusinessPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await getSession();
  if (!session) redirect(`/login?next=/directory/${id}/edit`);

  const [{ lang, t }, business, cats] = await Promise.all([
    getDictionary(),
    getBusiness(id, session.accessToken),
    getCategories("business"),
  ]);
  if (!business || !business.can_edit) notFound();
  const showMenu = business.menu.length > 0 || MENU_CATEGORIES.has(business.category?.slug ?? "");

  return (
    <Container className="max-w-3xl py-10">
      <Link href={`/directory/${business.id}`} className="text-sm text-brand-700 hover:underline">
        ← {businessName(business, lang)}
      </Link>
      <h1 className="mt-2 text-3xl font-bold" lang={lang}>
        {t.entryForm.titleEdit}
      </h1>
      <BusinessForm
        business={business}
        categories={cats.data}
        lang={lang}
        t={t.entryForm}
        languageNames={t.directory.languageNames}
      />
      {showMenu && (
        <MenuEditor business={business} t={t.menuEditor} labels={{ veg: t.directory.veg, nonVeg: t.directory.nonVeg }} />
      )}
    </Container>
  );
}
