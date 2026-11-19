import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getMe, getReviewQueue } from "@/lib/api";
import { businessName } from "@/lib/directory";
import { getSession } from "@/lib/supabase/server";
import { ReviewActions } from "./ReviewActions";

export const metadata: Metadata = { title: "Directory review queue" };

export default async function ReviewQueuePage() {
  const session = await getSession();
  if (!session) redirect("/login?next=/admin/directory");
  const [{ lang, t }, me] = await Promise.all([getDictionary(), getMe(session.accessToken).catch(() => null)]);
  if (me?.role !== "moderator" && me?.role !== "admin") notFound();

  const queue = await getReviewQueue(session.accessToken);
  const d = t.directory;

  return (
    <Container className="max-w-3xl py-10">
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-3xl font-bold" lang={lang}>
          {t.review.title}
        </h1>
        <Link href="/admin/directory/import" className="text-sm font-semibold text-brand-700 hover:underline">
          📋 {t.npiImport.link}
        </Link>
      </div>
      {queue.length === 0 ? (
        <p className="rounded-xl border border-dashed border-line p-8 text-center text-muted">{t.review.empty}</p>
      ) : (
        <ul className="space-y-4">
          {queue.map((b) => (
            <li key={b.id} className="space-y-3 rounded-[var(--radius-card)] border border-line bg-surface p-4">
              <div>
                <Link href={`/directory/${b.id}`} className="text-lg font-semibold hover:underline">
                  {b.category?.icon} {businessName(b, lang)}
                </Link>
                <p className="text-sm text-muted">
                  {[
                    b.category ? (lang === "te" ? b.category.name_te : b.category.name_en) : null,
                    b.kind === "individual" ? d.individual : null,
                    b.city,
                    `${t.review.added} ${new Date(b.created_at).toLocaleDateString(lang === "te" ? "te-IN" : "en-US")}`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                {b.phone && (
                  <>
                    <dt className="text-muted">{d.call}</dt>
                    <dd>{b.phone}</dd>
                  </>
                )}
                {b.whatsapp && (
                  <>
                    <dt className="text-muted">{d.whatsapp}</dt>
                    <dd>{b.whatsapp}</dd>
                  </>
                )}
                {b.email && (
                  <>
                    <dt className="text-muted">{d.email}</dt>
                    <dd>{b.email}</dd>
                  </>
                )}
                {b.website && (
                  <>
                    <dt className="text-muted">{d.website}</dt>
                    <dd className="break-all">{b.website}</dd>
                  </>
                )}
                {b.address && (
                  <>
                    <dt className="text-muted">{d.address}</dt>
                    <dd>{b.address}</dd>
                  </>
                )}
              </dl>
              {b.description_en && <p className="text-sm">{b.description_en}</p>}
              <ReviewActions id={b.id} t={t.review} />
            </li>
          ))}
        </ul>
      )}
    </Container>
  );
}
