import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";
import { getAdminUsers, getMe } from "@/lib/api";
import { getSession } from "@/lib/supabase/server";
import { UserRow } from "./UserRow";

export const metadata: Metadata = { title: "Members and access" };

export default async function AdminUsersPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const session = await getSession();
  if (!session) redirect("/login?next=/admin/users");
  const [{ lang, t }, me] = await Promise.all([getDictionary(), getMe(session.accessToken).catch(() => null)]);
  if (me?.role !== "admin") notFound();

  const { q } = await searchParams;
  const users = await getAdminUsers(session.accessToken, q?.trim() || undefined);
  const a = t.adminUsers;

  return (
    <Container className="max-w-3xl py-10">
      <h1 className="text-3xl font-bold" lang={lang}>
        {a.title}
      </h1>
      <p className="mt-2 text-muted" lang={lang}>
        {a.intro}
      </p>
      <form className="mt-6 flex gap-2" role="search">
        <label htmlFor="q" className="sr-only">
          {a.search}
        </label>
        <input
          id="q"
          name="q"
          defaultValue={q ?? ""}
          placeholder={a.search}
          className="h-11 min-w-0 flex-1 rounded-full border border-line bg-surface px-4"
        />
        <button type="submit" className="rounded-full bg-accent-500 px-5 font-semibold text-white hover:bg-accent-600">
          {a.searchButton}
        </button>
      </form>
      {users.length === 0 ? (
        <p className="mt-6 rounded-xl border border-dashed border-line p-8 text-center text-muted">{a.empty}</p>
      ) : (
        <ul className="mt-6 divide-y divide-line rounded-[var(--radius-card)] border border-line bg-surface">
          {users.map((u) => (
            <UserRow key={u.id} user={u} isSelf={u.id === me.id} t={a} lang={lang} />
          ))}
        </ul>
      )}
    </Container>
  );
}
