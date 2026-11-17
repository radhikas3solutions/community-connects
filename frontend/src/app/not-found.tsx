import { ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/i18n/server";

export default async function NotFound() {
  const { t } = await getDictionary();
  return (
    <Container className="py-24 text-center">
      <p className="text-6xl font-extrabold text-brand-200">404</p>
      <h1 className="mt-4 text-2xl font-bold">{t.errors.notFound}</h1>
      <ButtonLink href="/" className="mt-6">
        {t.errors.home}
      </ButtonLink>
    </Container>
  );
}
