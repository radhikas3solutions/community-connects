"use client";

import { useState } from "react";
import { buttonClass } from "@/components/ui/Button";

export function ShareListing({
  text,
  url,
  labels,
}: {
  /** Full message including the link. */
  text: string;
  url: string;
  labels: { title: string; whatsapp: string; copy: string; copied: string };
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt(labels.copy, url);
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-sm font-semibold">{labels.title}</p>
      <div className="flex flex-wrap gap-2">
        <a
          href={`https://wa.me/?text=${encodeURIComponent(text)}`}
          target="_blank"
          rel="noopener noreferrer"
          className={buttonClass("primary", "md", "bg-[#25D366] text-[#073b1d] hover:bg-[#1ebe5a]")}
        >
          <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="currentColor">
            <path d="M12.04 2a9.9 9.9 0 0 0-8.5 15l-1.4 5.1 5.2-1.4A9.9 9.9 0 1 0 12.04 2Zm0 18.1a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3.1.8.8-3-.2-.3a8.2 8.2 0 1 1 7 3.9Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.3-.4.8-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.1-1.2l-.4-.3Z" />
          </svg>
          {labels.whatsapp}
        </a>
        <button type="button" onClick={copy} className={buttonClass("secondary", "md")} aria-live="polite">
          🔗 {copied ? labels.copied : labels.copy}
        </button>
      </div>
    </div>
  );
}
