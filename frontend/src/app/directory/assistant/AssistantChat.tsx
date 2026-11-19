"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { BrowserApiError, browserApi } from "@/lib/browser-api";
import type { Business, Category, EntryKind, Language } from "@/lib/types";

type Message = { role: "user" | "assistant"; content: string };

type Draft = {
  kind: EntryKind | null;
  category_id: number | null;
  name: string | null;
  name_te: string | null;
  description_en: string | null;
  description_te: string | null;
  phone: string | null;
  whatsapp: string | null;
  email: string | null;
  website: string | null;
  address: string | null;
  city: string | null;
  zip_code: string | null;
  service_area: string | null;
  hours: string | null;
  languages: string[];
  is_self: boolean | null;
  other_person_agreed: boolean | null;
};

type DirectoryLabels = Pick<
  Dictionary["directory"],
  "call" | "whatsapp" | "email" | "website" | "address" | "serviceArea" | "hours" | "languages" | "individual"
>;

type TurnResponse = {
  reply: string;
  draft: Draft;
  missing: string[];
  ready: boolean;
};

const MAX_MESSAGES = 38; // the API accepts 40; leave room for the next turn

export function AssistantChat({
  categories,
  lang,
  t,
  languageNames,
  directoryLabels,
}: {
  categories: Category[];
  lang: Language;
  t: Dictionary["assistant"];
  languageNames: Record<string, string>;
  directoryLabels: DirectoryLabels;
}) {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [missing, setMissing] = useState<string[]>([]);
  const [ready, setReady] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<null | "chat" | "submit">(null);
  const [error, setError] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  async function send(content: string) {
    content = content.trim();
    if (!content || busy) return;
    if (messages.length >= MAX_MESSAGES) return setError(t.tooLong);
    const history: Message[] = [...messages, { role: "user", content }];
    setMessages(history);
    setText("");
    setError(null);
    setBusy("chat");
    try {
      const res = await browserApi<TurnResponse>("/api/v1/assistant/directory-intake", {
        method: "POST",
        body: JSON.stringify({ messages: history, draft, lang }),
      });
      setMessages([...history, { role: "assistant", content: res.reply }]);
      setDraft(res.draft);
      setMissing(res.missing);
      setReady(res.ready);
    } catch (err) {
      // Let them resend: put their text back and drop the unanswered message.
      setMessages(messages);
      setText(content);
      setError(err instanceof BrowserApiError && err.code === "rate_limited" ? t.rateLimited : t.error);
    } finally {
      setBusy(null);
    }
  }

  async function submit() {
    if (!draft || !ready) return;
    const isIndividual = draft.kind === "individual";
    if (isIndividual && !consent) return;
    setBusy("submit");
    setError(null);
    try {
      // is_self / other_person_agreed are chat-only; the checkbox above is the actual consent.
      const fields: Partial<Draft> = { ...draft };
      delete fields.is_self;
      delete fields.other_person_agreed;
      const created = await browserApi<Business>("/api/v1/businesses", {
        method: "POST",
        body: JSON.stringify({
          ...fields,
          consent_confirmed: isIndividual ? consent : false,
        }),
      });
      router.push(`/directory/${created.id}`);
      router.refresh();
    } catch (err) {
      const detail = err instanceof BrowserApiError && err.status === 422 ? ` (${err.message})` : "";
      setError(`${t.error}${detail}`);
      setBusy(null);
    }
  }

  function startOver() {
    setMessages([]);
    setDraft(null);
    setMissing([]);
    setReady(false);
    setConsent(false);
    setError(null);
    setText("");
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(text);
  };

  return (
    <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      {/* Chat */}
      <section
        aria-label="Chat"
        className="flex min-h-[28rem] flex-col rounded-[var(--radius-card)] border border-line bg-surface"
      >
        <ol className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
          <Bubble role="assistant" lang={lang}>
            {t.greeting}
          </Bubble>
          {messages.map((m, i) => (
            <Bubble key={i} role={m.role}>
              {m.content}
            </Bubble>
          ))}
          {busy === "chat" && (
            <li className="text-sm text-muted" lang={lang}>
              {t.thinking}
            </li>
          )}
          <div ref={bottom} />
        </ol>

        {messages.length === 0 && (
          <div className="flex flex-wrap gap-2 px-4 pb-3">
            {t.examples.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => send(ex)}
                className="rounded-full border border-line bg-canvas px-3 py-1 text-sm hover:bg-brand-50"
                lang={lang}
              >
                {ex}
              </button>
            ))}
          </div>
        )}

        {error && (
          <p role="alert" className="mx-4 mb-3 rounded-xl bg-accent-100 p-3 text-sm" lang={lang}>
            {error}
          </p>
        )}

        <form onSubmit={onSubmit} className="flex gap-2 border-t border-line p-3">
          <label htmlFor="chat-input" className="sr-only">
            {t.placeholder}
          </label>
          <textarea
            id="chat-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void send(text);
              }
            }}
            placeholder={t.placeholder}
            rows={2}
            maxLength={2000}
            className="min-w-0 flex-1 resize-none rounded-xl border border-line bg-surface px-3 py-2"
            disabled={busy !== null}
          />
          <Button type="submit" disabled={busy !== null || !text.trim()} className="self-end">
            {t.send}
          </Button>
        </form>
      </section>

      {/* Live preview */}
      <aside aria-label={t.preview} className="space-y-4">
        <div className="rounded-[var(--radius-card)] border border-line bg-surface p-4">
          <h2 className="mb-3 text-sm font-bold tracking-wide text-muted uppercase" lang={lang}>
            {t.preview}
          </h2>
          {draft ? (
            <Preview
              draft={draft}
              categories={categories}
              lang={lang}
              languageNames={languageNames}
              d={directoryLabels}
            />
          ) : (
            <p className="text-sm text-muted" lang={lang}>
              {t.previewEmpty}
            </p>
          )}
          {draft && missing.length > 0 && (
            <p className="mt-4 rounded-xl bg-canvas p-3 text-sm" lang={lang}>
              <span className="font-semibold">{t.stillNeeded}</span> {missing.map((m) => t.need[m] ?? m).join(", ")}
            </p>
          )}
        </div>

        {draft && ready && (
          <div className="space-y-3 rounded-[var(--radius-card)] border border-brand-200 bg-brand-50 p-4" lang={lang}>
            {draft.kind === "individual" && (
              <label className="flex items-start gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  className="mt-1"
                />
                {draft.is_self === false ? t.consentOther : t.consentSelf}
              </label>
            )}
            <Button
              type="button"
              onClick={submit}
              disabled={busy !== null || (draft.kind === "individual" && !consent)}
              className="w-full"
            >
              {busy === "submit" ? t.submitting : t.submit}
            </Button>
            <p className="text-xs text-muted">{t.reviewNote}</p>
          </div>
        )}

        <div className="flex flex-wrap justify-between gap-2 text-sm">
          {messages.length > 0 && (
            <button type="button" onClick={startOver} className="font-semibold text-brand-700 hover:underline">
              ↺ {t.startOver}
            </button>
          )}
          <Link href="/directory/new" className="ml-auto text-muted hover:underline">
            {t.preferForm}
          </Link>
        </div>
      </aside>
    </div>
  );
}

