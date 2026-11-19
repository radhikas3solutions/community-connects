import { ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";

/** A directory entry that no longer exists (removed, or re-imported under a new link). */
export default async function EntryNotFound() {
  const { lang, t } = await getDictionary();
  return (
    <Container className="max-w-xl py-24 text-center">
      <div lang={lang}>
        <p aria-hidden className="text-6xl">
          🔎
        </p>
        <h1 className="mt-4 text-2xl font-bold">{t.directory.goneTitle}</h1>
        <p className="mt-2 text-muted">{t.directory.goneText}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <ButtonLink href="/directory">{t.directory.goneSearch}</ButtonLink>
          <ButtonLink href="/ask" variant="secondary">
            ✨ {t.nav.ask}
          </ButtonLink>
        </div>
      </div>
    </Container>
  );
}
