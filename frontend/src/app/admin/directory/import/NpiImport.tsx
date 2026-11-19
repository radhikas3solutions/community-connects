"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { BrowserApiError, browserApi } from "@/lib/browser-api";
import type { Language } from "@/lib/types";

export type NpiOptions = { presets: { key: string; label: string }[]; default_zips: string[] };

type Result = {
  postal_code: string;
  preset: string;
  practices: number;
  created: number;
  updated: number;
  already_listed: number;
  skipped_removed: number;
};
type Row = { zip: string; preset: string; result?: Result; error?: string };

const DEFAULT_PRESETS = ["dentists", "pediatricians", "family"];

export function NpiImport({ options, t, lang }: { options: NpiOptions; t: Dictionary["npiImport"]; lang: Language }) {
  const [zips, setZips] = useState(options.default_zips.join("\n"));
  const [presets, setPresets] = useState<string[]>(
    options.presets.map((p) => p.key).filter((k) => DEFAULT_PRESETS.includes(k)),
  );
  const [rows, setRows] = useState<Row[]>([]);
  const [running, setRunning] = useState(false);
  const stop = useRef(false);

  const zipList = [...new Set(zips.split(/[\s,]+/).filter((z) => /^\d{5}$/.test(z)))];
  const label = (key: string) => options.presets.find((p) => p.key === key)?.label ?? key;

  async function run() {
    const jobs: Row[] = zipList.flatMap((zip) => presets.map((preset) => ({ zip, preset })));
    setRows(jobs);
    setRunning(true);
    stop.current = false;
    // One ZIP x type per request, one at a time: gentle on the public registry and shows progress.
    for (let i = 0; i < jobs.length && !stop.current; i++) {
      const { zip, preset } = jobs[i]!;
      let row: Row;
      try {
        const result = await browserApi<Result>("/api/v1/admin/import/npi", {
          method: "POST",
          body: JSON.stringify({ postal_code: zip, preset }),
        });
        row = { zip, preset, result };
      } catch (err) {
        row = { zip, preset, error: err instanceof BrowserApiError ? err.message : t.failed };
      }
      setRows((prev) => prev.map((r, j) => (j === i ? row : r)));
    }
    setRunning(false);
  }

  const sum = (k: keyof Omit<Result, "postal_code" | "preset">) => rows.reduce((n, r) => n + (r.result?.[k] ?? 0), 0);
  const finished = rows.filter((r) => r.result || r.error).length;
  const cell = "px-2 py-1 text-right tabular-nums";

  return (
    <div className="mt-6 space-y-6" lang={lang}>
      <div className="grid gap-6 md:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-sm font-semibold">{t.zips}</span>
          <textarea
            value={zips}
            onChange={(e) => setZips(e.target.value)}
            rows={8}
            disabled={running}
            className="w-full rounded-xl border border-line bg-surface px-3 py-2 font-mono text-sm"
          />
        </label>
        <fieldset>
          <legend className="mb-1 text-sm font-semibold">{t.types}</legend>
          <div className="space-y-2">
            {options.presets.map((p) => (
              <label key={p.key} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={presets.includes(p.key)}
                  disabled={running}
                  onChange={(e) =>
                    setPresets((prev) => (e.target.checked ? [...prev, p.key] : prev.filter((k) => k !== p.key)))
                  }
                />
                {p.label}
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {running ? (
          <Button type="button" variant="secondary" onClick={() => (stop.current = true)}>
            {t.stop}
          </Button>
        ) : (
          <Button type="button" onClick={run} disabled={!zipList.length || !presets.length}>
            {t.start} ({zipList.length * presets.length})
          </Button>
        )}
        {rows.length > 0 && (
          <span className="text-sm text-muted" role="status">
            {running ? t.running : t.done} {finished}/{rows.length}
          </span>
        )}
        {!running && sum("created") > 0 && (
          <Link href="/directory?category=doctors" className="text-sm font-semibold text-brand-700 hover:underline">
            {t.open} →
          </Link>
        )}
      </div>

      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full text-sm">
            <thead className="bg-canvas text-left">
              <tr>
                <th className="px-2 py-1">{t.columns.zip}</th>
                <th className="px-2 py-1">{t.columns.type}</th>
                <th className={cell}>{t.columns.practices}</th>
                <th className={cell}>{t.columns.created}</th>
                <th className={cell}>{t.columns.updated}</th>
                <th className={cell}>{t.columns.already}</th>
                <th className={cell}>{t.columns.removed}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.zip}-${r.preset}`} className="border-t border-line">
                  <td className="px-2 py-1 font-mono">{r.zip}</td>
                  <td className="px-2 py-1">{label(r.preset)}</td>
                  {r.result ? (
                    <>
                      <td className={cell}>{r.result.practices}</td>
                      <td className={cell}>{r.result.created}</td>
                      <td className={cell}>{r.result.updated}</td>
                      <td className={cell}>{r.result.already_listed}</td>
                      <td className={cell}>{r.result.skipped_removed}</td>
                    </>
                  ) : (
                    <td colSpan={5} className="px-2 py-1 text-muted">
                      {r.error ? `⚠️ ${r.error}` : running ? "…" : ""}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t-2 border-line font-semibold">
              <tr>
                <td className="px-2 py-1" colSpan={2}>
                  {t.total}
                </td>
                <td className={cell}>{sum("practices")}</td>
                <td className={cell}>{sum("created")}</td>
                <td className={cell}>{sum("updated")}</td>
                <td className={cell}>{sum("already_listed")}</td>
                <td className={cell}>{sum("skipped_removed")}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
