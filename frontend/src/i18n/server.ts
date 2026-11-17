import "server-only";

import { cookies, headers } from "next/headers";
import { dictionaries } from "@/i18n/dictionaries";
import type { Language } from "@/lib/types";

export const LANG_COOKIE = "cc_lang";

/** Cookie wins; otherwise honour the browser's Accept-Language; default English. */
export async function getLang(): Promise<Language> {
  const fromCookie = (await cookies()).get(LANG_COOKIE)?.value;
  if (fromCookie === "en" || fromCookie === "te") return fromCookie;
  const accept = (await headers()).get("accept-language") ?? "";
  return /^te\b/i.test(accept) ? "te" : "en";
}

export async function getDictionary() {
  const lang = await getLang();
  return { lang, t: dictionaries[lang] };
}