function Bubble({ role, lang, children }: { role: Message["role"]; lang?: Language; children: string }) {
  const mine = role === "user";
  return (
    <li className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <p
        lang={lang}
        className={`max-w-[85%] rounded-2xl px-4 py-2 whitespace-pre-line ${
          mine ? "rounded-br-sm bg-brand-600 text-white" : "rounded-bl-sm bg-canvas"
        }`}
      >
        {children}
      </p>
    </li>
  );
}

function Preview({
  draft,
  categories,
  lang,
  languageNames,
  d,
}: {
  draft: Draft;
  categories: Category[];
  lang: Language;
  languageNames: Record<string, string>;
  d: DirectoryLabels;
}) {
  const category = categories.find((c) => c.id === draft.category_id);
  const name = (lang === "te" && draft.name_te) || draft.name;
  const description =
    lang === "te" ? draft.description_te || draft.description_en : draft.description_en || draft.description_te;
  const rows: [string, string | null][] = [
    [d.call, draft.phone],
    [d.whatsapp, draft.whatsapp],
    [d.email, draft.email],
    [d.website, draft.website],
    [d.address, draft.address],
    ["📍", draft.city],
    [d.serviceArea, draft.service_area],
    [d.hours, draft.hours],
    [d.languages, draft.languages.map((c) => languageNames[c] ?? c).join(", ") || null],
  ];
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span aria-hidden className="grid size-12 shrink-0 place-items-center rounded-xl bg-brand-50 text-2xl">
          {category?.icon ?? "📍"}
        </span>
        <div className="min-w-0">
          <p className="truncate text-lg font-semibold">{name || "…"}</p>
          <p className="text-sm text-muted" lang={lang}>
            {[
              category ? (lang === "te" ? category.name_te : category.name_en) : null,
              draft.kind === "individual" ? d.individual : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      </div>
      {description && (
        <p className="text-sm" lang={lang === "te" && draft.description_te ? "te" : "en"}>
          {description}
        </p>
      )}
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        {rows
          .filter(([, v]) => v)
          .map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-muted">{label}</dt>
              <dd className="break-words">{value}</dd>
            </div>
          ))}
      </dl>
    </div>
  );
}
