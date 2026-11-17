"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { createClient } from "@/lib/supabase/client";

type State = "idle" | "sending" | "sent" | "error";

export function LoginForm({ t, next }: { t: Dictionary["auth"]; next: string }) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<State>("idle");

  const redirectTo = () =>
    `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`;

  async function sendLink(e: FormEvent) {
    e.preventDefault();
    setState("sending");
    const { error } = await createClient().auth.signInWithOtp({
      email,
      options: { emailRedirectTo: redirectTo() },
    });
    setState(error ? "error" : "sent");
  }

  async function google() {
    const { error } = await createClient().auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: redirectTo() },
    });
    if (error) setState("error");
  }

  if (state === "sent") {
    return (
      <p role="status" className="mt-6 rounded-lg bg-brand-50 p-4 text-brand-700">
        ✉️ {t.checkEmail}
      </p>
    );
  }

  return (
    <div className="mt-6 space-y-4">
      <form onSubmit={sendLink} className="space-y-3">
        <label htmlFor="email" className="block text-sm font-medium">
          {t.email}
        </label>
        <input
          id="email"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="h-11 w-full rounded-xl border border-line px-4"
        />
        <Button type="submit" className="w-full" disabled={state === "sending"}>
          {state === "sending" ? t.sending : t.sendLink}
        </Button>
      </form>
      {state === "error" && (
        <p role="alert" className="text-sm text-red-700">
          {t.error}
        </p>
      )}
      <div className="flex items-center gap-3 text-xs text-muted">
        <span className="h-px flex-1 bg-line" />
        {t.or}
        <span className="h-px flex-1 bg-line" />
      </div>
      <Button type="button" variant="secondary" className="w-full" onClick={google}>
        {t.google}
      </Button>
    </div>
  );
}
