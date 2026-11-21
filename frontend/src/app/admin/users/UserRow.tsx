"use client";

import { useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { browserApi } from "@/lib/browser-api";
import { whatsappLink } from "@/lib/phone";
import type { AdminProfile, Language, UserRole } from "@/lib/types";

const ROLES: UserRole[] = ["user", "business", "moderator", "admin"];

export function UserRow({
  user,
  isSelf,
  t,
  lang,
}: {
  user: AdminProfile;
  isSelf: boolean;
  t: Dictionary["adminUsers"];
  lang: Language;
}) {
  const [current, setCurrent] = useState(user);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<"" | "saved" | "failed">("");

  async function save(change: { role?: UserRole; is_banned?: boolean }) {
    setBusy(true);
    setStatus("");
    try {
      setCurrent(
        await browserApi<AdminProfile>(`/api/v1/admin/users/${user.id}`, {
          method: "PATCH",
          body: JSON.stringify(change),
        }),
      );
      setStatus("saved");
    } catch {
      setStatus("failed");
    } finally {
      setBusy(false);
    }
  }

  const name = current.display_name || [current.first_name, current.last_name].filter(Boolean).join(" ") || "—";

  return (
    <li className={`flex flex-wrap items-center gap-3 p-4 ${current.is_banned ? "bg-red-50" : ""}`}>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">
          {name}
          {isSelf && <span className="ml-2 rounded-full bg-brand-100 px-2 py-0.5 text-xs text-brand-700">{t.you}</span>}
          {current.is_banned && (
            <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700">{t.suspended}</span>
          )}
        </p>
        <p className="truncate text-sm text-muted">{current.email}</p>
        {(current.phone || current.whatsapp) && (
          <p className="flex flex-wrap gap-x-4 text-sm">
            {current.phone && (
              <a href={`tel:${current.phone}`} className="text-brand-700 hover:underline">
                📞 {current.phone}
              </a>
            )}
            {current.whatsapp && (
              <a
                href={whatsappLink(current.whatsapp)}
                target="_blank"
                rel="noopener"
                className="text-brand-700 hover:underline"
              >
                💬 {current.whatsapp}
              </a>
            )}
          </p>
        )}
        <p className="text-xs text-muted">
          {t.joined} {new Date(current.created_at).toLocaleDateString(lang === "te" ? "te-IN" : "en-US")}
        </p>
      </div>
      <label className="sr-only" htmlFor={`role-${user.id}`}>
        {t.roleLabel}
      </label>
      <select
        id={`role-${user.id}`}
        value={current.role}
        disabled={busy || isSelf}
        onChange={(e) => save({ role: e.target.value as UserRole })}
        className="h-9 rounded-full border border-line bg-surface px-3 text-sm"
      >
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {t.roles[r]}
          </option>
        ))}
      </select>
      {!isSelf && (
        <button
          type="button"
          disabled={busy}
          onClick={() => save({ is_banned: !current.is_banned })}
          className={`h-9 rounded-full px-4 text-sm font-semibold ${
            current.is_banned ? "bg-brand-600 text-white" : "border border-red-300 text-red-700 hover:bg-red-50"
          }`}
        >
          {current.is_banned ? t.restore : t.suspend}
        </button>
      )}
      {status && (
        <span role="status" className={`w-full text-xs ${status === "saved" ? "text-brand-700" : "text-red-700"}`}>
          {status === "saved" ? `✓ ${t.saved}` : t.failed}
        </span>
      )}
    </li>
  );
}
