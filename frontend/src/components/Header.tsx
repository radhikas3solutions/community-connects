import Link from "next/link";
import { LanguageToggle } from "@/components/LanguageToggle";
import { ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import type { Dictionary } from "@/i18n/dictionaries";
import type { Language } from "@/lib/types";

export function Header({ t, lang, signedIn }: { t: Dictionary; lang: Language; signedIn: boolean }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/90 backdrop-blur">
      <Container className="flex h-16 items-center gap-4">
        <Link href="/" className="flex items-center gap-2 font-bold text-brand-700">
          <span aria-hidden className="grid size-8 place-items-center rounded-xl bg-brand-600 text-white">
            CC
          </span>
          <span className="hidden sm:inline">{t.brand}</span>
        </Link>

        <nav aria-label="Main" className="ml-4 hidden items-center gap-1 text-sm font-medium md:flex">
          <Link href="/listings" className="rounded-full px-3 py-2 hover:bg-brand-50">
            {t.nav.browse}
          </Link>
          <span className="cursor-default rounded-full px-3 py-2 text-muted" title={t.home.comingSoon}>
            {t.nav.directory}
          </span>
          <span className="cursor-default rounded-full px-3 py-2 text-muted" title={t.home.comingSoon}>
            {t.nav.events}
          </span>
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <LanguageToggle lang={lang} />
          {signedIn ? (
            <ButtonLink href="/account" variant="secondary" size="sm">
              {t.nav.account}
            </ButtonLink>
          ) : (
            <ButtonLink href="/login" variant="primary" size="sm">
              {t.nav.signIn}
            </ButtonLink>
          )}
        </div>
      </Container>
    </header>
  );
}
