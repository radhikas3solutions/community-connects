"use client";

import type { AuthError } from "@supabase/supabase-js";
import { useState, type FormEvent, type ReactNode } from "react";
import { PhoneInput } from "@/components/PhoneInput";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { emptyPhone, toInternational } from "@/lib/phone";
import { createClient } from "@/lib/supabase/client";

/**
 * Email + password accounts. Registering asks for name, email and phone and emails a one-time
 * code to confirm the address; after that, signing in is just email and password (no email).
 * Forgotten passwords are reset with an emailed code. Codes work on any device or browser.
 */
type Mode = "signin" | "register" | "verify" | "forgot" | "reset";

const MIN_PASSWORD = 8;

const inputClass = "h-11 w-full rounded-xl border border-line bg-surface px-4";

function Field({ id, label, help, children }: { id: string; label: string; help?: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      {children}
      {help && <p className="text-xs text-muted">{help}</p>}
    </div>
  );
}

export function LoginForm({ t, next, google: showGoogle }: { t: Dictionary["auth"]; next: string; google: boolean }) {
  const [mode, setMode] = useState<Mode>("signin");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [notice, setNotice] = useState("");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState(emptyPhone);
  const [whatsappSame, setWhatsappSame] = useState(true);
  const [whatsapp, setWhatsapp] = useState(emptyPhone);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");

  const supabase = createClient();

  function go(nextMode: Mode) {
    setMode(nextMode);
    setProblem("");
    setNotice("");
    setCode("");
  }

  // A full page load, so the server sees the new sign-in cookies.
  const finish = () => window.location.assign(next);

  function explain(error: AuthError): string {
    console.error("[login]", error.code ?? error.status, error.message);
    if (error.status === 429 || /rate limit/i.test(error.message)) return t.tooManyEmails;
    switch (error.code) {
      case "invalid_credentials":
        return t.badLogin;
      case "otp_expired":
      case "invalid_otp":
        return t.badCode;
      case "weak_password":
        return t.weakPassword;
      case "user_already_exists":
      case "email_exists":
        return t.exists;
      case "same_password":
        return t.samePassword;
      default:
        return `${t.error} (${error.code ?? error.message})`;
    }
  }

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setProblem("");
    setNotice("");
    try {
      await work();
    } finally {
      setBusy(false);
    }
  }

  const signIn = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => {
      const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
      if (!error) return finish();
      if (error.code === "email_not_confirmed") {
        // Registered but never entered the code: send a fresh one.
        await supabase.auth.resend({ type: "signup", email: email.trim() });
        go("verify");
        setNotice(t.notVerified);
        return;
      }
      setProblem(explain(error));
    });
  };

  const register = (e: FormEvent) => {
    e.preventDefault();
    const phoneNumber = toInternational(phone);
    if (!phoneNumber) return setProblem(t.badPhone);
    const whatsappNumber = whatsappSame ? phoneNumber : whatsapp.number.trim() ? toInternational(whatsapp) : null;
    if (!whatsappSame && whatsapp.number.trim() && !whatsappNumber) return setProblem(t.badWhatsapp);
    if (password.length < MIN_PASSWORD) return setProblem(t.weakPassword);
    return run(async () => {
      const { data, error } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: {
            first_name: firstName.trim(),
            last_name: lastName.trim(),
            phone: phoneNumber,
            ...(whatsappNumber ? { whatsapp: whatsappNumber } : {}),
          },
          emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`,
        },
      });
      if (error) return setProblem(explain(error));
      if (data.session) return finish(); // email confirmation is switched off
      // Supabase hides whether an email is registered: an existing account comes back with no identities.
      if (data.user && data.user.identities?.length === 0) {
        go("signin");
        setProblem(t.exists);
        return;
      }
      go("verify");
    });
  };

  const verify = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => {
      const { error } = await supabase.auth.verifyOtp({ email: email.trim(), token: code.trim(), type: "email" });
      if (error) return setProblem(explain(error));
      finish();
    });
  };

  const resend = () =>
    run(async () => {
      const { error } = await supabase.auth.resend({ type: "signup", email: email.trim() });
      if (error) setProblem(explain(error));
      else setNotice(t.resent);
    });

  const sendReset = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => {
      const { error } = await supabase.auth.resetPasswordForEmail(email.trim());
      if (error) return setProblem(explain(error));
      setPassword("");
      go("reset");
    });
  };

  const reset = (e: FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) return setProblem(t.weakPassword);
    return run(async () => {
      const { error } = await supabase.auth.verifyOtp({ email: email.trim(), token: code.trim(), type: "recovery" });
      if (error) return setProblem(explain(error));
      const { error: saveError } = await supabase.auth.updateUser({ password });
      if (saveError) return setProblem(explain(saveError));
      finish();
    });
  };

  async function google() {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}` },
    });
    if (error) setProblem(explain(error));
  }

  const emailField = (
    <Field id="email" label={t.email}>
      <input
        id="email"
        type="email"
        required
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className={inputClass}
      />
    </Field>
  );

  const codeField = (
    <Field id="code" label={t.code}>
      <input
        id="code"
        required
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9]{6,10}"
        maxLength={10}
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
        className={`${inputClass} text-center text-xl tracking-[0.4em]`}
      />
    </Field>
  );

  const passwordField = (id: string, label: string, autoComplete: string, help?: string) => (
    <Field id={id} label={label} help={help}>
      <input
        id={id}
        type="password"
        required
        minLength={autoComplete === "new-password" ? MIN_PASSWORD : undefined}
        autoComplete={autoComplete}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className={inputClass}
      />
    </Field>
  );

  const messages = (
    <>
      {notice && (
        <p role="status" className="rounded-lg bg-brand-50 p-3 text-sm text-brand-700">
          {notice}
        </p>
      )}
      {problem && (
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {problem}
        </p>
      )}
    </>
  );

  const backLink = (
    <button type="button" onClick={() => go("signin")} className="text-sm font-semibold text-brand-700 hover:underline">
      ← {t.back}
    </button>
  );

  if (mode === "verify") {
    return (
      <form onSubmit={verify} className="mt-6 space-y-4">
        <h2 className="text-lg font-semibold">✉️ {t.verifyTitle}</h2>
        <p className="text-sm text-muted">{t.verifyText.replace("{email}", email.trim())}</p>
        {codeField}
        {messages}
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? t.working : t.verify}
        </Button>
        <div className="flex items-center justify-between">
          {backLink}
          <button type="button" onClick={resend} disabled={busy} className="text-sm text-muted hover:underline">
            {t.resend}
          </button>
        </div>
      </form>
    );
  }

  if (mode === "forgot" || mode === "reset") {
    return mode === "forgot" ? (
      <form onSubmit={sendReset} className="mt-6 space-y-4">
        <h2 className="text-lg font-semibold">{t.forgotTitle}</h2>
        <p className="text-sm text-muted">{t.forgotText}</p>
        {emailField}
        {messages}
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? t.working : t.sendCode}
        </Button>
        {backLink}
      </form>
    ) : (
      <form onSubmit={reset} className="mt-6 space-y-4">
        <h2 className="text-lg font-semibold">{t.forgotTitle}</h2>
        <p className="text-sm text-muted">{t.resetText.replace("{email}", email.trim())}</p>
        {codeField}
        {passwordField("new-password", t.newPassword, "new-password", t.passwordHelp)}
        {messages}
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? t.working : t.savePassword}
        </Button>
        {backLink}
      </form>
    );
  }

  return (
    <div className="mt-6 space-y-4">
      <div
        role="tablist"
        className="grid grid-cols-2 rounded-full border border-line bg-canvas p-1 text-sm font-semibold"
      >
        {(
          [
            ["signin", t.tabSignIn],
            ["register", t.tabRegister],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={mode === key}
            onClick={() => go(key)}
            className={`rounded-full py-2 transition-colors ${
              mode === key ? "bg-accent-500 text-white" : "text-muted hover:text-accent-600"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === "signin" ? (
        <form onSubmit={signIn} className="space-y-4">
          {emailField}
          {passwordField("password", t.password, "current-password")}
          <div className="text-right">
            <button type="button" onClick={() => go("forgot")} className="text-sm text-brand-700 hover:underline">
              {t.forgot}
            </button>
          </div>
          {messages}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? t.working : t.signIn}
          </Button>
          <p className="text-xs text-muted">{t.oldAccount}</p>
        </form>
      ) : (
        <form onSubmit={register} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field id="first-name" label={t.firstName}>
              <input
                id="first-name"
                required
                maxLength={60}
                autoComplete="given-name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field id="last-name" label={t.lastName}>
              <input
                id="last-name"
                required
                maxLength={60}
                autoComplete="family-name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className={inputClass}
              />
            </Field>
          </div>
          {emailField}
          <Field id="phone" label={t.phone} help={t.phoneHelp}>
            <PhoneInput id="phone" value={phone} onChange={setPhone} required countryLabel={t.country} />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={whatsappSame}
              onChange={(e) => setWhatsappSame(e.target.checked)}
              className="size-4 accent-[var(--color-accent-500)]"
            />
            {t.whatsappSame}
          </label>
          {!whatsappSame && (
            <Field id="whatsapp" label={t.whatsapp} help={t.whatsappHelp}>
              <PhoneInput id="whatsapp" value={whatsapp} onChange={setWhatsapp} countryLabel={t.country} />
            </Field>
          )}
          {passwordField("new-password", t.password, "new-password", t.passwordHelp)}
          {messages}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? t.working : t.createAccount}
          </Button>
        </form>
      )}

      {showGoogle && (
        <>
          <div className="flex items-center gap-3 text-xs text-muted">
            <span className="h-px flex-1 bg-line" />
            {t.or}
            <span className="h-px flex-1 bg-line" />
          </div>
          <Button type="button" variant="secondary" className="w-full" onClick={google}>
            {t.google}
          </Button>
        </>
      )}
    </div>
  );
}
