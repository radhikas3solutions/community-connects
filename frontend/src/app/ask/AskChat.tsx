"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { BrowserApiError, browserApi } from "@/lib/browser-api";
import { businessName, telHref, whatsappChatHref } from "@/lib/directory";
import { formatPrice, localized } from "@/lib/format";
import type { Business, Language, Listing } from "@/lib/types";

type Message = { role: "user" | "assistant"; content: string };
type Answer = { reply: string; businesses: Business[]; listings: Listing[] };
type Turn = Message & { businesses?: Business[]; listings?: Listing[] };

const MAX_MESSAGES = 28; // the API accepts 30; leave room for the next question

export function AskChat({
  lang,
  t,
  initialQuestion,
}: {
  lang: Language;
  t: Dictionary["ask"];
  initialQuestion: string;
}) {
  const router = useRouter();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const askedInitial = useRef(false);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, busy]);

  async function send(content: string, history: Turn[] = turns) {
    content = content.trim();
    if (!content || busy) return;
    if (history.length >= MAX_MESSAGES) return setError(t.tooLong);
    const next: Turn[] = [...history, { role: "user", content }];
    setTurns(next);
    setText("");
    setError(null);
    setBusy(true);
    try {
      const res = await browserApi<Answer>("/api/v1/assistant/ask", {
        method: "POST",
        body: JSON.stringify({
          messages: next.map(({ role, content }) => ({ role, content })),
          lang,
        }),
      });
      setTurns([
        ...next,
        { role: "assistant", content: res.reply, businesses: res.businesses, listings: res.listings },
      ]);
    } catch (err) {
      // Let them resend: put their text back and drop the unanswered question.
      setTurns(history);
      setText(content);
      setError(err instanceof BrowserApiError && err.code === "rate_limited" ? t.rateLimited : t.error);
    } finally {
      setBusy(false);
    }
  }

  // A question typed on the home page arrives as ?q=; ask it once, then tidy the URL.
  useEffect(() => {
    if (!initialQuestion || askedInitial.current) return;
    askedInitial.current = true;
    router.replace("/ask", { scroll: false });
    void send(initialQuestion, []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(text);
  };

  return (
    <section
      aria-label={t.title}
      className="mt-6 flex min-h-[28rem] flex-col rounded-[var(--radius-card)] border border-line bg-surface"
    >
      <ol className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
        <Bubble mine={false} lang={lang}>
          {t.greeting}
        </Bubble>
        {turns.map((turn, i) => (
          <li key={i} className="space-y-3">
            <Bubble mine={turn.role === "user"} as="div">
              {turn.content}
            </Bubble>
            {!!turn.businesses?.length && (
              <Results title={t.fromDirectory} lang={lang}>
                {turn.businesses.map((b) => (
                  <BusinessRow key={b.id} b={b} lang={lang} t={t} />
                ))}
              </Results>
            )}
            {!!turn.listings?.length && (
              <Results title={t.fromMarketplace} lang={lang}>
                {turn.listings.map((l) => (
                  <ListingRow key={l.id} l={l} lang={lang} t={t} />
                ))}
              </Results>
            )}
          </li>
        ))}
        {busy && (
          <li className="text-sm text-muted" lang={lang}>
            🔎 {t.thinking}
          </li>
        )}
        <div ref={bottom} />
      </ol>

      {turns.length === 0 && !busy && (
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
        <label htmlFor="ask-input" className="sr-only">
          {t.placeholder}
        </label>
        <input
          id="ask-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t.placeholder}
          maxLength={1000}
          autoComplete="off"
          className="h-11 min-w-0 flex-1 rounded-full border border-line bg-surface px-4"
          disabled={busy}
        />
        <Button type="submit" disabled={busy || !text.trim()}>
          {t.send}
        </Button>
      </form>
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 pb-3 text-xs text-muted" lang={lang}>
        <span>{t.note}</span>
        {turns.length > 0 && (
          <button
            type="button"
            onClick={() => {
              setTurns([]);
              setError(null);
              setText("");
            }}
            className="font-semibold text-brand-700 hover:underline"
          >
            ↺ {t.startOver}
          </button>
        )}
      </div>
    </section>
  );
}

function Bubble({
  mine,
  lang,
  as = "li",
  children,
}: {
  mine: boolean;
  lang?: Language;
  as?: "li" | "div";
  children: string;
}) {
  const Tag = as;
  return (
    <Tag className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <p
        lang={lang}
        className={`max-w-[85%] rounded-2xl px-4 py-2 whitespace-pre-line ${
          mine ? "rounded-br-sm bg-brand-600 text-white" : "rounded-bl-sm bg-canvas"
        }`}
      >
        {children}
      </p>
    </Tag>
  );
}

function Results({ title, lang, children }: { title: string; lang: Language; children: React.ReactNode }) {
  return (
    <div className="ml-0 space-y-2 sm:ml-6">
      <p className="text-xs font-bold tracking-wide text-muted uppercase" lang={lang}>
        {title}
      </p>
      <ul className="grid gap-2 sm:grid-cols-2">{children}</ul>
    </div>
  );
}

function BusinessRow({ b, lang, t }: { b: Business; lang: Language; t: Dictionary["ask"] }) {
  const category = b.category ? (lang === "te" ? b.category.name_te : b.category.name_en) : null;
  const where = b.kind === "individual" ? b.service_area || b.city : b.city;
  const whatsapp = b.whatsapp || b.phone;
  return (
    <li className="flex gap-3 rounded-xl border border-line bg-surface p-3">
      <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-lg bg-brand-50 text-xl">
        {b.category?.icon ?? "📍"}
      </span>
      <div className="min-w-0 flex-1">
        <Link href={`/directory/${b.id}`} className="font-semibold hover:underline">
          {businessName(b, lang)}
        </Link>
        {b.is_verified && <span className="ml-1 text-xs text-brand-700">✓ {t.verified}</span>}
        <p className="truncate text-sm text-muted">{[category, where].filter(Boolean).join(" · ")}</p>
        {(b.phone || whatsapp) && (
          <div className="mt-2 flex flex-wrap gap-2 text-sm">
            {b.phone && (
              <a href={telHref(b.phone)} className="rounded-full bg-brand-600 px-3 py-1 font-semibold text-white">
                📞 {t.call}
              </a>
            )}
            {whatsapp && (
              <a
                href={whatsappChatHref(whatsapp)}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-full border border-line px-3 py-1 font-semibold"
              >
                💬 {t.whatsapp}
              </a>
            )}
          </div>
        )}
      </div>
    </li>
  );
}

function ListingRow({ l, lang, t }: { l: Listing; lang: Language; t: Dictionary["ask"] }) {
  const cover = l.images?.[0];
  return (
    <li className="flex gap-3 rounded-xl border border-line bg-surface p-3">
      {cover ? (
        // eslint-disable-next-line @next/next/no-img-element -- signed, short-lived URL
        <img src={cover.url} alt="" className="size-14 shrink-0 rounded-lg object-cover" />
      ) : (
        <span aria-hidden className="grid size-14 shrink-0 place-items-center rounded-lg bg-brand-50 text-xl">
          {l.category?.icon ?? "🛍️"}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <Link href={`/listings/${l.id}`} className="font-semibold hover:underline">
          {localized(l.title_en, l.title_te, lang)}
        </Link>
        <p className="text-sm">
          <span className="font-semibold text-brand-700">
            {l.listing_type === "buy" ? t.wanted : formatPrice(l, lang)}
          </span>
          {l.city && <span className="text-muted"> · {l.city}</span>}
        </p>
      </div>
    </li>
  );
}
