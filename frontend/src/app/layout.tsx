import type { Metadata, Viewport } from "next";
import { Inter, Noto_Sans_Telugu } from "next/font/google";
import type { ReactNode } from "react";
import { AskWidget } from "@/components/AskWidget";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { getDictionary } from "@/i18n/server";
import { SITE_URL } from "@/lib/env";
import { getSession } from "@/lib/supabase/server";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const telugu = Noto_Sans_Telugu({
  subsets: ["telugu"],
  weight: ["400", "600", "700"],
  variable: "--font-telugu",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "AskMitra · Northern Virginia", template: "%s · AskMitra" },
  description:
    "Buy, sell and give away items, find local Indian & Telugu businesses, deals, jobs, movies and events in Northern Virginia.",
  appleWebApp: { capable: true, title: "AskMitra", statusBarStyle: "default" },
  openGraph: { type: "website", siteName: "AskMitra", locale: "en_US", alternateLocale: ["te_IN"] },
};

export const viewport: Viewport = { themeColor: "#cc4f0b", width: "device-width", initialScale: 1 };

export default async function RootLayout({ children }: { children: ReactNode }) {
  const [{ lang, t }, session] = await Promise.all([getDictionary(), getSession()]);
  return (
    <html lang={lang} className={`${inter.variable} ${telugu.variable}`}>
      <body className="flex min-h-dvh flex-col font-sans">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-surface focus:p-2"
        >
          Skip to content
        </a>
        <Header t={t} lang={lang} signedIn={Boolean(session)} />
        <main id="main" className="flex-1">
          {children}
        </main>
        <Footer t={t} />
        <AskWidget lang={lang} t={t.ask} signedIn={Boolean(session)} />
      </body>
    </html>
  );
}
