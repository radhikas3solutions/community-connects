import type { MetadataRoute } from "next";

/** Makes the site installable ("Add to Home Screen" / "Install app") with the AskMitra icon. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "AskMitra · Northern Virginia",
    short_name: "AskMitra",
    description:
      "Find doctors, dentists, restaurants, tutors and helpers, and buy, sell or give away items in Northern Virginia.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f6f8fb",
    theme_color: "#cc4f0b",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
