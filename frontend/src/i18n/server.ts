import "server-only";

import { cookies, headers } from "next/headers";
import { LANG_COOKIE, LANG_OVERRIDE_HEADER } from "@/i18n/constants";
import { dictionaries } from "@/i18n/dictionaries";
import type { Language } from "@/lib/types";


/** `?lang=` (shared links) wins, then the cookie, then Accept-Language; default English. */
export async function getLang(): Promise<Language> {
  const override = (await headers()).get(LANG_OVERRIDE_HEADER);
  if (override === "en" || override === "te") return override;
  const fromCookie = (await cookies()).get(LANG_COOKIE)?.value;
  if (fromCookie === "en" || fromCookie === "te") return fromCookie;
  const accept = (await headers()).get("accept-language") ?? "";
  return /^te\b/i.test(accept) ? "te" : "en";
}

export async function getDictionary() {
  const lang = await getLang();
  return { lang, t: dictionaries[lang] };
}
