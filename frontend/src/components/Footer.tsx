import { Container } from "@/components/ui/Container";
import type { Dictionary } from "@/i18n/dictionaries";

export function Footer({ t }: { t: Dictionary }) {
  return (
    <footer className="mt-16 border-t border-line bg-surface">
      <Container className="flex flex-col gap-2 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
        <p>
          © {new Date().getFullYear()} {t.brand}. {t.footer.madeFor}
        </p>
        <nav aria-label="Footer" className="flex gap-4">
          <span>{t.footer.privacy}</span>
          <span>{t.footer.terms}</span>
        </nav>
      </Container>
    </footer>
  );
}
